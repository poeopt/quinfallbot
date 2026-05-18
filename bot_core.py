import sys
import threading
import time
from tools.internal_sniffer import QuinfallSniffer
from tools.resource_tracker import ResourceTracker
from tools.vision_verifier import VisionVerifier
from tools.route_manager import RouteManager
from tools.bot_ui import BotMainWindow
import live_parser
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

class BotCore:
    def __init__(self):
        self.resource_tracker = ResourceTracker()
        self.vision_verifier = VisionVerifier()
        self.route_manager = RouteManager()

        self.player_pos = {"x": 0, "y": 0, "z": 0, "rot": 0, "id": 0}

        self.sniffer = QuinfallSniffer(self.packet_callback)
        self.sniffer_thread = threading.Thread(target=self.sniffer.start, daemon=True)

        self.app = QApplication(sys.argv)
        self.window = BotMainWindow()

        # Connect buttons
        self.window.start_btn.clicked.connect(self.start_bot)
        self.window.stop_btn.clicked.connect(self.stop_bot)

        # Update timer for UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100) # 10Hz

    def packet_callback(self, data):
        # Update player pos using live_parser
        res = live_parser.handle(data)
        if res:
            self.player_pos.update({
                "x": res.get("x", 0),
                "y": res.get("y", 0),
                "z": res.get("z", 0),
                "rot": res.get("yaw", 0),
                "id": res.get("entity_id", 0)
            })
            if self.route_manager.is_recording:
                self.route_manager.add_point(res["x"], res["y"], res["z"])

            # OCR verification when near a known resource (simplified demo)
            # if self.is_at_destination():
            #    self.verify_ore_with_ocr()

        # Update resources
        self.resource_tracker.process_packet(data)

    def start_bot(self):
        if not self.sniffer_thread.is_alive():
            self.sniffer_thread.start()
        self.window.status_label.setText("Running")
        self.window.log("Bot started.")

    def stop_bot(self):
        self.sniffer.stop()
        self.window.status_label.setText("Stopped")
        self.window.log("Bot stopped.")

    def update_ui(self):
        self.window.pos_label.setText(f"X: {self.player_pos['x']}, Y: {self.player_pos['y']}, Z: {self.player_pos['z']} (ID: {self.player_pos['id']})")

        # Update resource list
        self.window.resource_list.clear()
        for uuid, data in self.resource_tracker.get_resources().items():
            self.window.resource_list.addItem(f"{data['name']} at {data['x']}, {data['z']}")

    def run(self):
        self.window.show()
        # sys.exit(self.app.exec()) # Commented for sandbox

if __name__ == "__main__":
    core = BotCore()
    core.run()
    print("Bot Core initialized and integrated.")
