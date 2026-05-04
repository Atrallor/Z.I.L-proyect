import sys
import asyncio
import threading
import queue
import time
from dotenv import load_dotenv
from core.engine import ZIL
from interface.avatarLoader import set_vtube_always_on_top, launch_vtube_if_closed, close_vtube_studio
from interface.mic_button import launch_mic_button

load_dotenv()

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def main():
    print("=" * 55 + "\nZ.I.L – Activada\n" + "=" * 55)

    launch_vtube_if_closed()
    zil = ZIL()

    async def setup_vts():
        if await zil.avatar.connect():
            await zil.avatar.create_custom_parameters()
            print("[VTS] Parámetros custom listos.")
            await zil.avatar.disconnect()
        else:
            print("[VTS] No se pudo conectar con VTube Studio.")

    asyncio.run(setup_vts())

    zil.start()

    set_vtube_always_on_top(500, 500, 250, 450)
    launch_mic_button(zil)

    print("Tip: Ctrl+C para salir.\n")

    def poll_queue():
        while zil.running:
            try:
                msg = zil.message_queue.get(timeout=1)
                if isinstance(msg, tuple):
                    comment, emotion = msg
                else:
                    print(f"[Z.I.L] {msg}")
            except queue.Empty:
                continue

    queue_thread = threading.Thread(target=poll_queue, daemon=True)
    queue_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Z.I.L] Cerrando...")
        zil.stop()
        close_vtube_studio()

if __name__ == "__main__":
    main()