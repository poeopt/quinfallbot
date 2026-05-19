import json
from src import live_parser

def test_parser():
    count = 0
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            pkt = json.loads(line)
            data = bytes.fromhex(pkt['hex'])
            # The handle function expects payload without the 4-byte size header if called from sniffer,
            # but internal_sniffer.py does self.callback(buf[4:4+size])
            # Wait, internal_sniffer.py says:
            # packet_data = buf[4:4+size]
            # self.callback(packet_data)
            # And buf[4:9] is the TAG.
            # live_parser.handle(payload) checks msg_type at payload[9:13].
            # If payload starts with TAG (5 bytes), then msg_type is at offset 9?
            # Let's check: 0,1,2,3,4 (TAG) 5,6,7,8 (Size of what?) 9,10,11,12 (Type?)

            result = live_parser.handle(data[4:]) # Skip 4-byte size header
            if result:
                ts = pkt.get('time') or pkt.get('ts')
                print(f"Time: {ts} Result: {result}")
                count += 1
                #if count > 20: break

if __name__ == "__main__":
    test_parser()
