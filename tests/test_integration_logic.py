import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot_core import BotCore
from src.internal_sniffer import QuinfallSniffer

class TestIntegrationLogic(unittest.TestCase):
    @patch('bot_core.QApplication')
    @patch('bot_core.BotMainWindow')
    @patch('bot_core.QTimer')
    def setUp(self, mock_timer, mock_ui, mock_app):
        self.core = BotCore()
        self.mock_ui = self.core.window

    def test_initialization(self):
        # Verify that refresh_interfaces was called during init
        self.mock_ui.iface_combo.clear.assert_called()
        self.mock_ui.iface_combo.addItems.assert_called()
        self.mock_ui.log.assert_called()

    @patch('bot_core.threading.Thread')
    def test_start_bot(self, mock_thread):
        # Mock selected interface
        self.mock_ui.iface_combo.currentText.return_value = "eth0"

        self.core.start_bot()

        # Verify thread was created with correct target and interface
        mock_thread.assert_called_once()
        args, kwargs = mock_thread.call_args
        self.assertEqual(kwargs['kwargs']['iface'], "eth0")
        self.mock_ui.status_label.setText.assert_called_with("Running")

    def test_packet_callback_updates_pos(self):
        # Mock data for a movement packet (simplified)
        # Using the same structure as gen_mock.py
        import struct
        payload = bytearray(100)
        payload[0:5] = bytes([0x01, 0x04, 0x00, 0x00, 0x00]) # TAG
        payload[9:13] = struct.pack("<I", 200) # Type
        pos = 20
        payload[pos:pos+5] = bytes([0x02, 0x04, 0x00, 0x00, 0x00]) # MARKER
        struct.pack_into("<f", payload, pos + 5, 123.45)
        struct.pack_into("<f", payload, pos + 14, 67.89)
        struct.pack_into("<f", payload, pos + 23, 10.11)
        struct.pack_into("<I", payload, pos + 26, 999)

        self.core.packet_callback(bytes(payload))

        self.assertEqual(self.core.player_pos['x'], 123.45)
        self.assertEqual(self.core.player_pos['id'], 999)

if __name__ == '__main__':
    unittest.main()
