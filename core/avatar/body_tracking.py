import win32gui
import win32api
import asyncio
import time

async def body_tracking_loop(vts_api):
    screen_width = win32api.GetSystemMetrics(0)
    screen_height = win32api.GetSystemMetrics(1)

    while True:
        try:
            # Check if API is connected
            if not vts_api._ws:
                await asyncio.sleep(1)
                continue

            hwnd = win32gui.FindWindow(None, "\u200b")
            if not hwnd:
                hwnd = win32gui.FindWindow(None, "VTube Studio")
                
            if not hwnd:
                await asyncio.sleep(1)
                continue

            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2

            cursor_x, cursor_y = win32gui.GetCursorPos()

            dx = cursor_x - center_x
            dy = cursor_y - center_y

            # X calculations
            if dx < 0:
                ratio_x = dx / center_x if center_x > 0 else 0
            else:
                dist_right = screen_width - center_x
                ratio_x = dx / dist_right if dist_right > 0 else 0

            ratio_x = max(-1.0, min(1.0, ratio_x))
            
            face_angle_x = ratio_x * 30
            eye_x = -ratio_x * 1  # Invertido el eje X de los ojos

            # Y calculations
            if dy < 0:
                ratio_y = -dy / center_y if center_y > 0 else 0
            else:
                dist_bottom = screen_height - center_y
                ratio_y = -dy / dist_bottom if dist_bottom > 0 else 0

            # Limitamos el mínimo para que nunca llegue completamente a mirar hacia abajo
            ratio_y = max(-0.5, min(1.0, ratio_y))

            face_angle_y = ratio_y * 30
            eye_y = ratio_y * 1

            params = {
                "ZIL_FaceAngleX": round(face_angle_x, 2),
                "ZIL_FaceAngleY": round(face_angle_y, 2),
                "ZIL_EyeX": round(eye_x, 2),
                "ZIL_EyeY": round(eye_y, 2),
            }

            await vts_api.set_parameters(params)
            
        except Exception as e:
            # Suppress noisy errors if connection drops temporarily
            pass
        
        await asyncio.sleep(0.05)

def start_body_tracking(vts_api, loop):
    asyncio.run_coroutine_threadsafe(body_tracking_loop(vts_api), loop)
