import os
import time
import asyncio
import edge_tts
import ctypes
import tempfile
import threading
from core.config import CONFIG
from mutagen.mp3 import MP3
from core.avatar import start_lip_sync

SYNC_DELAY = 2.0

# ── Control global de TTS ─────────────────────────────────────────────────────
# Lock que serializa toda reproducción: sólo un speak_text() corre a la vez.
_tts_lock = threading.Lock()

# Alias MCI del clip actualmente en reproducción (para poder interrumpirlo).
_current_alias: str | None = None
_alias_lock    = threading.Lock()          # protege _current_alias

# Cuando se setea, el thread de TTS activo aborta la reproducción.
_tts_interrupted = threading.Event()

# Seteado mientras el audio está sonando por los altavoces.
# micro_to_text lo usa para descartar chunks y evitar auto-feedback.
tts_playing = threading.Event()

# Seteado desde que ZIL empieza a generar la respuesta hasta que termina de hablar.
# Evita que el micrófono se abra mientras ella está "pensando" o hablando.
tts_busy = threading.Event()


def interrupt_tts() -> None:
    """
    Detiene inmediatamente cualquier audio TTS en reproducción y descarta
    los clips que estén en cola esperando el lock.
    Llámalo desde engine.enter_conversation() antes de hablar por mic.
    """
    global _current_alias
    _tts_interrupted.set()
    with _alias_lock:
        alias = _current_alias
    if alias:
        try:
            ctypes.windll.winmm.mciSendStringW(f"stop {alias}", None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)
        except Exception:
            pass


def get_mp3_duration(filepath: str) -> float:
    return MP3(filepath).info.length


def speak_text(text: str, avatar_api=None, loop=None) -> None:
    if not CONFIG["use_tts"] or not text:
        return

    # Marcamos que el sistema está ocupado ANTES de lanzar el hilo
    # para asegurar que el micrófono no intente escuchar.
    tts_busy.set()

    def _tts_thread():
        global _current_alias
        lock_held = False

        try:
            # Si ya nos interrumpieron antes de arrancar, no hacemos nada.
            if _tts_interrupted.is_set():
                return

            # Esperamos turno; si nos interrumpen mientras esperamos, salimos.
            acquired = _tts_lock.acquire(timeout=60)
            if not acquired or _tts_interrupted.is_set():
                if acquired:
                    _tts_lock.release()
                return

            lock_held = True

            # ── Generar MP3 con edge-tts ─────────────────────────────────────
            temp_file = os.path.join(
                tempfile.gettempdir(), f"zil_voice_{int(time.time())}.mp3"
            )

            async def generate():
                communicate = edge_tts.Communicate(
                    text,
                    "es-CO-SalomeNeural",
                    rate="15%",
                    pitch="+12Hz",
                )
                await communicate.save(temp_file)

            asyncio.run(generate())

            if not os.path.exists(temp_file) or _tts_interrupted.is_set():
                return

            duration = get_mp3_duration(temp_file)
            print(f"[TTS] Duración real del audio: {duration:.2f}s")

            time.sleep(SYNC_DELAY)

            if _tts_interrupted.is_set():
                return

            if avatar_api and loop:
                start_lip_sync(avatar_api, text, duration, loop)

            # ── Reproducir con MCI ───────────────────────────────────────────
            short_path = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(temp_file, short_path, 260)

            alias = f"zil_audio_{int(time.time())}"
            ctypes.windll.winmm.mciSendStringW(
                f"open {short_path.value} type mpegvideo alias {alias}", None, 0, 0
            )

            with _alias_lock:
                _current_alias = alias

            # Reproducción con polling para poder interrumpir mid-clip
            tts_playing.set()                          # avisa al mic que ZIL está hablando
            ctypes.windll.winmm.mciSendStringW(f"play {alias}", None, 0, 0)

            status_buf = ctypes.create_unicode_buffer(128)
            while True:
                if _tts_interrupted.is_set():
                    ctypes.windll.winmm.mciSendStringW(f"stop {alias}", None, 0, 0)
                    break
                ctypes.windll.winmm.mciSendStringW(
                    f"status {alias} mode", status_buf, 128, 0
                )
                if status_buf.value != "playing":
                    break
                time.sleep(0.05)

            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)
            tts_playing.clear()                        # ZIL terminó de hablar
            with _alias_lock:
                _current_alias = None

        except Exception as e:
            print(f"[Z.I.L] Error en TTS: {e}")
        finally:
            tts_playing.clear()
            tts_busy.clear()
            if lock_held:
                _tts_lock.release()
            try:
                os.remove(temp_file)
            except Exception:
                pass

    threading.Thread(target=_tts_thread, daemon=True).start()