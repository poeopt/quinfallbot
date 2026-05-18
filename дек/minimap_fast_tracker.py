# Source Generated with Decompyle++
# File: minimap_fast_tracker.pyc (Python 3.11)

from __future__ import annotations
import logging
import threading
import time
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import MinimapFastSnapshot, VisionEngine

class MinimapFastTracker:
    
    def __init__(self = None, config = None, profile = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.profile = profile
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest = None
        self._perf_last_log_at = 0
        self._perf_tick_count = 0
        self._perf_processing_ms_sum = 0
        self._backend_name = 'mss'

    
    def start(self = None):
        pass
    # WARNING: Decompyle incomplete

    
    def stop(self = None):
        self._stop_event.set()
    # WARNING: Decompyle incomplete

    
    def get_latest(self = None, max_age_s = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _run(self = None):
        capture = None
        minimap_spec = self.profile.zones.get('minimap_region')
        minimap_rect = minimap_spec.as_pixels(self.profile.screen_size) if minimap_spec else None
    # WARNING: Decompyle incomplete


