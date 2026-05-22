import struct
from scapy.all import sniff, TCP, Raw, IP, conf
import threading
import time
import traceback
from src import config

class QuinfallSniffer:
    TAG = bytes([0x01, 0x04, 0x00, 0x00, 0x00])

    def __init__(self, callback, log_callback=None):
        self.callback = callback
        self.log_callback = log_callback
        self.sessions = {} # (ip_src, port_src, ip_dst, port_dst) -> {"buf": b"", "last_ts": float}
        self.running = False

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)
        print(f"[Sniffer] {message}")

    @staticmethod
    def list_interfaces():
        try:
            return [str(iface) for iface in conf.ifaces.values()]
        except Exception as e:
            return [f"Error listing interfaces: {e}"]

    def handle_packet(self, pkt):
        if not pkt.haslayer(TCP) or not pkt.haslayer(Raw):
            return

        ip = pkt[IP]
        tcp = pkt[TCP]
        session_id = (ip.src, tcp.sport, ip.dst, tcp.dport)

        payload = pkt[Raw].load
        now = time.time()

        if session_id not in self.sessions:
            self.sessions[session_id] = {"buf": b"", "last_ts": now}

        session = self.sessions[session_id]
        session["buf"] += payload
        session["last_ts"] = now
        session["buf"] = self._parse_buffer(session["buf"])

        # Periodic cleanup of old sessions
        if len(self.sessions) > 50:
            self._cleanup_sessions(now)

    def _cleanup_sessions(self, now):
        timeout = 60 # 60 seconds of inactivity
        to_delete = [sid for sid, s in self.sessions.items() if now - s["last_ts"] > timeout]
        for sid in to_delete:
            del self.sessions[sid]

    def _parse_buffer(self, buf):
        while len(buf) >= 13: # Min size for a header + TAG
            try:
                size = struct.unpack("<I", buf[:4])[0]

                # Check if this looks like a valid Quinfall packet
                # Offset 4 should be the TAG
                if 0 < size < 65535 and len(buf) >= 9 and buf[4:9] == self.TAG:
                    if len(buf) < size + 4:
                        break # Wait for more data

                    packet_data = buf[4:4+size]
                    self.callback(packet_data)
                    buf = buf[4+size:]
                else:
                    # Not a valid header or TAG mismatch, search for next TAG
                    next_tag = buf.find(self.TAG, 1)
                    if next_tag != -1 and next_tag >= 4:
                        buf = buf[next_tag - 4:] # Align to potential size header
                    else:
                        buf = buf[1:]
            except Exception:
                buf = buf[1:]
        return buf

    def start(self, iface=None):
        if iface is None:
            iface = config.SNIFFER_INTERFACE

        filter_str = "tcp"
        if config.GAME_SERVER_PORT > 0:
            filter_str = f"tcp port {config.GAME_SERVER_PORT}"

        self.running = True
        self._log(f"Starting Quinfall internal sniffer on {iface if iface else 'all interfaces'} with filter '{filter_str}'...")

        try:
            sniff(iface=iface, filter=filter_str, prn=self.handle_packet, store=0, stop_filter=lambda x: not self.running)
        except Exception as e:
            self.running = False
            err_msg = f"Sniffer error: {e}\n{traceback.format_exc()}"
            self._log(err_msg)

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
