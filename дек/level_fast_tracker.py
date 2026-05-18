# Source Generated with Decompyle++
# File: level_fast_tracker.pyc (Python 3.11)

from __future__ import annotations
import logging
import threading
import time
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import LevelFastSnapshot, VisionEngine

class LevelFastTracker:
    
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
        self._last_target_point = None
        self._miss_streak = 0
        self._tick_index = 0

    
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
        level_spec = self.profile.zones.get('lvl_mob_region')
        level_rect = level_spec.as_pixels(self.profile.screen_size) if level_spec else None
    # WARNING: Decompyle incomplete


