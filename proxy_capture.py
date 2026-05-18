from mitmproxy import tcp
import json
import time


LOG_FILE = "live_packets.jsonl"


class PacketCapture:

    def tcp_message(self, flow: tcp.TCPFlow):

        try:

            message = flow.messages[-1]

            payload = bytes(message.content)

            row = {
                "time": time.time(),
                "size": len(payload),
                "hex": payload.hex()
            }

            with open(
                LOG_FILE,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    json.dumps(row) + "\n"
                )

        except Exception as e:

            print(e)


addons = [PacketCapture()]