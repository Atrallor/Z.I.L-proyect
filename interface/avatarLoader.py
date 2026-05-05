import win32gui
import win32con
import subprocess
import time
import psutil
import ctypes

VTS_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\VTube Studio\VTube Studio.exe"

def is_vtube_running():
    for proc in psutil.process_iter(['name']):
        if 'VTube Studio' in proc.info['name']: return True
    return False

def launch_vtube_if_closed():
    if not is_vtube_running():
        print("[VTS] VTube Studio cerrado, abriendo...")
        subprocess.Popen(VTS_PATH)
        print("[VTS] Esperando que cargue (30s)...")
        time.sleep(30)
        print("[VTS] Listo.")
    else: print("[VTS] VTube Studio ya está corriendo.")

def close_vtube_studio():
    print("[VTS] Cerrando VTube Studio...")
    closed = False
    for proc in psutil.process_iter(['name']):
        if 'VTube Studio' in proc.info['name']:
            try:
                proc.terminate()
                proc.wait(timeout=3)
                closed = True
            except psutil.NoSuchProcess: pass
            except psutil.TimeoutExpired: proc.kill(); closed = True
    if closed: print("[VTS] VTube Studio cerrado.")
    else: print("[VTS] VTube Studio no estaba abierto.")

def set_vtube_always_on_top(x, y, width, height):
    hwnds = []
    def callback(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if "VTube Studio" in title or title == "\u200b": hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)
    for hwnd in hwnds:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~win32con.WS_MINIMIZEBOX
        style &= ~win32con.WS_MAXIMIZEBOX
        style &= ~win32con.WS_SYSMENU
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.SetWindowText(hwnd, "\u200b")

        try:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_dark_mode = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(set_dark_mode), ctypes.sizeof(set_dark_mode))
        except Exception: pass
        try:
            DWMWA_CAPTION_COLOR = 35
            dark_gray = ctypes.c_int(0x00282828)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(dark_gray), ctypes.sizeof(dark_gray))
        except Exception: pass
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,x, y, width, height, win32con.SWP_FRAMECHANGED)
        print(f"[VTS] Ventana posicionada en ({x}, {y}) tamaño {width}x{height}.")