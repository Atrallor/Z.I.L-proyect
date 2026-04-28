import io
import mss
import mss.tools
from PIL import Image

def capture_screen() -> bytes | None:
    try:
        with mss.MSS() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)

        img = Image.frombytes(
            "RGB",
            (screenshot.width, screenshot.height),
            screenshot.bgra,
            "raw",
            "BGRX"
        )

        print(f"[Z.I.L] Screenshot capturado")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    except Exception as e:
        print(f"[Z.I.L] Error capturando pantalla: {e}")
        return None
