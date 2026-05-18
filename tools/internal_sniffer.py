import struct
from scapy.all import sniff, TCP, Raw, IP
import threading
import time

class QuinfallSniffer:
    TAG = bytes([0x01, 0x04, 0x00, 0x00, 0x00])

    def __init__(self, callback):
        self.callback = callback
        self.sessions = {} # (ip_src, port_src, ip_dst, port_dst) -> b""
        self.running = False

    def handle_packet(self, pkt):
        if not pkt.haslayer(TCP) or not pkt.haslayer(Raw):
            return

        ip = pkt[IP]
        tcp = pkt[TCP]
        session_id = (ip.src, tcp.sport, ip.dst, tcp.dport)

        payload = pkt[Raw].load

        if session_id not in self.sessions:
            self.sessions[session_id] = b""

        self.sessions[session_id] += payload
        self.sessions[session_id] = self._parse_buffer(self.sessions[session_id])

    def _parse_buffer(self, buf):
        while len(buf) >= 4:
            try:
                size = struct.unpack("<I", buf[:4])[0]
                if size == 0 or size > 65535:
                    buf = buf[1:]
                    continue

                if len(buf) < size + 4:
                    break

                packet_data = buf[4:4+size]
                self.callback(packet_data)
                buf = buf[4+size:]
            except Exception as e:
                buf = buf[1:]
        return buf

    def start(self, iface=None, filter_str="tcp"):
        self.running = True
        print(f"Starting Quinfall internal sniffer on {iface if iface else 'all interfaces'}...")
        sniff(iface=iface, filter=filter_str, prn=self.handle_packet, store=0, stop_filter=lambda x: not self.running)

    def stop(self):
        self.running = False

def example_callback(data):
    if len(data) >= 13 and data[4:9] == QuinfallSniffer.TAG:
        msg_type = struct.unpack("<I", data[9:13])[0]
        print(f"Captured Quinfall Msg: Type={msg_type}, Size={len(data)}")

if __name__ == "__main__":
    sniffer = QuinfallSniffer(example_callback)
    try:
        sniffer.start()
    except KeyboardInterrupt:
        sniffer.stop()
