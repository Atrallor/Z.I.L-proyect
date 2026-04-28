import base64
import httpx
from core.config import CONFIG, SYSTEM_PROMPT, USER_PROMPT

def analyze_screen(img_bytes: bytes) -> tuple[str, str] | None:
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    payload = {
        "model": CONFIG["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT, "images": [img_b64]}
        ],
        "stream": False,
        "options": {
            "temperature": CONFIG["temperature"],
            "num_predict": CONFIG["max_tokens"],
        },
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post("http://localhost:11434/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "").strip()

        print(f"[Z.I.L] Respuesta raw: {repr(text[:100])}")

        if text:
            printable = sum(1 for c in text if c.isprintable())
            if printable / len(text) < 0.75:
                print("[Z.I.L] Respuesta corrupta descartada.")
                return None

        if "[SILENCIO]" in text or not text:
            return None
        
        # Parsear emoción: [EMOCION] Texto
        emotion = "FELIZ" # Default
        clean_text = text
        if text.startswith("[") and "]" in text:
            try:
                emotion = text[text.find("[")+1:text.find("]")]
                clean_text = text[text.find("]")+1:].strip()
            except:
                pass

        if len(clean_text) < 8:
            return None

        return clean_text, emotion

    except httpx.HTTPStatusError as e:
        print(f"[Z.I.L] HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[Z.I.L] Error al consultar Ollama: {e}")
        return None
