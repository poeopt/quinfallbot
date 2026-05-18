# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'local_dev_main.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
SOURCE_BASE_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SOURCE_BASE_DIR
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from mmobot.core.logging_setup import configure_logging
from mmobot.gui.main_window import MainWindow
from mmobot.models.config_models import AppConfig
def main() -> int:
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        internal_dir = exe_dir / '_internal'
        base_dir = internal_dir if (internal_dir / 'profiles').exists() else exe_dir
    else:
        base_dir = BASE_DIR
    config = AppConfig.default(base_dir)
    configure_logging(config.log_dir)
    app = QApplication(sys.argv)
    window = MainWindow(config, access_controller=None)
    window.setWindowTitle('QwinBot - Local Dev')
    window.set_subscription_status_text('Local dev mode: auth skipped')
    window.show()
    try:
        return app.exec()
    finally:
        window.shutdown()
if __name__ == '__main__':
    raise SystemExit(main())