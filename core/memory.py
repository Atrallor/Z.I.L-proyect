import chromadb
import io
import os
import threading
from datetime import datetime
from PIL import Image
from sentence_transformers import SentenceTransformer

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "zil_memory_db")
IMAGES_PATH = os.path.join(DB_PATH, "images")
COLLECTION_NAME = "zil_knowledge_v2"
SIMILARITY_THRESH = 0.45
TOP_K = 3

_client: chromadb.PersistentClient | None = None
_collection = None
_lock = threading.Lock()
_st_model: SentenceTransformer | None = None
_st_lock = threading.Lock()


def _get_st_model() -> SentenceTransformer:
    global _st_model
    with _st_lock:
        if _st_model is None: _st_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _st_model

def _get_collection():
    global _client, _collection
    with _lock:
        if _collection is None:
            _client = chromadb.PersistentClient(path=DB_PATH)
            _collection = _client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
            os.makedirs(IMAGES_PATH, exist_ok=True)
            print(f"[MEM] ChromaDB lista. Entradas: {_collection.count()}")
    return _collection


def _embed(text: str) -> list[float] | None:
    if not text: return None

    try:
        model = _get_st_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e: print(f"[MEM] Error al generar embedding: {e}"); return None

def _save_screenshot(doc_id: str, img_bytes: bytes) -> str | None:
    try:
        img = Image.open(io.BytesIO(img_bytes))
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        path = os.path.join(IMAGES_PATH, f"{doc_id}.webp")
        img.save(path, format="WEBP", quality=60)
        print(f"[MEM] Imagen guardada: {os.path.basename(path)} ({os.path.getsize(path) // 1024}KB)")
        return path
    except Exception as e: print(f"[MEM] Error guardando imagen: {e}");return None


def _load_screenshot(image_path: str) -> bytes | None:
    try:
        if not os.path.exists(image_path): return None
        img = Image.open(image_path)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()
    except Exception as e: print(f"[MEM] Error cargando imagen: {e}"); return None

def learn(screen_description: str, zil_question: str, ale_explanation: str,screenshot_bytes: bytes | None = None) -> bool:

    col = _get_collection()
    combined = (
        f"PANTALLA: {screen_description}\n"
        f"PREGUNTA ZIL: {zil_question}\n"
        f"ALE EXPLICÓ: {ale_explanation}"
    )

    embedding = _embed(combined)
    if embedding is None: return False
    doc_id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    image_path = ""
    if screenshot_bytes:
        saved = _save_screenshot(doc_id, screenshot_bytes)
        if saved: image_path = saved

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
    col = _get_collection()
    if col.count() == 0: return "", []
    embedding = _embed(screen_description)
    if embedding is None: return "", []

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
        if similarity >= SIMILARITY_THRESH: relevant.append((similarity, meta))

    if not relevant: return "", []
    relevant.sort(key=lambda x: -x[0])
    lines = [
        "---",
        "## RECUERDOS RELEVANTES (Conocimiento que Ale ya te explicó):\n",
    ]
    for _, meta in relevant:
        lines.append(f"- \"{meta['ale_explanation']}\"")
        lines.append(f"  (lo aprendiste mientras veías: {meta['screen_description'][:100]})")
        lines.append("")
    lines.append("---")

    memory_images = []
    top_image_path = relevant[0][1].get("image_path", "")
    if top_image_path:
        img_data = _load_screenshot(top_image_path)
        if img_data:
            memory_images.append(img_data)
            print(f"[MEM] Imagen de memoria cargada para comparación visual.")

    print(f"[MEM] {len(relevant)} memoria(s) relevante(s) inyectada(s).")
    return "\n".join(lines), memory_images


def total_memories() -> int: return _get_collection().count()

