import math
import threading
import tkinter as tk
import win32gui
from core.micro_to_text import start_listening_loop

BTN_SIZE = 50
GAP_X    = 4
TRACK_INTERVAL = 16
ANIM_INTERVAL  = 50


class MicButton:

    def __init__(self, engine):
        self.engine = engine
        self.active = False
        self._stop_listen = threading.Event()
        self._listen_thread: threading.Thread | None = None
        self._pulse_phase = 0.0
        self._last_geo: str = ""

        self.root = tk.Tk()
        self.root.overrideredirect(True)                   
        self.root.wm_attributes("-topmost", True)           
        self.root.wm_attributes("-transparentcolor", "#000001")
        self.root.configure(bg="#000001")
        self.root.geometry(f"{BTN_SIZE}x{BTN_SIZE}+0+0")   

        self.canvas = tk.Canvas(
            self.root,
            width=BTN_SIZE,
            height=BTN_SIZE,
            bg="#000001",
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

        self._track_window()
        self._animate()

    def _find_vts_hwnd(self):
        hwnd = win32gui.FindWindow(None, "\u200b")   
        if not hwnd: hwnd = win32gui.FindWindow(None, "VTube Studio")
        return hwnd if hwnd else None

    def _track_window(self):
        hwnd = self._find_vts_hwnd()
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            x = left - BTN_SIZE - GAP_X
            y = bottom - BTN_SIZE
            new_geo = f"{BTN_SIZE}x{BTN_SIZE}+{x}+{y-10}"
            if new_geo != self._last_geo:
                self._last_geo = new_geo
                self.root.geometry(new_geo)
        self.root.after(TRACK_INTERVAL, self._track_window)

    def _animate(self):
        self.canvas.delete("all")

        if self.active:
            self._pulse_phase = (self._pulse_phase + 0.18) % (2 * math.pi)
            pulse = 0.65 + 0.35 * math.sin(self._pulse_phase)

            r = int(180 + 75 * pulse)
            r = min(255, r)
            main_color = f"#{r:02x}1515"
            ring_color = "#ff2222"
            icon_color = "#ffe0e0"
        else:
            main_color = "#2a2a2a"
            ring_color = "#484848"
            icon_color = "#cccccc"

        pad = 4
        self.canvas.create_oval(
            pad, pad, BTN_SIZE - pad, BTN_SIZE - pad,
            fill=ring_color, outline="", width=0,
        )
        inner = pad + 3
        self.canvas.create_oval(
            inner, inner, BTN_SIZE - inner, BTN_SIZE - inner,
            fill=main_color, outline="", width=0,
        )
        self.canvas.create_text(
            BTN_SIZE // 2, BTN_SIZE // 2,
            text="🎤",
            font=("Segoe UI Emoji", 15),
            fill=icon_color,
        )

        self.root.after(ANIM_INTERVAL, self._animate)

    def _on_click(self, _event):
        if not self.active: self._activate()
        else: self._deactivate()

    def _activate(self):
        self.active = True
        self.engine.enter_conversation()
        self._stop_listen.clear()
        self._listen_thread = threading.Thread(
            target=start_listening_loop,
            args=(self._on_voice_input, self._stop_listen),
            daemon=True,
        )
        self._listen_thread.start()
        print("[MIC BTN] Modo conversación ACTIVADO 🎤")

    def _deactivate(self):
        self.active = False
        self._stop_listen.set()
        self.engine.exit_conversation()
        print("[MIC BTN] Modo conversación DESACTIVADO ⏹")

    def _on_voice_input(self, text: str):
        self.engine.handle_voice_input(text)


    def run(self): self.root.mainloop()

def launch_mic_button(engine) -> threading.Thread:
    def _run():
        btn = MicButton(engine)
        btn.run()
    t = threading.Thread(target=_run, daemon=True, name="MicButtonThread")
    t.start()
    return t
