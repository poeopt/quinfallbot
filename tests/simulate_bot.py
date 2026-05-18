import json
import bot_core
import time

def simulate():
    # Mock BotCore to not start real sniffer or UI loop
    core = bot_core.BotCore()

    print("Simulating packet processing...")
    count = 0
    with open('live_packets.jsonl', 'r') as f:
        for line in f:
            pkt = json.loads(line)
            data = bytes.fromhex(pkt['hex'])
            core.packet_callback(data)
            count += 1
            if count % 1000 == 0:
                print(f"Processed {count} packets. Current Pos: {core.player_pos}")

    print("\nSimulation complete.")
    print(f"Final Player Pos: {core.player_pos}")
    resources = core.resource_tracker.get_resources()
    print(f"Detected {len(resources)} unique entities/resources.")
    for uuid, data in list(resources.items())[:10]:
        print(f"  {uuid}: {data['name']} at {data['x']}, {data['z']}")

if __name__ == "__main__":
    simulate()
