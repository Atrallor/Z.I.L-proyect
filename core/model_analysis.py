import base64
import httpx
from core.config import CONFIG, SYSTEM_PROMPT, USER_PROMPT

_client = httpx.Client(timeout=120.0)

def analyze_screen(img_bytes: bytes, memory_context: str = "", memory_images: list[bytes] | None = None) -> tuple[str, str] | None:
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    effective_system = SYSTEM_PROMPT
    if memory_context: effective_system = SYSTEM_PROMPT + "\n\n" + memory_context
    images = [img_b64]
    effective_user_prompt = USER_PROMPT

    if memory_images:
        for mem_img in memory_images:images.append(base64.b64encode(mem_img).decode("utf-8"))
        effective_user_prompt = (
            USER_PROMPT + "\n\n"
            "NOTA: La primera imagen es lo que ves AHORA. "
            "La segunda imagen es de algo que viste antes y sobre lo cual Ale te explicó. "
            "Si notas relación, intégralo de forma natural en tu comentario, "
            "como si simplemente lo supieras."
        )

    payload = {
        "model": CONFIG["model"],
        "messages": [
            {"role": "system", "content": effective_system},
            {"role": "user", "content": effective_user_prompt, "images": images},
        ],
        "stream": False,
        "options": {
            "temperature": CONFIG["temperature"],
            "num_predict": CONFIG["max_tokens"],
        },
    }

    try:
        resp = _client.post("http://localhost:11434/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "").strip()

        print(f"[Z.I.L] Respuesta: {repr(text)}")

        if "[SILENCIO]" in text or not text:
            return None

        emotion = "FELIZ"
        clean_text = text
        if text.startswith("[") and "]" in text:
            try:
                emotion    = text[text.find("[") + 1 : text.find("]")]
                clean_text = text[text.find("]")+1:].strip()
            except Exception: pass

        if len(clean_text) < 8: return None
        return clean_text, emotion

    except Exception as e:
        print(f"[Z.I.L] Error al consultar Ollama: {e}")
        return None
