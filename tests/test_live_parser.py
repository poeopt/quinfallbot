import json
from src import live_parser

def test_parser():
    count = 0
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            pkt = json.loads(line)
            data = bytes.fromhex(pkt['hex'])
            result = live_parser.handle(data)
            if result:
                ts = pkt.get('time') or pkt.get('ts')
                print(f"Time: {ts} Result: {result}")
                count += 1
                #if count > 20: break

if __name__ == "__main__":
    test_parser()
