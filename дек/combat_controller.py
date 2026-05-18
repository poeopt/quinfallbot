# Source Generated with Decompyle++
# File: combat_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from mmobot.bot.cooldown_tracker import CooldownTracker
from mmobot.input.game_window import GameWindowManager
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import EnemyBodyTarget, EnemyHpTarget, EnemyLevelTarget, VisionSnapshot
from mmobot.vision.monster_nn_detector import MonsterNnTarget
CombatTargetTrack = <NODE:12>()

class CombatController:
    
    def __init__(self = None, input_controller = None, cooldowns = None, config = ('input_controller', 'InputController', 'cooldowns', 'CooldownTracker', 'config', 'AppConfig', 'return', 'None')):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.input = input_controller
        self.cooldowns = cooldowns
        self.config = config
        self.window_manager = GameWindowManager(config)
        self.target_history = deque(maxlen = 6)
        self.absence_history = deque(maxlen = 20)
        self.absence_started_at = 0
        self.scan_turns_done = 0
        self.last_scan_time = 0
        self.last_acquire_time = 0
        self.last_confirmed_time = 0
        self.last_enemy_presence_time = 0
        self.last_actionable_presence_time = 0
        self.last_attack_stop_time = 0
        self.last_skill_2_turn_time = 0
        self.last_behind_turn_time = 0
        self.attack_started_at = 0
        self.acquire_index = 0
        self.vertical_offset_y = 0
        self.acquire_pattern = [
            (40, 0),
            (-80, 0),
            (120, 0),
            (-160, 0),
            (220, 0),
            (-260, 0)]
        self.close_acquire_pattern = [
            (18, 12),
            (-28, 12),
            (40, 14),
            (-56, 14),
            (78, 10),
            (-104, 8)]
        self.attack_active = False
        self.last_minimap_turn_direction = 0
        self.last_minimap_acquire_time = 0
        self.target_track = CombatTargetTrack()
        self.last_track_log_at = 0
        self.last_attack_hold_log_at = 0
        self.post_skill_2_recovery_turn_direction = 0
        self.post_skill_2_direction_lock_until = 0
        self.last_level_acquire_dx = 0
        self.last_level_acquire_dy = 0
        self.last_level_acquire_at = 0
        self.attack_motion_history = deque(maxlen = 12)
        self.last_attack_motion_distance = 0
        self.last_behind_reason = 'none'

    minimap_support_enabled = (lambda profile = None: float(profile.thresholds.get('combat_enable_minimap_support', 0)) > 0.5)()
    level_only_targeting_enabled = (lambda profile = None: float(profile.thresholds.get('combat_level_only_targeting', 1)) > 0.5)()
    
    def reset(self = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def note_enemy_presence(self = None, actionable = None):
        now = time.monotonic()
        self.last_enemy_presence_time = now
        if actionable:
            self.last_actionable_presence_time = now
        self.scan_turns_done = 0
        self.absence_history.clear()
        self.absence_started_at = 0
        if actionable or self.target_track.last_seen_at > 0:
            self.target_track.last_confirmed_at = now
            return None
        return None

    
    def _track_hold_seconds(self = None, profile = None):
        return float(profile.timeouts.get('combat_track_hold_seconds', 1.25))

    
    def _track_cleanup_hold_seconds(self = None, profile = None):
        return float(profile.timeouts.get('combat_track_cleanup_hold_seconds', max(self._track_hold_seconds(profile), 1.8)))

    
    def _track_confirmed_hold_seconds(self = None, profile = None):
        return float(profile.timeouts.get('combat_track_confirmed_hold_seconds', max(self._track_cleanup_hold_seconds(profile), self._track_hold_seconds(profile) + 1)))

    
    def _post_skill_2_hold_seconds(self = None, profile = None):
        return float(profile.timeouts.get('combat_post_skill_2_hold_attack_seconds', max(1.6, profile.timeouts.get('combat_hold_attack_seconds', 0.9) * 2)))

    
    def _is_post_skill_2_recovery(self = None, profile = None):
        if self.last_skill_2_turn_time <= 0:
            return False
        return None.monotonic() - self.last_skill_2_turn_time <= self._post_skill_2_hold_seconds(profile)

    
    def _update_attack_motion_history(self = None, snapshot = None, profile = None):
        window_s = float(profile.timeouts.get('combat_attack_motion_behind_window_seconds', 0.9))
        post_attack_hold_s = float(profile.timeouts.get('combat_attack_motion_post_attack_hold_seconds', min(1.4, max(0.6, window_s))))
        now = time.monotonic()
        cutoff = now - max(0.2, window_s)
    # WARNING: Decompyle incomplete

    
    def _front_target_is_close(self = None, snapshot = None, profile = None):
        aim_center = self._current_aim_center(profile)
    # WARNING: Decompyle incomplete

    
    def _attack_motion_suggests_target_behind(self = None, snapshot = None, profile = None):
