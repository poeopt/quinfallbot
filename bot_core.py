import sys
import threading
import time
from src.internal_sniffer import QuinfallSniffer
from src.resource_tracker import ResourceTracker
from src.vision_verifier import VisionVerifier
from src.route_manager import RouteManager
from src.bot_ui import BotMainWindow
from src import live_parser, config
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

class BotCore:
    def __init__(self):
        self.resource_tracker = ResourceTracker()
        self.vision_verifier = VisionVerifier(tesseract_cmd=config.TESSERACT_PATH)
        self.route_manager = RouteManager()

        self.player_pos = {"x": 0, "y": 0, "z": 0, "rot": 0, "id": 0}

        self.sniffer = QuinfallSniffer(self.packet_callback)
        self.sniffer_thread = None

        self.app = QApplication(sys.argv)
        self.window = BotMainWindow()

        # Connect buttons
        self.window.start_btn.clicked.connect(self.start_bot)
        self.window.stop_btn.clicked.connect(self.stop_bot)
        self.window.record_btn.toggled.connect(self.toggle_record)
        self.window.save_route_btn.clicked.connect(self.save_route)
        self.window.load_route_btn.clicked.connect(self.load_route)

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
        if self.sniffer_thread is None or not self.sniffer_thread.is_alive():
            self.sniffer_thread = threading.Thread(target=self.sniffer.start, daemon=True)
            self.sniffer_thread.start()
        self.window.status_label.setText("Running")
        self.window.log("Bot started.")

    def stop_bot(self):
        self.sniffer.stop()
        self.window.status_label.setText("Stopped")
        self.window.log("Bot stopped.")

    def toggle_record(self, checked):
        if checked:
            self.route_manager.start_recording()
            self.window.log("Started recording route...")
        else:
            self.route_manager.stop_recording()
            self.window.log(f"Stopped recording. Points: {len(self.route_manager.current_route)}")

    def save_route(self):
        self.route_manager.save_route("custom_route.json")
        self.window.log("Route saved to custom_route.json")

    def load_route(self):
        try:
            pts = self.route_manager.load_route("custom_route.json")
            self.window.log(f"Loaded route with {len(pts)} points.")
        except:
            self.window.log("Error: custom_route.json not found.")

    def update_ui(self):
        self.window.pos_label.setText(f"X: {self.player_pos['x']}, Y: {self.player_pos['y']}, Z: {self.player_pos['z']} (ID: {self.player_pos['id']})")

        # Update resource list only if changed or periodically to avoid flicker
        resources = self.resource_tracker.get_resources()
        if self.window.resource_list.count() != len(resources):
            self.window.resource_list.clear()
            for uuid, data in resources.items():
                self.window.resource_list.addItem(f"{data['name']} at {data['x']}, {data['z']}")

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())

if __name__ == "__main__":
    core = BotCore()
    core.run()
    print("Bot Core initialized and integrated.")
