# Source Generated with Decompyle++
# File: vendor_sell_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import math
import time
from pathlib import Path
from threading import Event
import cv2
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.input.game_window import GameWindowManager
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine

class VendorSellController:
    VENDOR_TEXTS = ('Weaponsmith', 'Оружейник')
    SELL_TEXTS = ('Sell', 'Продать')
    FILL_TEXTS = ('Fill from inventory', 'Fill from Inventory', 'Заполнить из инвентаря')
    OCR_LANG_SEQUENCE = ('eng', 'rus')
    VENDOR_TEXT = VENDOR_TEXTS[0]
    SELL_TEXT = SELL_TEXTS[0]
    FILL_TEXT = FILL_TEXTS[0]
    
    def __init__(self, capture = None, vision = None, input_controller = None, config = ('capture', 'ScreenCapture', 'vision', 'VisionEngine', 'input_controller', 'InputController', 'config', 'AppConfig', 'return', 'None')):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.capture = capture
        self.vision = vision
        self.input = input_controller
        self.window = GameWindowManager(config)
        self.log_dir = config.log_dir
        self.map_dir = config.base_dir / 'map'
        self._allow_sell_tab_only_confirm = False
        self.vendor_templates = self._load_template_assets((self.map_dir / 'weaapon.png', self.map_dir / 'weapon2.png', self.map_dir / 'Weapon_shop.png'))
        self.vendor_template = self.vendor_templates[0] if self.vendor_templates else None
        self.interact_template = self._load_template_asset(self.map_dir / 'E_shop.png')
        self.sell_tab_template = self._load_template_asset(self.map_dir / 'sell_up.png')
        self.fill_button_template = self._load_template_asset(self.map_dir / 'inventar_sell.png')
        self.sell_button_template = self._load_template_asset(self.map_dir / 'sell_down.png')
        self._vendor_coord_log_at = 0
        self._vendor_near_search_direction = 1
        self._vendor_near_search_flip_at = 0
        self._vendor_near_search_next_walk_at = 0
        self._vendor_local_search_direction = 1
        self._vendor_local_search_flip_at = 0
        self._vendor_local_search_next_walk_at = 0

    
    def _sleep_interruptible(self = None, seconds = None, stop_event = None):
        end_time = time.monotonic() + max(0, seconds)
    # WARNING: Decompyle incomplete

    
    def _prepare_vendor_view(self = None, profile = None, stop_event = None):
