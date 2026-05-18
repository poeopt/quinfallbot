import json
import struct

def find_entity_262598():
    MARKER = bytes.fromhex("0204000000")
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            pkt = json.loads(line)
            data = bytes.fromhex(pkt['hex'])
            if len(data) >= 56:
                entity_id = struct.unpack("<I", data[52:56])[0]
                if entity_id == 262598:
                    msg_type = struct.unpack("<I", data[9:13])[0] if len(data) >= 13 else 0
                    pos = data.find(MARKER)
                    print(f"Found 262598: Size={len(data)} Type={msg_type} MarkerPos={pos}")
                    if pos != -1:
                        x = struct.unpack("<f", data[pos+5:pos+9])[0]
                        print(f"  X={x}")

if __name__ == "__main__":
    find_entity_262598()
