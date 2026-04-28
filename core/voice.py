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

def get_mp3_duration(filepath):
    audio = MP3(filepath)
    return audio.info.length


def speak_text(text: str, avatar_api=None, loop=None):
    if not CONFIG["use_tts"] or not text:
        return

    def _tts_thread():
        try:
            temp_file = os.path.join(tempfile.gettempdir(), f"zil_voice_{int(time.time())}.mp3")

            async def generate():
                communicate = edge_tts.Communicate(
                    text,
                    CONFIG["voice"],
                    rate=CONFIG["voice_rate"],
                    pitch=CONFIG["voice_pitch"]
                )
                await communicate.save(temp_file)

            asyncio.run(generate())

            if not os.path.exists(temp_file):
                return

            duration = get_mp3_duration(temp_file)
            print(f"[TTS] Duración real del audio: {duration:.2f}s")

            time.sleep(SYNC_DELAY)

            if avatar_api and loop:
                start_lip_sync(avatar_api, text, duration, loop)

            short_path = ctypes.create_unicode_buffer(260)
            ctypes.windll.kernel32.GetShortPathNameW(temp_file, short_path, 260)

            alias = f"zil_audio_{int(time.time())}"
            ctypes.windll.winmm.mciSendStringW(f"open {short_path.value} type mpegvideo alias {alias}", None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)

            try:
                os.remove(temp_file)
            except:
                pass

        except Exception as e:
            print(f"[Z.I.L] Error en TTS: {e}")

    threading.Thread(target=_tts_thread, daemon=True).start()