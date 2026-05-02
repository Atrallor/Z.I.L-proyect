import math
import threading
import tkinter as tk
import win32gui

from core.micro_to_text import start_listening_loop

# ── Tamaño y offset del botón respecto a la esquina inferior-izquierda de VTS ──
BTN_SIZE = 50
# El botón queda a la IZQUIERDA de la ventana, alineado con su borde inferior
GAP_X    = 4    # px de separación entre el borde izquierdo de VTS y el botón

# Frecuencia del loop de seguimiento (ms) — 16 ms ≈ 60 fps, movimiento imperceptible
TRACK_INTERVAL = 16
# Frecuencia del loop de animación (ms)
ANIM_INTERVAL  = 50


class MicButton:
    """
    Ventana Tkinter flotante sin bordes que se ancla a la esquina
    inferior-izquierda de la ventana de VTube Studio y la sigue si se mueve.

    Al hacer clic activa/desactiva el modo conversación del engine:
      - Pausa el loop de análisis de pantalla (engine.enter_conversation)
      - Inicia un thread de escucha continua con Whisper
      - Cada fragmento de voz se envía a engine.handle_voice_input(text)
    """

    def __init__(self, engine):
        self.engine = engine
        self.active = False
        self._stop_listen = threading.Event()
        self._listen_thread: threading.Thread | None = None
        self._pulse_phase = 0.0
        self._last_geo: str = ""   # cache para evitar llamadas redundantes a geometry()

        # ── Ventana Tkinter ──────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.overrideredirect(True)                    # sin bordes ni barra de título
        self.root.wm_attributes("-topmost", True)           # siempre encima
        self.root.wm_attributes("-alpha", 0.92)             # ligera transparencia
        self.root.configure(bg="#111111")
        self.root.geometry(f"{BTN_SIZE}x{BTN_SIZE}+0+0")   # posición inicial cualquiera

        # ── Canvas (dibujo del botón) ────────────────────────────────────────
        self.canvas = tk.Canvas(
            self.root,
            width=BTN_SIZE,
            height=BTN_SIZE,
            bg="#111111",
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

        # ── Arrancar loops ───────────────────────────────────────────────────
        self._track_window()
        self._animate()

    # ── Seguimiento de ventana ───────────────────────────────────────────────

    def _find_vts_hwnd(self):
        """Busca el hwnd de VTube Studio igual que body_tracking.py."""
        hwnd = win32gui.FindWindow(None, "\u200b")   # título invisible que le asigna avatarLoader
        if not hwnd:
            hwnd = win32gui.FindWindow(None, "VTube Studio")
        return hwnd if hwnd else None

    def _track_window(self):
        """Reposiciona el botón pegado a la esquina inferior-izquierda de VTS.
        Se corre cada 16 ms para que el movimiento se vea como si el botón
        fuera parte de la ventana.
        """
        hwnd = self._find_vts_hwnd()
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            # Botón a la IZQUIERDA del borde izquierdo, alineado con el borde inferior
            x = left - BTN_SIZE - GAP_X
            y = bottom - BTN_SIZE
            new_geo = f"{BTN_SIZE}x{BTN_SIZE}+{x}+{y}"
            if new_geo != self._last_geo:        # sólo actualizar si cambió
                self._last_geo = new_geo
                self.root.geometry(new_geo)
        self.root.after(TRACK_INTERVAL, self._track_window)

    # ── Animación del botón ──────────────────────────────────────────────────

    def _animate(self):
        """Redibuja el botón en cada frame; aplica pulso rojo cuando está activo."""
        self.canvas.delete("all")

        if self.active:
            self._pulse_phase = (self._pulse_phase + 0.18) % (2 * math.pi)
            pulse = 0.65 + 0.35 * math.sin(self._pulse_phase)

            # Color rojo pulsante
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
        # Anillo exterior (brillo/sombra)
        self.canvas.create_oval(
            pad, pad, BTN_SIZE - pad, BTN_SIZE - pad,
            fill=ring_color, outline="", width=0,
        )
        # Círculo principal
        inner = pad + 3
        self.canvas.create_oval(
            inner, inner, BTN_SIZE - inner, BTN_SIZE - inner,
            fill=main_color, outline="", width=0,
        )
        # Ícono micrófono
        self.canvas.create_text(
            BTN_SIZE // 2, BTN_SIZE // 2,
            text="🎤",
            font=("Segoe UI Emoji", 15),
            fill=icon_color,
        )

        self.root.after(ANIM_INTERVAL, self._animate)

    # ── Interacción ──────────────────────────────────────────────────────────

    def _on_click(self, _event):
        if not self.active:
            self._activate()
        else:
            self._deactivate()

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

    # ── Arranque ─────────────────────────────────────────────────────────────

    def run(self):
        """Bloquea hasta que se cierre la ventana (llamar desde un thread separado)."""
        self.root.mainloop()


# ── Función de lanzamiento ───────────────────────────────────────────────────

def launch_mic_button(engine) -> threading.Thread:
    """
    Lanza el botón flotante en un thread daemon separado.
    Retorna el thread por si se necesita hacer join.
    """
    def _run():
        btn = MicButton(engine)
        btn.run()

    t = threading.Thread(target=_run, daemon=True, name="MicButtonThread")
    t.start()
    return t
