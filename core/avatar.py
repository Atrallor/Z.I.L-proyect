import asyncio
import websockets
import json
import time

PARAM_MOUTH_OPEN  = "ZIL_MouthOpen"
PARAM_MOUTH_SMILE = "ZIL_MouthSmile"

VOWELS = set('aáeéiíoóuúü')
PUNCTUATION_SHORT = set(',;')
PUNCTUATION_LONG  = set('.!?…')

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
            {"parameterName": PARAM_MOUTH_OPEN,  "explanation": "ZIL lip sync - apertura boca", "min": 0,  "max": 1,  "defaultValue": 0},
            {"parameterName": PARAM_MOUTH_SMILE, "explanation": "ZIL lip sync - forma boca",    "min": -1, "max": 1,  "defaultValue": 0},
        ]
        for p in params:
            resp = await self._send_raw("ParameterCreationRequest", p, "CreateParam")
            err = resp.get("data", {}).get("errorID", 0)
            if err == 0:
                print(f"[VTS] Parámetro '{p['parameterName']}' creado.")
            elif err == 159:
                print(f"[VTS] Parámetro '{p['parameterName']}' ya existía.")
            else:
                print(f"[VTS] Error creando '{p['parameterName']}': {resp}")

    async def set_parameters(self, params_dict):
        parameter_values = [{"id": k, "value": v} for k, v in params_dict.items()]
        await self._send_raw(
            "InjectParameterDataRequest",
            {"faceFound": True, "mode": "set", "parameterValues": parameter_values},
        )

    async def _lerp_to(self, target_open, target_smile, current, steps=6, interval=0.03):
        cur_open, cur_smile = current
        for _ in range(steps):
            cur_open  += (target_open  - cur_open)  * 0.5
            cur_smile += (target_smile - cur_smile) * 0.5
            await self.set_parameters({
                PARAM_MOUTH_OPEN:  round(cur_open,  3),
                PARAM_MOUTH_SMILE: round(cur_smile, 3),
            })
            await asyncio.sleep(interval)
        return (cur_open, cur_smile)

    async def lip_sync_sim(self, text, duration):
        if self._is_speaking:
            return
        self._is_speaking = True

        VOWEL_MAP = {
            'a': (0.5,   1.0), 'á': (0.5,   1.0),
            'e': (0.35,  0.35),'é': (0.35,  0.35),
            'i': (0.35,  0.65),'í': (0.35,  0.65),
            'o': (1.0,  -1.0), 'ó': (1.0,  -1.0),
            'u': (0.65, -1.0), 'ú': (0.65, -1.0), 'ü': (0.65, -1.0),
            's': (0.18,  1.0),
        }
        REST        = (0.15, -0.5)
        PAUSE_SHORT = (0.15, -0.5)
        PAUSE_LONG  = (0.15, -0.5)

        events = []
        for c in text.lower():
            if c in VOWELS or c == 's':
                events.append(('vowel', c))
            elif c == ' ':
                events.append(('space', ' '))
            elif c in PUNCTUATION_SHORT:
                events.append(('pause_short', c))
            elif c in PUNCTUATION_LONG:
                events.append(('pause_long', c))

        if not events:
            events = [('vowel', 'a')] * 5

        WEIGHTS = {
            'vowel':       1.0,
            'space':       0.4,
            'pause_short': 0.8,
            'pause_long':  1.5,
        }
        total_weight = sum(WEIGHTS[kind] for kind, _ in events)
        time_unit = duration / total_weight

        start_time = time.time()
        current = REST

        try:
            for kind, char in events:
                if time.time() - start_time > duration:
                    break

                slot = time_unit * WEIGHTS[kind]

                if kind == 'vowel':
                    target = VOWEL_MAP.get(char, REST)
                    current = await self._lerp_to(
                        target[0], target[1], current,
                        steps=4, interval=slot * 0.6 / 4
                    )
                    current = await self._lerp_to(
                        REST[0], REST[1], current,
                        steps=3, interval=slot * 0.4 / 3
                    )

                elif kind == 'space':
                    current = await self._lerp_to(
                        REST[0], REST[1], current,
                        steps=2, interval=slot / 2
                    )

                elif kind == 'pause_short':
                    current = await self._lerp_to(
                        PAUSE_SHORT[0], PAUSE_SHORT[1], current,
                        steps=3, interval=slot / 3
                    )

                elif kind == 'pause_long':
                    current = await self._lerp_to(
                        PAUSE_LONG[0], PAUSE_LONG[1], current,
                        steps=4, interval=slot / 4
                    )

        finally:
            await self._lerp_to(REST[0], REST[1], current, steps=8, interval=0.04)
            await self.set_parameters({PARAM_MOUTH_OPEN: 0.15, PARAM_MOUTH_SMILE: -0.5})
            self._is_speaking = False

    def start_lip_sync(self, text, duration, loop):
        asyncio.run_coroutine_threadsafe(
            self.lip_sync_sim(text, duration), loop
        )