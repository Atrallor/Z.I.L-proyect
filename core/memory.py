"""
core/memory.py — Memoria semántica de ZIL con ChromaDB + sentence-transformers.

Flujo:
  APRENDER:  (screen_desc + explanation + screenshot) → embedding (CPU) → ChromaDB + .webp
  RECORDAR:  screen_desc actual → embedding (CPU) → buscar top-K similares → texto + imagen

Los embeddings se generan con all-MiniLM-L6-v2 en CPU (~50ms),
sin tocar Ollama ni la GPU donde vive gemma3.

La colección "zil_knowledge_v2" persiste en disco en ./zil_memory_db/
Las imágenes se guardan en ./zil_memory_db/images/ como .webp
"""

import chromadb
import io
import os
import threading
from datetime import datetime
from PIL import Image
from sentence_transformers import SentenceTransformer

# ── Configuración ─────────────────────────────────────────────────────────────
DB_PATH           = os.path.join(os.path.dirname(__file__), "..", "zil_memory_db")
IMAGES_PATH       = os.path.join(DB_PATH, "images")
COLLECTION_NAME   = "zil_knowledge_v2"
SIMILARITY_THRESH = 0.45
TOP_K             = 3

_client: chromadb.PersistentClient | None = None
_collection = None
_lock = threading.Lock()

# ── Modelo de embeddings (carga UNA sola vez, ~30MB en RAM, 0 GPU) ────────────
_st_model: SentenceTransformer | None = None
_st_lock = threading.Lock()


def _get_st_model() -> SentenceTransformer:
    """Singleton: carga all-MiniLM-L6-v2 la primera vez y lo reutiliza siempre."""
    global _st_model
    with _st_lock:
        if _st_model is None:
            print("[MEM] Cargando modelo de embeddings (all-MiniLM-L6-v2, CPU)...")
            _st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            print("[MEM] Modelo de embeddings listo.")
    return _st_model


# ── Inicialización ────────────────────────────────────────────────────────────

def _get_collection():
    global _client, _collection
    with _lock:
        if _collection is None:
            _client = chromadb.PersistentClient(path=DB_PATH)
            _collection = _client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            os.makedirs(IMAGES_PATH, exist_ok=True)
            print(f"[MEM] ChromaDB lista. Entradas: {_collection.count()}")
    return _collection


# ── Embeddings vía sentence-transformers (CPU, ~50ms) ─────────────────────────

def _embed(text: str) -> list[float] | None:
    """Genera un embedding usando all-MiniLM-L6-v2 en CPU. Sin tocar Ollama."""
    if not text:
        return None

    try:
        model = _get_st_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"[MEM] Error al generar embedding: {e}")
        return None


# ── Almacenamiento de imágenes ────────────────────────────────────────────────

def _save_screenshot(doc_id: str, img_bytes: bytes) -> str | None:
    """Guarda screenshot como .webp comprimido. Retorna la ruta o None."""
    try:
        img = Image.open(io.BytesIO(img_bytes))
        # Reducir a 50% para ahorrar disco (~50-80KB por imagen)
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        path = os.path.join(IMAGES_PATH, f"{doc_id}.webp")
        img.save(path, format="WEBP", quality=60)
        print(f"[MEM] Imagen guardada: {os.path.basename(path)} ({os.path.getsize(path) // 1024}KB)")
        return path
    except Exception as e:
        print(f"[MEM] Error guardando imagen: {e}")
        return None


def _load_screenshot(image_path: str) -> bytes | None:
    """Carga una imagen guardada y la retorna como bytes JPEG para Ollama."""
    try:
        if not os.path.exists(image_path):
            return None
        img = Image.open(image_path)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()
    except Exception as e:
        print(f"[MEM] Error cargando imagen: {e}")
        return None


# ── API pública ───────────────────────────────────────────────────────────────

def learn(screen_description: str, zil_question: str, ale_explanation: str,
          screenshot_bytes: bytes | None = None) -> bool:
    """
    Guarda una nueva memoria en ChromaDB, opcionalmente con screenshot.

    Args:
        screen_description: Lo que ZIL dijo/comentó al ver la pantalla.
        zil_question:       La pregunta/observación específica que hizo ZIL.
        ale_explanation:    Lo que Ale le explicó por voz.
        screenshot_bytes:   La imagen que ZIL estaba viendo (se guarda como .webp).
    """
    col = _get_collection()

    combined = (
        f"PANTALLA: {screen_description}\n"
        f"PREGUNTA ZIL: {zil_question}\n"
        f"ALE EXPLICÓ: {ale_explanation}"
    )

    embedding = _embed(combined)
    if embedding is None:
        return False

    doc_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    # Guardar imagen si la hay
    image_path = ""
    if screenshot_bytes:
        saved = _save_screenshot(doc_id, screenshot_bytes)
        if saved:
            image_path = saved

    col.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[combined],
        metadatas=[{
            "timestamp":          datetime.now().isoformat(),
            "screen_description": screen_description,
            "zil_question":       zil_question,
            "ale_explanation":    ale_explanation,
            "image_path":         image_path,
        }],
    )
    img_tag = " (con imagen)" if image_path else ""
    print(f"[MEM] Aprendido{img_tag}: '{ale_explanation[:70]}' (total: {col.count()})")
    return True


def recall(screen_description: str) -> tuple[str, list[bytes]]:
    """
    Busca memorias semánticamente similares a la descripción de pantalla actual.

    Returns:
        (texto_contexto, imagenes) donde:
        - texto_contexto: bloque de texto para inyectar en el system prompt
        - imagenes: lista con máximo 1 imagen (bytes JPEG) de la memoria más relevante
    """
    col = _get_collection()
    if col.count() == 0:
        return "", []

    embedding = _embed(screen_description)
    if embedding is None:
        return "", []

    results = col.query(
        query_embeddings=[embedding],
        n_results=min(TOP_K, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances",  [[]])[0]

    relevant = []
    for meta, dist in zip(metadatas, distances):
        similarity = 1.0 - dist
        if similarity >= SIMILARITY_THRESH:
            relevant.append((similarity, meta))

    if not relevant:
        return "", []

    # Ordenar por relevancia
    relevant.sort(key=lambda x: -x[0])

    # Construir texto de contexto
    lines = [
        "---",
        "## RECUERDOS RELEVANTES (Conocimiento que Ale ya te explicó):\n",
    ]
    for _, meta in relevant:
        lines.append(f"- \"{meta['ale_explanation']}\"")
        lines.append(f"  (lo aprendiste mientras veías: {meta['screen_description'][:100]})")
        lines.append("")
    lines.append("---")

    # Cargar SOLO la imagen de la memoria más relevante (máx velocidad)
    memory_images = []
    top_image_path = relevant[0][1].get("image_path", "")
    if top_image_path:
        img_data = _load_screenshot(top_image_path)
        if img_data:
            memory_images.append(img_data)
            print(f"[MEM] Imagen de memoria cargada para comparación visual.")

    print(f"[MEM] {len(relevant)} memoria(s) relevante(s) inyectada(s).")
    return "\n".join(lines), memory_images


def total_memories() -> int:
    return _get_collection().count()

