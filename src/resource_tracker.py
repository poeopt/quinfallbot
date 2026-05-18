import json
import struct
import time
from collections import defaultdict

class ResourceTracker:
    MARKER = bytes([0x02, 0x04, 0x00, 0x00, 0x00])
    TAG = bytes([0x01, 0x04, 0x00, 0x00, 0x00])

    def __init__(self):
        self.resources = {} # uuid -> {x, y, z, name, ts}

    def process_packet(self, data):
        if len(data) < 13 or data[4:9] != self.TAG:
            return

        msg_type = struct.unpack("<I", data[9:13])[0]

        if msg_type == 156: # MSG_ENTITY_POS
            self._handle_entity_pos(data)
        elif msg_type == 101: # MSG_SPAWN
            self._handle_spawn(data)

    def _handle_entity_pos(self, data):
        # BLOCK from proxy_server.py
        BLOCK = bytes([0x00,0x00,0x00,0x00,0x18,0x00,0x00,0x00])
        now = time.time()
        pos = 0
        while True:
            p = data.find(BLOCK, pos)
            if p == -1: break
            us = p + 8
            if us + 24 <= len(data):
                try:
                    uuid = data[us:us+24].decode()
                    # Check if it's a hex-like UUID often used for entities
                    if all(b in b'0123456789abcdef' for b in data[us:us+24]):
                        seg = data[us:us+150]
                        coords = []
                        bp = 0
                        while bp < len(seg) - 9:
                            if seg[bp:bp+5] == self.MARKER:
                                v = struct.unpack_from("<f", seg, bp+5)[0]
                                if -200000 < v < 200000 and abs(v) > 10:
                                    coords.append(round(v, 2))
                                bp += 9
                            else: bp += 1

                        if len(coords) >= 2:
                            if uuid not in self.resources:
                                self.resources[uuid] = {"name": "Entity", "ts": now}
                            self.resources[uuid].update({"x": coords[0], "z": coords[1], "y": coords[2] if len(coords)>2 else 0, "ts": now})
                except:
                    pass
            pos = p + 1

        # Cleanup old resources
        cutoff = now - 30
        self.resources = {k: v for k, v in self.resources.items() if v["ts"] > cutoff}

    def _handle_spawn(self, data):
        # Basic spawn parsing to get names if possible
        now = time.time()
        strs = self._find_strings(data)
        uuids = [s for s in strs if len(s) == 24 and all(c in '0123456789abcdef' for c in s)]
        items = [s for s in strs if '_' in s and len(s) > 5]

        if uuids and items:
            uuid = uuids[0]
            name = items[0]
            if uuid in self.resources:
                self.resources[uuid]["name"] = name
            else:
                self.resources[uuid] = {"name": name, "ts": now, "x":0, "y":0, "z":0}

    def _find_strings(self, data):
        i, res = 0, []
        while i < len(data) - 4:
            try:
                sl = struct.unpack_from('<I', data, i)[0]
                if 3 <= sl <= 80 and i + 4 + sl <= len(data):
                    s = data[i+4:i+4+sl]
                    if all(32 <= b < 127 for b in s):
                        res.append(s.decode())
                        i += 4 + sl
                        continue
            except: pass
            i += 1
        return res

    def get_resources(self):
        return self.resources
