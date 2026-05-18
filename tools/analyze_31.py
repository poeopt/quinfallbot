import json
import struct

def analyze_31():
    print("Analyzing 31-byte packets:")
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            try:
                pkt = json.loads(line)
                data = bytes.fromhex(pkt['hex'])
                if len(data) == 31:
                    msg_type = struct.unpack("<I", data[9:13])[0] if len(data) >= 13 else 0
                    raw_26 = struct.unpack("<h", data[26:28])[0] if len(data) >= 28 else 0
                    raw_18 = struct.unpack("<h", data[18:20])[0] if len(data) >= 20 else 0
                    print(f"Type: {msg_type:3} Offset 26: {raw_26:6} Offset 18: {raw_18:6} Hex: {data.hex()}")
            except:
                pass

if __name__ == "__main__":
    analyze_31()
