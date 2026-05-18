import json
import struct
from collections import Counter

def analyze():
    size_274_yaw = []
    size_274_pitch = []
    size_31_rot = []

    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            try:
                pkt = json.loads(line)
                data = bytes.fromhex(pkt['hex'])

                if len(data) == 274:
                    # Based on live_parser.py
                    yaw_raw = struct.unpack("<H", data[85:87])[0]
                    pitch_raw = struct.unpack("<h", data[94:96])[0]
                    size_274_yaw.append(yaw_raw)
                    size_274_pitch.append(pitch_raw)

                if len(data) == 31:
                    # Based on CONTEXT_PROMPT.md
                    if len(data) >= 28:
                        rot_raw = struct.unpack("<h", data[26:28])[0]
                        size_31_rot.append(rot_raw)
            except Exception as e:
                pass

    print(f"Size 274: Found {len(size_274_yaw)} packets")
    if size_274_yaw:
        print(f"Yaw range: {min(size_274_yaw)} - {max(size_274_yaw)}, unique: {len(set(size_274_yaw))}")
        print(f"Pitch range: {min(size_274_pitch)} - {max(size_274_pitch)}, unique: {len(set(size_274_pitch))}")
        print("First 10 yaws:", size_274_yaw[:10])

    print(f"\nSize 31: Found {len(size_31_rot)} packets")
    if size_31_rot:
        print(f"ROT range: {min(size_31_rot)} - {max(size_31_rot)}, unique: {len(set(size_31_rot))}")
        print("First 10 ROTs:", size_31_rot[:10])

    # Check for other markers in 274
    if len(size_274_yaw) > 0:
        print("\nChecking markers in 274 byte packets...")
        MARKER = bytes.fromhex("0204000000")
        with open('live_packets.jsonl', 'r') as f:
            count = 0
            for line in f:
                pkt = json.loads(line)
                data = bytes.fromhex(pkt['hex'])
                if len(data) == 274:
                    pos = 0
                    markers = []
                    while True:
                        p = data.find(MARKER, pos)
                        if p == -1: break
                        val = struct.unpack("<f", data[p+5:p+9])[0]
                        markers.append((p, val))
                        pos = p + 1
                    if markers:
                        print(f"Packet {count} markers: {markers}")
                    count += 1
                    if count > 5: break

if __name__ == "__main__":
    analyze()
