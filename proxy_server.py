"""
proxy_server.py — TCP прокси + WebSocket сервер.

Заменяет mitmproxy полностью. Proxifier направляет трафик игры сюда.

Схема:
    Игра → Proxifier → proxy_server.py:8080 → Сервер игры
                              ↓
                       ws://localhost:9999  → radar.html

Настройка Proxifier:
    Rules → Add:
        Application: The_Quinfall.exe (или имя exe игры)
        Action: Proxy SOCKS5 127.0.0.1:8080

Запуск:
    python proxy_server.py

Зависимости:
    pip install websockets
"""

import asyncio
import json
import struct
import time
import threading
import socket

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False
    print("[!] pip install websockets")

# ═══════════════════════════════════════════════════════════════════
# Настройки
# ═══════════════════════════════════════════════════════════════════

PROXY_HOST = "0.0.0.0"
PROXY_PORT = 8080        # Proxifier направляет сюда

WS_HOST    = "localhost"
WS_PORT    = 9999        # Радар подключается сюда

# ═══════════════════════════════════════════════════════════════════
# Протокол Quinfall
# ═══════════════════════════════════════════════════════════════════

TAG    = bytes([0x01, 0x04, 0x00, 0x00, 0x00])
MARKER = bytes([0x02, 0x04, 0x00, 0x00, 0x00])

MSG_PLAYER_POS = 200
MSG_ENTITY_POS = 156
MSG_SPAWN      = 101
MSG_PLAYERS    = 171

# ═══════════════════════════════════════════════════════════════════
# Мировое состояние
# ═══════════════════════════════════════════════════════════════════

state = {
    "player":   {"x": 0.0, "y": 0.0, "z": 0.0, "rot": 0.0, "ts": 0.0},
    "entities": {},
    "players":  {},
    "spawns":   [],
}

ws_clients = set()
_dirty     = False
_pkt_count = 0

# ═══════════════════════════════════════════════════════════════════
# Парсеры
# ═══════════════════════════════════════════════════════════════════

def rf(data, pos):
    if pos + 4 > len(data): return 0.0
    return struct.unpack_from("<f", data, pos)[0]

def ru32(data, pos):
    if pos + 4 > len(data): return 0
    return struct.unpack_from("<I", data, pos)[0]

def get_msg_type(pkt):
    if len(pkt) >= 13 and pkt[4:9] == TAG:
        return ru32(pkt, 9)
    return 0

def all_markers(data):
    pos, res = 0, []
    while True:
        p = data.find(MARKER, pos)
        if p == -1: break
        res.append((p, rf(data, p + 5)))
        pos = p + 1
    return res

def valid(v):
    return -200_000 < v < 200_000

def find_strings(data):
    i, res = 0, []
    while i < len(data) - 4:
        sl = ru32(data, i)
        if 3 <= sl <= 80 and i + 4 + sl <= len(data):
            s = data[i+4:i+4+sl]
            if all(32 <= b < 127 for b in s):
                res.append((i, s.decode()))
        i += 1
    return res

def parse_player_pos(pkt):
    global _dirty
    now   = time.time()

    pos = pkt.find(MARKER)
    if pos == -1: return

    # Position
    try:
        x = struct.unpack_from("<f", pkt, pos + 5)[0]
        y = struct.unpack_from("<f", pkt, pos + 14)[0]
        z = struct.unpack_from("<f", pkt, pos + 23)[0]

        state["player"].update({
            "x": round(x, 2),
            "y": round(y, 2),
            "z": round(z, 2),
            "ts": now
        })
        _dirty = True
    except:
        pass

    # Rotation
    try:
        if pos + 61 <= len(pkt):
            yaw_raw = struct.unpack_from("<H", pkt, pos + 59)[0]
            yaw = (yaw_raw / 65535.0) * 360.0
            state["player"]["rot"] = round(yaw, 2)
            _dirty = True
    except:
        pass

