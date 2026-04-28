import time
import threading
import queue
import random
import asyncio
from core.config import CONFIG
from core.screenshots import capture_screen
from core.model_analysis import analyze_screen
from core.voice import speak_text
from core.avatar import VTubeStudioAPI, start_body_tracking

class ZIL:
    def __init__(self):
        self.message_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self._worker_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._loop_thread: threading.Thread | None = None
        self.avatar = VTubeStudioAPI()
        self.avatar.auth_token = CONFIG["vtube_token"]

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def start(self):
        self.running = True

        self._loop_thread = threading.Thread(target=self._start_loop, daemon=True)
        self._loop_thread.start()

        connected = self._run(self.avatar.connect())
        if connected:
            print("[VTS] Avatar conectado y activo.")
            start_body_tracking(self.avatar, self._loop)
        else:
            print("[VTS] No se pudo conectar el avatar.")

        self._worker_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._worker_thread.start()
        print(f"[Z.I.L] Iniciado. Analizando cada {CONFIG['capture_interval']}s...")

    def stop(self):
        self.running = False
        self._run(self.avatar.disconnect())
        self._loop.call_soon_threadsafe(self._loop.stop)
        print("[Z.I.L] Detenido.")

    def _analysis_loop(self):

        while self.running:
            try:
                if random.random() < CONFIG["silence_threshold"]:
                    print("[Z.I.L] Ronda silenciosa...")
                    time.sleep(CONFIG["capture_interval"])
                    continue

                print("[Z.I.L] Analizando pantalla...")
                img_bytes = capture_screen()

                if img_bytes is None:
                    time.sleep(CONFIG["capture_interval"])
                    continue

                analysis = analyze_screen(img_bytes)

                if analysis:
                    comment, emotion = analysis
                    self.message_queue.put((comment, emotion))
                    speak_text(comment, self.avatar, self._loop)

                else:
                    print("[Z.I.L] Sin comentario esta vez.")

            except Exception as e:
                print(f"[Z.I.L] Error en loop: {e}")

            time.sleep(CONFIG["capture_interval"])