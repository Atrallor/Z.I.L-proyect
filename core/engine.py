import time
import threading
import queue
import random
import asyncio
import os
from core.screenshots import capture_screen
from core.model_analysis import analyze_screen
from core.voice import speak_text, interrupt_tts
from core.avatar import VTubeStudioAPI, start_body_tracking
from core.conversation import ConversationSession
from core.memory import recall

capture_interval = 20

class ZIL:
    def __init__(self):
        self.message_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self._worker_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._loop_thread: threading.Thread | None = None
        self.avatar = VTubeStudioAPI()
        self.avatar.auth_token = os.getenv("VTUBE_TOKEN")
        self.conversation_mode = threading.Event()
        self._last_screen_comment: str | None = None
        self._last_screen_img: bytes | None = None
        self._conv_session: ConversationSession | None = None

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
        print(f"[Z.I.L] Iniciado. Analizando cada {capture_interval}s...")

    def stop(self):
        self.running = False
        self._run(self.avatar.disconnect())
        self._loop.call_soon_threadsafe(self._loop.stop)
        print("[Z.I.L] Detenido.")

    def enter_conversation(self):
        self.conversation_mode.set()
        interrupt_tts()
        self._conv_session = ConversationSession(
            screen_comment=self._last_screen_comment,
            screen_img=self._last_screen_img,
        )
        print("[Z.I.L] Loop de pantalla PAUSADO (modo conversación).")

    def exit_conversation(self):
        from core.voice import _tts_interrupted
        _tts_interrupted.clear()
        if self._conv_session:
            session = self._conv_session
            self._conv_session = None
            threading.Thread(target=session.close, daemon=True).start()

        self.conversation_mode.clear()
        print("[Z.I.L] Loop de pantalla REANUDADO.")

    def handle_voice_input(self, text: str) -> None:
        if self._conv_session:
            self._conv_session.reply(text, self.avatar, self._loop)
        else:
            tmp = ConversationSession()
            tmp.reply(text, self.avatar, self._loop)

    def _analysis_loop(self):
        while self.running:
            try:
                if self.conversation_mode.is_set(): time.sleep(0.5); continue

                if random.random() < 0.3:
                    print("[Z.I.L] Ronda silenciosa...")
                    time.sleep(capture_interval)
                    continue

                print("[Z.I.L] Analizando pantalla...")
                img_bytes = capture_screen()

                if img_bytes is None: time.sleep(capture_interval); continue

                memory_context = ""
                memory_images = []

                try:
                    if self._last_screen_comment: memory_context, memory_images = recall(self._last_screen_comment)
                except Exception as e: print(f"[MEM] recall() falló (no bloqueante): {e}")

                analysis = analyze_screen(img_bytes, memory_context=memory_context, memory_images=memory_images)

                if analysis:
                    comment, emotion = analysis
                    self._last_screen_comment = comment
                    self._last_screen_img = img_bytes
                    self.message_queue.put((comment, emotion))
                    speak_text(comment, self.avatar, self._loop)

                else: print("[Z.I.L] Sin comentario esta vez.")

            except Exception as e: print(f"[Z.I.L] Error en loop: {e}")

            time.sleep(capture_interval)