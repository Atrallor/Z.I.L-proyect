import time
import asyncio

PARAM_MOUTH_OPEN  = "ZIL_MouthOpen"
PARAM_MOUTH_SMILE = "ZIL_MouthSmile"

VOWELS = set('aáeéiíoóuúü')
PUNCTUATION_SHORT = set(',;')
PUNCTUATION_LONG  = set('.!?…')

async def _lerp_to(vts_api, target_open, target_smile, current, steps=6, interval=0.03):
    cur_open, cur_smile = current
    for _ in range(steps):
        cur_open  += (target_open  - cur_open)  * 0.5
        cur_smile += (target_smile - cur_smile) * 0.5
        await vts_api.set_parameters({
            PARAM_MOUTH_OPEN:  round(cur_open,  3),
            PARAM_MOUTH_SMILE: round(cur_smile, 3),
        })
        await asyncio.sleep(interval)
    return (cur_open, cur_smile)

async def lip_sync_sim(vts_api, text, duration):
    if vts_api._is_speaking:
        return
    vts_api._is_speaking = True

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
                current = await _lerp_to(
                    vts_api, target[0], target[1], current,
                    steps=4, interval=slot * 0.6 / 4
                )
                current = await _lerp_to(
                    vts_api, REST[0], REST[1], current,
                    steps=3, interval=slot * 0.4 / 3
                )

            elif kind == 'space':
                current = await _lerp_to(
                    vts_api, REST[0], REST[1], current,
                    steps=2, interval=slot / 2
                )

            elif kind == 'pause_short':
                current = await _lerp_to(
                    vts_api, PAUSE_SHORT[0], PAUSE_SHORT[1], current,
                    steps=3, interval=slot / 3
                )

            elif kind == 'pause_long':
                current = await _lerp_to(
                    vts_api, PAUSE_LONG[0], PAUSE_LONG[1], current,
                    steps=4, interval=slot / 4
                )

    finally:
        await _lerp_to(vts_api, REST[0], REST[1], current, steps=8, interval=0.04)
        await vts_api.set_parameters({PARAM_MOUTH_OPEN: 0.15, PARAM_MOUTH_SMILE: -0.5})
        vts_api._is_speaking = False

def start_lip_sync(vts_api, text, duration, loop):
    asyncio.run_coroutine_threadsafe(
        lip_sync_sim(vts_api, text, duration), loop
    )
