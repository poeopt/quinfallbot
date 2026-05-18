import json
import struct

def test_robust_parsing():
    MARKER = bytes.fromhex("0204000000")
    count = 0
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            try:
                pkt = json.loads(line)
                data = bytes.fromhex(pkt['hex'])
                if len(data) < 13: continue

                msg_type = struct.unpack("<I", data[9:13])[0]
                if msg_type == 200:
                    pos = data.find(MARKER)
                    if pos != -1:
                        if pos + 27 <= len(data):
                            x = struct.unpack("<f", data[pos+5:pos+9])[0]
                            y = struct.unpack("<f", data[pos+14:pos+18])[0]
                            z = struct.unpack("<f", data[pos+23:pos+27])[0]

                            yaw, pitch = None, None
                            if pos + 61 <= len(data):
                                yaw_raw = struct.unpack("<H", data[pos+59:pos+61])[0]
                                yaw = (yaw_raw / 65535.0) * 360.0

                            if pos + 70 <= len(data):
                                pitch_raw = struct.unpack("<h", data[pos+68:pos+70])[0]
                                pitch = (pitch_raw / 32767.0) * 90.0

                            print(f"Size {len(data):3}: X={x:10.2f} Y={y:7.2f} Z={z:10.2f} Yaw={yaw if yaw is not None else 0:7.2f} Pitch={pitch if pitch is not None else 0:7.2f}")
                            count += 1
                            if count > 50: break
            except Exception as e:
                pass

if __name__ == "__main__":
    test_robust_parsing()