def parse_entity_pos(pkt):
    global _dirty
    now   = time.time()
    BLOCK = bytes([0x00,0x00,0x00,0x00,0x18,0x00,0x00,0x00])
    pos   = 0
    changed = False
    while True:
        p = pkt.find(BLOCK, pos)
        if p == -1: break
        us = p + 8
        if us + 24 > len(pkt): pos = p+1; continue
        ub = pkt[us:us+24]
        if not all(b in b'0123456789abcdef' for b in ub): pos = p+1; continue
        uuid = ub.decode()
        seg, coords, bp = pkt[us:us+150], [], 0
        while bp < len(seg) - 9:
            if seg[bp:bp+5] == MARKER:
                v = rf(seg, bp+5)
                if valid(v) and abs(v) > 10: coords.append(round(v,1))
                bp += 9
            else: bp += 1
        if len(coords) >= 2:
            state["entities"][uuid] = {"x": coords[0], "z": coords[1], "ts": now}
            changed = True
        pos = p + 1
    cutoff = now - 30
    state["entities"] = {k:v for k,v in state["entities"].items() if v["ts"] > cutoff}
    if changed: _dirty = True

def parse_spawn(pkt):
    global _dirty
    now     = time.time()
    floats  = [(p,v) for p,v in all_markers(pkt) if valid(v)]
    strings = find_strings(pkt)
    uuids   = [(i,s) for i,s in strings if len(s)==24 and all(c in '0123456789abcdef' for c in s)]
    items   = [s for _,s in strings if '_' in s and len(s) > 5]
    xyz     = [round(v,1) for _,v in floats[:3]] if len(floats)>=3 else []
    if uuids and xyz:
        uuid  = uuids[0][1]
        event = {"uuid":uuid,"x":xyz[0],"y":xyz[1] if len(xyz)>1 else 0,
                 "z":xyz[2] if len(xyz)>2 else 0,"items":items,"ts":now}
        state["spawns"] = [s for s in state["spawns"] if s["uuid"]!=uuid]
        state["spawns"].append(event)
        state["spawns"] = state["spawns"][-100:]
        _dirty = True

def parse_players(pkt):
    global _dirty
    now = time.time()
    for _, text in find_strings(pkt):
        for suf in ("'s Area"," Area"," area"):
            if text.endswith(suf):
                name = text[:-len(suf)]
                if name and len(name)<30 and not all(c in '0123456789abcdef' for c in name.lower()):
                    state["players"][name] = {"area": text, "ts": now}
                    _dirty = True
                break

def process_packet(data: bytes):
    global _pkt_count
    if len(data) < 13: return
    mt = get_msg_type(data)
    _pkt_count += 1
    if   mt == MSG_PLAYER_POS: parse_player_pos(data)
    elif mt == MSG_ENTITY_POS: parse_entity_pos(data)
    elif mt == MSG_SPAWN:      parse_spawn(data)
    elif mt == MSG_PLAYERS:    parse_players(data)

# ═══════════════════════════════════════════════════════════════════
# SOCKS5 прокси — Proxifier использует SOCKS5
# ═══════════════════════════════════════════════════════════════════

