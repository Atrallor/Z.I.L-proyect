"""
core/conversation.py — Conversación directa con ZIL por voz.

Mantiene el historial completo del hilo y realiza búsquedas semánticas
en cada turno para que ZIL siempre pueda recordar lo que Ale le ha enseñado.
"""

import httpx
from core.config import CONFIG
from core.voice import speak_text

CONVERSATION_SYSTEM_PROMPT = """Eres ZIL, una mujer colombiana de clase media-alta. Natural, fresca, relajada, sin exagerar acento.

Ale te está hablando DIRECTAMENTE por voz. 
Respóndele como en una conversación cara a cara.

---

CONTEXTO DE MEMORIA:
Tienes acceso a recuerdos de cosas que Ale te ha explicado antes. 
Si Ale te pregunta algo que ya te explicó, o si la conversación toca temas que ya conoces por explicaciones previas, USA esa información como si fuera conocimiento propio. 
NO digas "según mis registros" ni "recuerdo que me dijiste", simplemente intégralo en tu respuesta de forma natural.

---

FORMATO (OBLIGATORIO):
[EMOCION] Respuesta

EMOCIONES: FELIZ, ENOJADA, SORPRENDIDA, TRISTE, PENSATIVA, GRACIOSA

---

REGLAS:
- Máx 2 oraciones cortas y naturales.
- Coloquial, colombiana, directa.
- Si Ale te explica algo nuevo, acéptalo y agradécele o comenta algo al respecto.
- NO suenes como asistente virtual.
"""

EXTRACT_FACT_PROMPT = """De esta conversación entre ZIL y Ale, extrae en UNA sola oración concisa
el conocimiento factual que Ale le explicó a ZIL (qué es la cosa, cómo funciona, etc.).
Solo la información objetiva, sin diálogo. Si no hay nada nuevo que aprender, responde: NADA.

Conversación:
{history}

Extracción (1 oración o NADA):"""


_client = httpx.Client(timeout=60.0)

def _parse_response(raw: str) -> tuple[str, str] | None:
    if not raw: return None
    emotion = "FELIZ"
    clean = raw
    if raw.startswith("[") and "]" in raw:
        try:
            emotion = raw[raw.find("[") + 1 : raw.find("]")]
            clean = raw[raw.find("]") + 1 :].strip()
        except Exception: pass
    return (clean, emotion) if len(clean) >= 3 else None


def _extract_learned_fact(history: list[dict]) -> str | None:
    if not history: return None
    conv_text = "\n".join(f"{'ZIL' if m['role'] == 'assistant' else 'Ale'}: {m['content']}" for m in history)
    prompt = EXTRACT_FACT_PROMPT.format(history=conv_text)
    try:
        payload = {
            "model": CONFIG["model"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 100},
        }
        resp = _client.post("http://localhost:11434/api/chat", json=payload)
        resp.raise_for_status()
        fact = resp.json().get("message", {}).get("content", "").strip()
        if fact.upper() == "NADA" or not fact or len(fact) < 10: return None
        return fact
    except Exception as e:
        print(f"[MEM] Error al extraer hecho: {e}")
        return None


class ConversationSession:
    def __init__(self, screen_comment: str | None = None, screen_img: bytes | None = None):
        self.screen_comment = screen_comment or ""
        self.screen_img = screen_img
        self.history: list[dict] = []
        self.memories_found: set[str] = set() # Para no repetir memorias inyectadas

        if screen_comment:
            self.history.append({"role": "assistant", "content": screen_comment})
            print(f"[CONV] Sesión iniciada con contexto visual.")

    def reply(self, user_text: str, avatar=None, loop=None) -> None:
        if not user_text: return

        # ── BÚSQUEDA DINÁMICA EN MEMORIA ──
        # Buscamos memorias relevantes para lo que Ale acaba de decir
        current_memories = ""
        try:
            from core.memory import recall
            # Buscamos tanto por el comentario de pantalla como por lo que dice Ale
            search_query = f"{self.screen_comment} {user_text}"
            current_memories, _ = recall(search_query)  # solo texto, sin imágenes
        except Exception as e:
            print(f"[CONV] Error en recall: {e}")

        # Construir el prompt del sistema con las memorias inyectadas
        full_system_prompt = CONVERSATION_SYSTEM_PROMPT
        if current_memories:
            full_system_prompt += f"\n\nRECUERDOS RELEVANTES:\n{current_memories}"

        messages = [{"role": "system", "content": full_system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_text})

        try:
            payload = {
                "model": CONFIG["model"],
                "messages": messages,
                "stream": False,
                "options": {"temperature": CONFIG["temperature"], "num_predict": 150},
            }
            resp = _client.post("http://localhost:11434/api/chat", json=payload)
            resp.raise_for_status()

            raw = resp.json().get("message", {}).get("content", "").strip()
            parsed = _parse_response(raw)
            if not parsed: return

            clean_text, emotion = parsed
            
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": clean_text})

            from core.voice import _tts_interrupted
            _tts_interrupted.clear()
            speak_text(clean_text, avatar, loop)

        except Exception as e:
            print(f"[ZIL Conv] Error: {e}")

    def close(self) -> None:
        if len(self.history) <= 1: return # Solo el seed de pantalla

        print("[CONV] Analizando qué aprendí en esta charla...")
        learned_fact = _extract_learned_fact(self.history)

        if learned_fact:
            from core.memory import learn
            learn(
                screen_description=self.screen_comment,
                zil_question=self.screen_comment,
                ale_explanation=learned_fact,
                screenshot_bytes=self.screen_img,
            )
