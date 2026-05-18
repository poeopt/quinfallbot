import struct
import time
import math
from collections import defaultdict

OUTPUT_FILE = "player_live.txt"

last_write = 0

# =========================================
# ENTITY TRACKING
# =========================================

entity_scores = defaultdict(int)

current_entity = None

last_position = None

last_switch_time = 0


# =========================================
# READERS
# =========================================

def read_float(data, offset):

    try:
        return struct.unpack(
            "<f",
            data[offset:offset + 4]
        )[0]
    except:
        return 0.0


def read_u32(data, offset):

    try:
        return struct.unpack(
            "<I",
            data[offset:offset + 4]
        )[0]
    except:
        return 0


def read_u16(data, offset):

    try:
        return struct.unpack(
            "<H",
            data[offset:offset + 2]
        )[0]
    except:
        return 0


def read_i16(data, offset):

    try:
        return struct.unpack(
            "<h",
            data[offset:offset + 2]
        )[0]
    except:
        return 0


# =========================================
# ROTATION
# =========================================

def yaw_to_degrees(v):

    return (v / 65535.0) * 360.0


def pitch_to_degrees(v):

    return (v / 32767.0) * 90.0


# =========================================
# DISTANCE
# =========================================

def distance(a, b):

    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2 +
        (a[2] - b[2]) ** 2
    )


# =========================================
# MAIN PARSER
# =========================================

def handle(payload: bytes):

    global last_write
    global current_entity
    global last_position
    global last_switch_time

    # =========================================
    # MOVEMENT PACKET FILTER
    # =========================================

    if len(payload) != 274:
        return {}

    if payload[:4].hex() != "0e010000":
        return {}

    # =========================================
    # ENTITY
    # =========================================

    entity_id = read_u32(payload, 52)

    # =========================================
    # POSITION
    # =========================================

    x = read_float(payload, 31)
    y = read_float(payload, 40)
    z = read_float(payload, 49)

    position = (x, y, z)

    # =========================================
    # ROTATION
    # =========================================

    yaw_raw = read_u16(payload, 85)

    pitch_raw = read_i16(payload, 94)

    yaw = yaw_to_degrees(yaw_raw)

    pitch = pitch_to_degrees(pitch_raw)

    # =========================================
    # ENTITY SCORING
    # =========================================

    entity_scores[entity_id] += 1

    # =========================================
    # AUTO ENTITY REBIND
    # =========================================

    now = time.time()

    if current_entity is None:

        current_entity = entity_id

    else:

        if entity_id == current_entity:

            pass

        else:

            # =========================================
            # TELEPORT / WORLD TRANSFER DETECTION
            # =========================================

            if last_position is not None:

                dist = distance(
                    position,
                    last_position
                )

                # Large world jump detected

                if dist > 5000:

                    # Candidate new local entity

                    if (
                        entity_scores[entity_id]
                        >
                        entity_scores[current_entity] * 0.5
                    ):

                        current_entity = entity_id

                        last_switch_time = now

    # =========================================
    # FILTER NON-LOCAL ENTITY
    # =========================================

    if entity_id != current_entity:
        return {}

    # =========================================
    # SAVE POSITION
    # =========================================

    last_position = position

    # =========================================
    # RESULT
    # =========================================

    result = {

        "entity_id": entity_id,

        "x": round(x, 3),
        "y": round(y, 3),
        "z": round(z, 3),

        "yaw": round(yaw, 2),
        "pitch": round(pitch, 2)
    }

    # =========================================
    # REALTIME TXT OUTPUT
    # =========================================

    if now - last_write > 0.05:

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
f"""LOCAL PLAYER

ENTITY_ID: {entity_id}

POSITION
X: {result["x"]}
Y: {result["y"]}
Z: {result["z"]}

ROTATION
YAW: {result["yaw"]}
PITCH: {result["pitch"]}

AUTO ENTITY TRACKING: ACTIVE
"""
            )

        last_write = now

    return result
