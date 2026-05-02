import numpy as np
import sounddevice as sd
import whisper
import threading
import time as _time

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.008   # amplitud media mínima para considerar voz (bajado para no cortar tan rápido)
SILENCE_DURATION  = 2     # Aumentado: segundos de silencio para cortar (evita corte prematuro)
MAX_DURATION      = 25.0    # máximo de grabación por turno (seg)
CHUNK_DURATION    = 0.1     # duración de cada chunk de audio (seg)

_model: whisper.Whisper | None = None
_model_lock = threading.Lock()


def _get_model() -> whisper.Whisper:
    """Carga el modelo Whisper 'tiny' una sola vez (singleton)."""
    global _model
    with _model_lock:
        if _model is None:
            print("[MIC] Cargando modelo Whisper (base)...")
            _model = whisper.load_model("base")
            print("[MIC] Modelo Whisper listo.")
    return _model


def listen_once() -> str | None:
    # Importación diferida para evitar importación circular
    from core.voice import tts_playing, tts_busy

    # Esperar si ZIL está ocupada procesando o hablando
    while tts_busy.is_set():
        _time.sleep(0.1)

    model = _get_model()

    print("[MIC] Escuchando...")
    chunks: list[np.ndarray] = []
    silence_count   = 0
    speech_detected = False
    max_chunks     = int(MAX_DURATION   / CHUNK_DURATION)
    silence_limit  = int(SILENCE_DURATION / CHUNK_DURATION)
    chunk_frames   = int(SAMPLE_RATE * CHUNK_DURATION)

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_frames)

                # Si ZIL está hablando por los altavoces, descartar todo el audio
                # capturado para evitar que se escuche a sí misma.
                if tts_playing.is_set():
                    chunks.clear()
                    speech_detected = False
                    silence_count   = 0
                    continue

                amplitude = float(np.abs(chunk).mean())

                if amplitude > SILENCE_THRESHOLD:
                    speech_detected = True
                    silence_count = 0
                    chunks.append(chunk.copy())
                elif speech_detected:
                    silence_count += 1
                    chunks.append(chunk.copy())
                if silence_count >= silence_limit:
                    break
                
    except Exception as e:
        print(f"[MIC] Error de audio: {e}")
        return None

    if not speech_detected or not chunks:
        return None

    audio = np.concatenate(chunks, axis=0).squeeze().astype(np.float32)
    print("[MIC] Transcribiendo...")

    try:
        result = model.transcribe(audio, language="es", fp16=False)
        text = result.get("text", "").strip()
        print(f"[MIC] Transcrito: {repr(text)}")
        
        # ── BLOQUEO POST-RESPUESTA ───────────────────────────────────────────
        # Antes de devolver el texto (lo que disparará la respuesta de ZIL), 
        # nos aseguramos de que cualquier audio previo haya terminado y 
        # damos un margen para que el nuevo audio empiece y bloquee el flag.
        _time.sleep(0.5) 
        while tts_playing.is_set():
            _time.sleep(0.2)

        return text if len(text) > 2 else None
    except Exception as e:
        print(f"[MIC] Error al transcribir: {e}")
        return None


def start_listening_loop(callback, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        text = listen_once()
        if text and not stop_event.is_set():
            callback(text)