class Socks5Proxy:
    """Минимальный SOCKS5 прокси с перехватом S→C трафика."""

    SOCKS_VER = 5

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(50)
        print(f"[Proxy] SOCKS5 слушаю {self.host}:{self.port}")
        while True:
            try:
                cl, addr = srv.accept()
                threading.Thread(target=self._handle, args=(cl,), daemon=True).start()
            except Exception as e:
                print(f"[Proxy] accept error: {e}")

    def _handle(self, cl: socket.socket):
        try:
            # ── Handshake ──────────────────────────────────────
            cl.recv(2)                          # VER + NMETHODS
            cl.recv(1)                          # METHOD (no auth)
            cl.sendall(bytes([self.SOCKS_VER, 0x00]))  # no auth required

            # ── Request ────────────────────────────────────────
            hdr = cl.recv(4)
            if len(hdr) < 4: return
            cmd, atyp = hdr[1], hdr[3]

            if atyp == 0x01:        # IPv4
                addr = socket.inet_ntoa(cl.recv(4))
            elif atyp == 0x03:      # Domain
                ln   = cl.recv(1)[0]
                addr = cl.recv(ln).decode()
            elif atyp == 0x04:      # IPv6
                addr = cl.recv(16)
                addr = socket.inet_ntop(socket.AF_INET6, addr)
            else:
                cl.close(); return

            port = struct.unpack("!H", cl.recv(2))[0]

            if cmd != 0x01:         # только CONNECT
                cl.sendall(bytes([self.SOCKS_VER, 0x07, 0x00, 0x01,
                                  0,0,0,0, 0,0]))
                cl.close(); return

            # ── Connect to real server ─────────────────────────
            try:
                srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv_sock.settimeout(10)
                srv_sock.connect((addr, port))
                srv_sock.settimeout(None)
            except Exception as e:
                cl.sendall(bytes([self.SOCKS_VER, 0x05, 0x00, 0x01,
                                  0,0,0,0, 0,0]))
                cl.close(); return

            # ── Success ────────────────────────────────────────
            cl.sendall(bytes([self.SOCKS_VER, 0x00, 0x00, 0x01,
                              0,0,0,0, 0,0]))

            # ── Pipe ───────────────────────────────────────────
            t1 = threading.Thread(target=self._pipe,
                                  args=(cl, srv_sock, False), daemon=True)
            t2 = threading.Thread(target=self._pipe,
                                  args=(srv_sock, cl, True), daemon=True)
            t1.start(); t2.start()
            t1.join(); t2.join()

        except Exception:
            pass
        finally:
            try: cl.close()
            except: pass

    def _pipe(self, src, dst, parse: bool):
        """Читаем поток, парсим пакеты если parse=True (S→C), пересылаем."""
        buf = b""
        while True:
            try:
                chunk = src.recv(65536)
                if not chunk: break
                dst.sendall(chunk)
                if parse:
                    buf += chunk
                    buf  = self._parse_buf(buf)
            except Exception:
                break
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

    @staticmethod
    def _parse_buf(buf: bytes) -> bytes:
        """Вычленяем пакеты из TCP потока и парсим."""
        while len(buf) >= 4:
            size = struct.unpack_from("<I", buf, 0)[0]
            if size == 0 or size > 65535:
                buf = buf[1:]; continue
            if len(buf) < size + 4:
                break
            process_packet(buf[4:4+size])
            buf = buf[4+size:]
        return buf


# ═══════════════════════════════════════════════════════════════════
# WebSocket сервер
# ═══════════════════════════════════════════════════════════════════

async def ws_handler(ws):
    ws_clients.add(ws)
    print(f"[WS] Радар подключился")
    try:
        await ws.send(json.dumps(state))
        async for _ in ws: pass
    except Exception:
        pass
    finally:
        ws_clients.discard(ws)
        print(f"[WS] Радар отключился")

async def broadcast_loop():
    global _dirty
    while True:
        await asyncio.sleep(0.05)   # 20 Hz
        if _dirty and ws_clients:
            msg    = json.dumps(state, ensure_ascii=False)
            _dirty = False
            dead   = set()
            for ws in list(ws_clients):
                try: await ws.send(msg)
                except: dead.add(ws)
            ws_clients -= dead

async def ws_main():
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT,
                                ping_interval=20, ping_timeout=10):
        print(f"[WS] Сервер: ws://{WS_HOST}:{WS_PORT}")
        await broadcast_loop()

# ═══════════════════════════════════════════════════════════════════
# Статус — печатаем каждые 5 секунд
# ═══════════════════════════════════════════════════════════════════

def status_loop():
    while True:
        time.sleep(5)
        p = state["player"]
        ent = len(state["entities"])
        spw = len(state["spawns"])
        print(f"[*] PKT={_pkt_count}  "
              f"X={p['x']:.0f} Y={p['y']:.0f} Z={p['z']:.0f}  "
              f"ROT={p['rot']:.3f}  ENT={ent}  SPAWN={spw}  "
              f"WS-clients={len(ws_clients)}")

# ═══════════════════════════════════════════════════════════════════
# Запуск
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  Quinfall Proxy + WebSocket Server")
    print("=" * 55)
    print(f"  SOCKS5 прокси : {PROXY_HOST}:{PROXY_PORT}")
    print(f"  WebSocket     : ws://{WS_HOST}:{WS_PORT}")
    print()
    print("  Настройте Proxifier:")
    print("    Proxy Server → Add → SOCKS5 127.0.0.1:8080")
    print("    Rules → игра использует этот прокси")
    print("=" * 55)

    if not HAS_WS:
        print("[!] pip install websockets")
        return

    # Статус в фоне
    threading.Thread(target=status_loop, daemon=True).start()

    # WebSocket в фоне
    def run_ws():
        asyncio.run(ws_main())
    threading.Thread(target=run_ws, daemon=True).start()

    # SOCKS5 прокси — главный поток
    proxy = Socks5Proxy(PROXY_HOST, PROXY_PORT)
    proxy.start()

if __name__ == "__main__":
    main()
