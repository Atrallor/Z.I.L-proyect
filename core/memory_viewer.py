import sys
import os
from pathlib import Path

# Añadir el directorio actual al path para poder importar core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from core.memory import _get_collection
    
    def view_memory():
        col = _get_collection()
        count = col.count()
        print("=" * 60)
        print(f"ESTADO DE LA MEMORIA SEMÁNTICA DE Z.I.L")
        print(f"Total de memorias guardadas: {count}")
        print("=" * 60)
        
        if count > 0:
            results = col.get(include=['metadatas', 'documents'])
            for i, (meta, doc) in enumerate(zip(results['metadatas'], results['documents'])):
                timestamp = meta.get('timestamp', 'Sin fecha')[:16].replace('T', ' ')
                image_path = meta.get('image_path', '')
                print(f"\n[Memoria #{i+1}] - {timestamp}")
                print(f"  Visual: {meta.get('screen_description', '')[:100]}...")
                print(f"  ZIL pregunto: {meta.get('zil_question', '')[:100]}...")
                print(f"  Ale explico: {meta.get('ale_explanation', '')}")
                if image_path and os.path.exists(image_path):
                    print(f"  Imagen: {Path(image_path).resolve().as_uri()}")
                else:
                    print(f"  Imagen: Sin imagen")
                print("-" * 40)
        else:
            print("\nLa base de datos está vacía. Z.I.L aún no ha 'aprendido' nada.")
            print("Para que aprenda, activa el micrófono y explícale algo sobre lo que ella vea.")
            
        print("\n" + "=" * 60)

    if __name__ == "__main__":
        view_memory()

except Exception as e:
    print(f"Error al acceder a la memoria: {e}")
