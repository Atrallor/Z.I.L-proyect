import win32gui
import win32con
import subprocess
import time
import psutil

VTS_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\VTube Studio\VTube Studio.exe"

def is_vtube_running():
    """Detecta por proceso, no por título de ventana."""
    for proc in psutil.process_iter(['name']):
        if 'VTube Studio' in proc.info['name']:
            return True
    return False

def launch_vtube_if_closed():
    if not is_vtube_running():
        print("[VTS] VTube Studio cerrado, abriendo...")
        subprocess.Popen(VTS_PATH)
        print("[VTS] Esperando que cargue (20s)...")
        time.sleep(20)
        print("[VTS] Listo.")
    else:
        print("[VTS] VTube Studio ya está corriendo.")

def set_vtube_always_on_top(x, y, width, height):
    hwnds = []
    def callback(hwnd, _):
        if "VTube Studio" in win32gui.GetWindowText(hwnd):
            hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)
    for hwnd in hwnds:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~win32con.WS_CAPTION
        style &= ~win32con.WS_MINIMIZEBOX
        style &= ~win32con.WS_MAXIMIZEBOX
        style &= ~win32con.WS_SYSMENU
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST,
            x, y, width, height,
            win32con.SWP_FRAMECHANGED
        )
        print(f"[VTS] Ventana posicionada en ({x}, {y}) tamaño {width}x{height}.")