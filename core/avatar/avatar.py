import asyncio
import websockets
import json

class VTubeStudioAPI:
    def __init__(self, host="localhost", port=8001):
        self.uri = f"ws://{host}:{port}"
        self.plugin_name = "Z.I.L Project"
        self.developer = "GAMM"
        self.auth_token = None
        self._is_speaking = False
        self._ws = None
        self._lock = asyncio.Lock()

    async def connect(self):
        self._ws = await websockets.connect(self.uri)
        ok = await self._authenticate_on_socket(self._ws)
        if not ok:
            await self._ws.close()
            self._ws = None
        return ok

    async def disconnect(self):
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _send_raw(self, message_type, data, request_id="ZILRequest"):
        if not self._ws:
            raise RuntimeError("No hay conexión activa.")
        async with self._lock:
            request = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": request_id,
                "messageType": message_type,
                "data": data,
            }
            await self._ws.send(json.dumps(request))
            response = await self._ws.recv()
            return json.loads(response)

    async def _authenticate_on_socket(self, ws):
        req = {
            "apiName": "VTubeStudioPublicAPI", "apiVersion": "1.0",
            "requestID": "AuthRequest",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": self.plugin_name,
                "pluginDeveloper": self.developer,
                "authenticationToken": self.auth_token,
            },
        }
        await ws.send(json.dumps(req))
        data = json.loads(await ws.recv())
        authenticated = data.get("data", {}).get("authenticated", False)
        if not authenticated:
            print("[VTS] Fallo de autenticación. Token inválido?")
        return authenticated

    async def create_custom_parameters(self):
        params = [
            {"parameterName": "ZIL_MouthOpen",  "explanation": "ZIL lip sync - apertura boca", "min": 0,  "max": 1,  "defaultValue": 0.15},
            {"parameterName": "ZIL_MouthSmile", "explanation": "ZIL lip sync - forma boca",    "min": -1, "max": 1,  "defaultValue": -0.5},
            {"parameterName": "ZIL_FaceAngleX", "explanation": "ZIL body tracking - X face",   "min": -30, "max": 30, "defaultValue": 0},
            {"parameterName": "ZIL_FaceAngleY", "explanation": "ZIL body tracking - Y face",   "min": -30, "max": 30, "defaultValue": 0},
            {"parameterName": "ZIL_EyeX",       "explanation": "ZIL body tracking - X eye",    "min": -1, "max": 1,  "defaultValue": 0},
            {"parameterName": "ZIL_EyeY",       "explanation": "ZIL body tracking - Y eye",    "min": -1, "max": 1,  "defaultValue": 0},
        ]
        for p in params:
            resp = await self._send_raw("ParameterCreationRequest", p, "CreateParam")
            err = resp.get("data", {}).get("errorID", 0)
            if err == 0: continue
            else: print(f"[VTS] Error creando '{p['parameterName']}': {resp}")

    async def set_parameters(self, params_dict):
        parameter_values = [{"id": k, "value": v} for k, v in params_dict.items()]
        await self._send_raw(
            "InjectParameterDataRequest",
            {"faceFound": True, "mode": "set", "parameterValues": parameter_values},
        )

if __name__ == "__main__":
    async def get_token():
        vts = VTubeStudioAPI()
        print("\n" + "="*50)
        print("1. Abre VTube Studio.")
        print("2. Ve a Configuración.")
        print("3. Asegúrate de que 'API de VTube Studio' esté ACTIVADO, puerto default 8001")
        print("4. Al ejecutar este script, aparecerá un popup en VTube Studio.")
        print("5. Dale a 'Allow' (Permitir).")
        print("="*50 + "\n")

        try:
            ws = await websockets.connect(vts.uri)
            # Enviar solicitud de token
            req_token = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "TokenRequest",
                "messageType": "AuthenticationTokenRequest",
                "data": {
                    "pluginName": vts.plugin_name,
                    "pluginDeveloper": vts.developer
                }
            }
            await ws.send(json.dumps(req_token))
            response = json.loads(await ws.recv())
            token = response.get("data", {}).get("authenticationToken")

            if token:
                print(f"\n¡ÉXITO! Tu VTUBE_TOKEN es:\n\n{token}\n")
                print("Cópialo y pégalo en tu archivo .env")
            else:
                print("\nNo se recibió token. ¿Aceptaste el popup en VTube Studio?")

            await ws.close()
        except Exception as e:
            print(f"\nError conectando a VTube Studio: {e}")
            print("Asegúrate de que VTube Studio esté abierto y la API activada.")

    asyncio.run(get_token())
