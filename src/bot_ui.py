import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QListWidget)
from PySide6.QtCore import Qt, QTimer

class BotMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quinfall Bot Control Panel")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side - Status and Controls
        left_layout = QVBoxLayout()
        main_layout.addLayout(left_layout, 1)

        left_layout.addWidget(QLabel("<b>Bot Status</b>"))
        self.status_label = QLabel("Idle")
        left_layout.addWidget(self.status_label)

        self.pos_label = QLabel("X: 0.0, Y: 0.0, Z: 0.0")
        left_layout.addWidget(self.pos_label)

        self.start_btn = QPushButton("START BOT")
        self.start_btn.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        left_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP BOT")
        self.stop_btn.setStyleSheet("background-color: red; color: white;")
        left_layout.addWidget(self.stop_btn)

        left_layout.addSpacing(20)
        left_layout.addWidget(QLabel("<b>Route Controls</b>"))

        self.record_btn = QPushButton("RECORD ROUTE")
        self.record_btn.setCheckable(True)
        left_layout.addWidget(self.record_btn)

        self.save_route_btn = QPushButton("SAVE ROUTE")
        left_layout.addWidget(self.save_route_btn)

        self.load_route_btn = QPushButton("LOAD ROUTE")
        left_layout.addWidget(self.load_route_btn)

        left_layout.addStretch()

        # Center - Radar (Placeholder)
        center_layout = QVBoxLayout()
        main_layout.addLayout(center_layout, 2)
        center_layout.addWidget(QLabel("<b>Radar / Map</b>"))
        self.radar_view = QWidget()
        self.radar_view.setMinimumSize(400, 400)
        self.radar_view.setStyleSheet("background-color: black; border: 1px solid gray;")
        center_layout.addWidget(self.radar_view)

        # Right side - Log and Resources
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout, 1)

        right_layout.addWidget(QLabel("<b>Near Resources</b>"))
        self.resource_list = QListWidget()
        right_layout.addWidget(self.resource_list)

        right_layout.addWidget(QLabel("<b>Log</b>"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)

    def log(self, message):
        self.log_text.append(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotMainWindow()
    window.show()
    # sys.exit(app.exec()) # Commented out for sandbox environment
    print("UI module created successfully.")
