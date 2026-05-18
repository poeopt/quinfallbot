# Source Generated with Decompyle++
# File: compass_return_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import math
import time
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionSnapshot

class CompassReturnController:
    
    def __init__(self = None, input_controller = None, config = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.input = input_controller
        self.config = config
        self.arrival_frames = 0
        self.centered_frames = 0
        self.started_at = 0
        self.marker_seen_frames = 0
        self.off_center_started_at = 0
        self._route_log_at = 0

    
    def reset(self = None):
        self.arrival_frames = 0
        self.centered_frames = 0
        self.started_at = time.monotonic()
        self.marker_seen_frames = 0
        self.off_center_started_at = 0
        self._route_log_at = 0

    _wrap_angle_rad = (lambda angle = None: float((angle + math.pi) % 2 * math.pi - math.pi))()
    
    def _update_internal(self, snapshot, profile, arrival_distance, confirm_frames, fast_arrival_distance, fast_confirm_frames = None, min_return_s = None, centered_arrival_enabled = None, centered_confirm_frames = (True,), distance_gate_open = ('snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'arrival_distance', 'float', 'confirm_frames', 'int', 'fast_arrival_distance', 'float', 'fast_confirm_frames', 'int', 'min_return_s', 'float', 'centered_arrival_enabled', 'bool', 'centered_confirm_frames', 'int', 'distance_gate_open', 'bool', 'return', 'bool')):
        if self.started_at <= 0:
            self.started_at = time.monotonic()
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
    # WARNING: Decompyle incomplete

    
    def update(self = None, snapshot = None, profile = None):
        arrival_distance = float(profile.thresholds.get('arrival_distance', 8))
        confirm_frames = max(1, int(profile.thresholds.get('arrival_confirm_frames', 8)))
        fast_arrival_distance = float(profile.thresholds.get('return_fast_arrival_distance', 10))
        fast_confirm_frames = max(1, int(profile.thresholds.get('return_fast_arrival_confirm_frames', 2)))
        centered_confirm_frames = int(profile.thresholds.get('return_centered_confirm_frames', confirm_frames * 3))
        centered_arrival_enabled = bool(profile.thresholds.get('return_allow_centered_arrival_without_distance', 0))
        min_return_s = float(profile.timeouts.get('return_min_seconds_before_arrival', 8))
        return self._update_internal(snapshot = snapshot, profile = profile, arrival_distance = arrival_distance, confirm_frames = confirm_frames, fast_arrival_distance = fast_arrival_distance, fast_confirm_frames = fast_confirm_frames, min_return_s = min_return_s, centered_arrival_enabled = centered_arrival_enabled, centered_confirm_frames = centered_confirm_frames)

    
    def update_long(self = None, snapshot = None, profile = None, distance_gate_open = ('snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'distance_gate_open', 'bool', 'return', 'bool')):
        arrival_distance = float(profile.thresholds.get('arrival_distance', 8))
        confirm_frames = max(1, int(profile.thresholds.get('arrival_confirm_frames', 8)))
        fast_arrival_distance = float(profile.thresholds.get('return_fast_arrival_distance', 10))
        fast_confirm_frames = max(1, int(profile.thresholds.get('return_fast_arrival_confirm_frames', 2)))
        min_return_s = float(profile.timeouts.get('return_min_seconds_before_arrival', 8))
        return self._update_internal(snapshot = snapshot, profile = profile, arrival_distance = arrival_distance, confirm_frames = confirm_frames, fast_arrival_distance = fast_arrival_distance, fast_confirm_frames = fast_confirm_frames, min_return_s = min_return_s, centered_arrival_enabled = False, centered_confirm_frames = 0, distance_gate_open = distance_gate_open)

    
    def update_home(self = None, snapshot = None, profile = None):
        arrival_distance = float(profile.thresholds.get('gather_home_arrival_distance', 10))
        confirm_frames = max(1, int(profile.thresholds.get('gather_home_arrival_confirm_frames', 3)))
        fast_arrival_distance = arrival_distance
        fast_confirm_frames = confirm_frames
        centered_confirm_frames = max(2, int(profile.thresholds.get('gather_home_center_confirm_frames', 5)))
        centered_arrival_enabled = True
        return self._update_internal(snapshot = snapshot, profile = profile, arrival_distance = arrival_distance, confirm_frames = confirm_frames, fast_arrival_distance = fast_arrival_distance, fast_confirm_frames = fast_confirm_frames, min_return_s = 0, centered_arrival_enabled = centered_arrival_enabled, centered_confirm_frames = centered_confirm_frames)

    
    def update_route_target(self, snapshot = None, profile = None, target_x = None, target_z = ('snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'target_x', 'int', 'target_z', 'int', 'return', 'bool')):
        if self.started_at <= 0:
            self.started_at = time.monotonic()
        arrival_radius = float(profile.thresholds.get('return_route_arrival_radius', 12))
        arrival_axis = float(profile.thresholds.get('return_route_arrival_axis', arrival_radius))
        confirm_frames = max(1, int(profile.thresholds.get('return_route_arrival_confirm_frames', 3)))
        sprint_threshold_deg = float(profile.thresholds.get('return_route_heading_sprint_threshold_deg', 14))
        align_threshold_deg = float(profile.thresholds.get('return_route_heading_align_threshold_deg', 34))
        turn_in_place_threshold_deg = float(profile.thresholds.get('return_route_heading_turn_in_place_threshold_deg', 70))
        deadzone_deg = float(profile.thresholds.get('return_route_heading_deadzone_deg', 2))
        turn_gain = float(profile.thresholds.get('return_route_heading_turn_gain_px_per_deg', 1.05))
        turn_min_dx = int(profile.thresholds.get('return_route_heading_turn_min_dx', 4))
        turn_max_dx = int(profile.thresholds.get('return_route_heading_turn_max_dx', 42))
        min_return_s = float(profile.timeouts.get('return_min_seconds_before_arrival', 1))
        world_x = snapshot.world_x
        world_z = snapshot.world_z
    # WARNING: Decompyle incomplete

    
    def stop(self = None):
        self.off_center_started_at = 0
        self.input.release_key('W')
        self.input.release_key('SHIFT')


