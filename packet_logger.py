from mitmproxy import tcp
import json
import time

LOG_FILE = "live_packets.jsonl"

class PacketLogger:

    def tcp_message(self, flow: tcp.TCPFlow):

        try:

            message = flow.messages[-1]

            payload = message.content

            if not payload:
                return

            entry = {
                "ts": time.time(),
                "size": len(payload),
                "hex": payload.hex(),
                "from_client": message.from_client
            }

            with open(
                LOG_FILE,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    json.dumps(entry)
                    + "\n"
                )

        except Exception as e:

            print("LOGGER ERROR:", e)

addons = [
    PacketLogger()
]