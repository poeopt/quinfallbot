# Source Generated with Decompyle++
# File: go_to_farm_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import math
import time
from threading import Event
import cv2
import numpy as np
from mmobot.bot.compass_return_controller import CompassReturnController
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.input.game_window import GameWindowManager
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine

class GoToFarmController:
    
    def __init__(self, capture = None, vision = None, input_controller = None, config = ('capture', 'ScreenCapture', 'vision', 'VisionEngine', 'input_controller', 'InputController', 'config', 'AppConfig', 'return', 'None')):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.capture = capture
        self.vision = vision
        self.input = input_controller
        self.config = config
        self.window = GameWindowManager(config)
        self.compass = CompassReturnController(input_controller, config)
        self._previous_motion_signature = None
        self._last_progress_at = 0
        self._last_distance_value = None
        self._last_distance_progress_value = None
        self._last_distance_accept_at = 0
        self._last_distance_progress_at = 0
        self._plateau_anchor_distance = None
        self._plateau_anchor_started_at = 0
        self._distance_bootstrap_value = None
        self._distance_bootstrap_frames = 0
        self._start_distance_value = None
        self._recent_distance_values = []
        self._recent_enemy_counts = []
        self._arrival_close_frames = 0
        self._arrival_brake_frames = 0
        self._terminal_mode_active = False
        self._terminal_best_distance = None
        self._terminal_overshoot_detected = False
        self._terminal_confirm_frames = 0
        self._low_motion_frames = 0
        self._stuck_attempt = 0
        self._arrival_gate_frames = 0
        self._arrival_gate_open = False
        self._arrival_enemy_frames = 0
        self._last_marker_offset_abs = None
        self._last_marker_offset_signed = None
        self._smoothed_marker_offset_signed = None
        self._last_world_coords = None
        self._last_world_coords_at = 0
        self._last_world_progress_at = 0
        self._last_target_coord_error = None
        self._coord_velocity_x = 0
        self._coord_velocity_z = 0
        self._coord_forward_speed = 0
        self._coord_lateral_speed = 0
        self._coord_arrival_frames = 0
        self._stable_world_coords = None
        self._world_coord_candidate = None
        self._world_coord_candidate_frames = 0
        self._steer_direction = 0
        self._steer_hold_until = 0
        self._last_mouse_turn_at = 0
        self._last_mouse_turn_direction = 0
        self._post_recover_steer_settle_until = 0
        self._dock_pulse_until = 0
        self._dock_pulse_next_at = 0
        self._recover_lock_direction = 0
        self._recover_lock_until = 0
        self._recover_lock_reference_error = None
        self._recover_escape_direction = 0
        self._last_nav_source = 'idle'
        self._last_predictive_offset = None
        self._last_predictive_align = None
        self._last_predictive_improvement = None
        self._route_waypoints = []
        self._route_index = 0
        self._route_aligned = False
        self._route_reach_frames = 0
        self._route_pass_frames = 0
        self._route_best_distance = None

    
    def _sleep_interruptible(self = None, seconds = None, stop_event = None):
        end_time = time.monotonic() + max(0, seconds)
    # WARNING: Decompyle incomplete

    
    def _camera_probe_region(self = None, frame_shape = None, profile = None):
        (frame_h, frame_w) = frame_shape[:2]
        default = (0.25, 0.16, 0.5, 0.45)
        raw_region = profile.thresholds.get('go_to_farm_camera_probe_region', default)
        (x_ratio, y_ratio, w_ratio, h_ratio) = raw_region
    # WARNING: Decompyle incomplete

    
    def _frame_motion_score(self = None, before = None, after = None, region = ('before', 'np.ndarray', 'after', 'np.ndarray', 'region', 'tuple[int, int, int, int]', 'return', 'float')):
        (x, y, w, h) = region
        before_crop = before[(y:y + h, x:x + w)]
        after_crop = after[(y:y + h, x:x + w)]
        if before_crop.size == 0 or after_crop.size == 0:
            return 0
        before_gray = None.cvtColor(before_crop, cv2.COLOR_BGR2GRAY)
        after_gray = cv2.cvtColor(after_crop, cv2.COLOR_BGR2GRAY)
        before_small = cv2.resize(before_gray, (160, 90), interpolation = cv2.INTER_AREA)
        after_small = cv2.resize(after_gray, (160, 90), interpolation = cv2.INTER_AREA)
        return float(cv2.mean(cv2.absdiff(before_small, after_small))[0])

    
    def _probe_camera_motion(self = None, profile = None, stop_event = None):
        dx = int(profile.thresholds.get('go_to_farm_camera_probe_dx_px', 90))
        settle_s = float(profile.timeouts.get('go_to_farm_camera_probe_settle_seconds', 0.16))
        restore_s = float(profile.timeouts.get('go_to_farm_camera_probe_restore_seconds', 0.08))
        if dx == 0:
            return 0
        before = None.capture.grab_bgr()
        region = self._camera_probe_region(before.shape, profile)
        self.input.move_mouse_relative(dx, 0)
        if not self._sleep_interruptible(settle_s, stop_event):
            return None
        after = None.capture.grab_bgr()
        self.input.move_mouse_relative(-dx, 0)
        if not self._sleep_interruptible(restore_s, stop_event):
            return None
        return None._frame_motion_score(before, after, region)

    
    def _ensure_camera_control(self = None, profile = None, stop_event = None):
        enabled = bool(int(profile.thresholds.get('go_to_farm_camera_control_check_enabled', 1)))
        if not enabled:
            self.logger.info('Go to farm camera control check disabled')
            return True
        threshold = None(profile.thresholds.get('go_to_farm_camera_probe_min_score', 4))
        retry_delay_s = float(profile.timeouts.get('go_to_farm_post_y_delay_seconds', 0.2))
        attempts = max(1, int(profile.thresholds.get('go_to_farm_camera_probe_attempts', 2)))
    # WARNING: Decompyle incomplete

    
    def _reset_progress_tracking(self = None):
        self._previous_motion_signature = None
        now = time.monotonic()
        self._last_progress_at = now
        self._last_distance_value = None
        self._last_distance_progress_value = None
        self._last_distance_accept_at = 0
        self._last_distance_progress_at = now
        self._plateau_anchor_distance = None
        self._plateau_anchor_started_at = 0
        self._distance_bootstrap_value = None
        self._distance_bootstrap_frames = 0
        self._start_distance_value = None
        self._recent_distance_values = []
        self._recent_enemy_counts = []
        self._arrival_close_frames = 0
        self._arrival_brake_frames = 0
        self._terminal_mode_active = False
        self._terminal_best_distance = None
        self._terminal_overshoot_detected = False
        self._terminal_confirm_frames = 0
        self._low_motion_frames = 0
        self._stuck_attempt = 0
        self._arrival_gate_frames = 0
        self._arrival_gate_open = False
        self._arrival_enemy_frames = 0
        self._last_marker_offset_abs = None
        self._last_marker_offset_signed = None
        self._smoothed_marker_offset_signed = None
        self._last_world_coords = None
        self._last_world_coords_at = 0
        self._last_world_progress_at = now
        self._last_target_coord_error = None
        self._coord_velocity_x = 0
        self._coord_velocity_z = 0
        self._coord_forward_speed = 0
        self._coord_lateral_speed = 0
        self._coord_arrival_frames = 0
        self._stable_world_coords = None
        self._world_coord_candidate = None
        self._world_coord_candidate_frames = 0
        self._steer_direction = 0
        self._steer_hold_until = 0
        self._last_mouse_turn_at = 0
        self._last_mouse_turn_direction = 0
        self._post_recover_steer_settle_until = 0
        self._dock_pulse_until = 0
        self._dock_pulse_next_at = 0
        self._recover_lock_direction = 0
        self._recover_lock_until = 0
        self._recover_lock_reference_error = None
        self._recover_escape_direction = 0
        self._last_nav_source = 'idle'
        self._last_predictive_offset = None
        self._last_predictive_align = None
        self._last_predictive_improvement = None
        self._route_waypoints = []
        self._route_index = 0
        self._route_aligned = False
        self._route_reach_frames = 0
        self._route_pass_frames = 0
        self._route_best_distance = None
        self._coord_heading_rad = None
        self._coord_heading_confidence = 0
        self._coord_heading_at = 0
        self._coord_valid = False
        self._coord_validity_reason = 'init'
        self._coord_last_good_at = 0
        self._recent_coord_progress_at = 0
        self._nav_state = 'ALIGN'
        self._nav_state_since = 0
        self._route_transition_until = 0
        self._final_dwell_started_at = 0
        self._last_segment_metric = None
        self._last_segment_progress_at = 0

    
    def _load_route_waypoints(self = None, profile = None):
        waypoints = []
        route_data = profile.get_active_go_to_farm_route()
    # WARNING: Decompyle incomplete

    
    def _prepare_route(self = None, profile = None):
        now = time.monotonic()
        self._route_waypoints = self._load_route_waypoints(profile)
        self._route_index = 0
        self._route_aligned = False
        self._route_reach_frames = 0
        self._route_pass_frames = 0
        self._route_best_distance = None
        self._coord_heading_rad = None
        self._coord_heading_confidence = 0
        self._coord_heading_at = 0
        self._coord_valid = False
        self._coord_validity_reason = 'reset'
        self._coord_last_good_at = 0
        self._recent_coord_progress_at = now
        self._nav_state = 'ALIGN'
        self._nav_state_since = now
        self._route_transition_until = 0
        self._final_dwell_started_at = 0
        self._last_segment_metric = None
        self._last_segment_progress_at = now

    
    def _single_target_world_coordinates(self = None, profile = None):
        target_x = profile.thresholds.get('go_to_farm_target_x')
        target_z = profile.thresholds.get('go_to_farm_target_z')
    # WARNING: Decompyle incomplete

    
    def _route_target(self = None):
        if not self._route_waypoints:
            return None
        index = None(0, min(self._route_index, len(self._route_waypoints) - 1))
        return self._route_waypoints[index]

    
    def _route_previous_waypoint(self = None):
        if self._route_waypoints or self._route_index <= 0:
            return None
        return None._route_waypoints[self._route_index - 1]

    
    def _route_next_waypoint(self = None):
        if self._route_waypoints or self._route_index >= len(self._route_waypoints) - 1:
            return None
        return None._route_waypoints[self._route_index + 1]

    
    def _route_is_final(self = None):
        if bool(self._route_waypoints):
            pass
        return self._route_index >= len(self._route_waypoints) - 1

    
    def _route_hard_anchor_count(self = None, profile = None):
        if not self._route_waypoints:
            return 0
        configured = None(0, int(profile.thresholds.get('go_to_farm_route_hard_anchor_count', 3)))
        return min(len(self._route_waypoints), configured)

    
    def _route_in_hard_anchor_phase(self = None, profile = None):
        if bool(self._route_waypoints):
            pass
        return self._route_index < self._route_hard_anchor_count(profile)

    
    def _align_route_start(self = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _route_segment_metrics(self = None, start = None, end = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _route_segment_lookahead_target(self = None, start = None, end = None, profile = ('start', 'tuple[int, int | None, int] | None', 'end', 'tuple[int, int | None, int] | None', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int | None, int] | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _route_guidance_target(self = None, profile = None):
        current_target = self._route_target()
    # WARNING: Decompyle incomplete

    
    def _try_advance_route(self = None, snapshot = None, profile = None):
        if self._route_waypoints or self._route_is_final():
            self._route_reach_frames = 0
            self._route_pass_frames = 0
            self._route_best_distance = None
            return False
        coord_error = None._final_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _target_world_coordinates(self = None, profile = None):
        route_target = self._route_guidance_target(profile)
    # WARNING: Decompyle incomplete

    
    def _final_world_coordinates(self = None, profile = None):
        route_target = self._route_target()
    # WARNING: Decompyle incomplete

    
    def _target_coord_error(self = None, snapshot = None, profile = None):
        target = self._target_world_coordinates(profile)
        current_world = self._stable_world_coords
    # WARNING: Decompyle incomplete

    
    def _route_coord_error(self = None, snapshot = None, profile = None):
        target = self._final_world_coordinates(profile)
        current_world = self._stable_world_coords
    # WARNING: Decompyle incomplete

    
    def _final_coord_error(self = None, snapshot = None, profile = None):
        target = self._final_world_coordinates(profile)
        current_world = self._stable_world_coords
    # WARNING: Decompyle incomplete

    
    def _steering_coord_error(self = None, coord_error = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    _wrap_angle_rad = (lambda angle = None: float((angle + math.pi) % 2 * math.pi - math.pi))()
    
    def _set_coord_validity(self = None, valid = None, reason = None):
        if self._coord_valid == valid and self._coord_validity_reason == reason:
            return None
        self._coord_valid = None
        self._coord_validity_reason = reason
        if valid:
            self._coord_last_good_at = time.monotonic()
        self.logger.info('Go to farm coord validity: valid=%s reason=%s', valid, reason)

    
    def _read_validated_coordinates(self = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _estimate_heading(self = None, snapshot = None, profile = None):
        now = time.monotonic()
        speed = float(np.hypot(self._coord_velocity_x, self._coord_velocity_z))
        min_speed = float(profile.thresholds.get('go_to_farm_heading_min_speed_units_per_s', profile.thresholds.get('go_to_farm_coord_heading_min_speed_units_per_s', 3.5)))
        smoothing_alpha = float(profile.thresholds.get('go_to_farm_heading_smoothing_alpha', 0.38))
        hold_timeout_s = float(profile.timeouts.get('go_to_farm_heading_hold_timeout_sec', 0.9))
        minimap_heading_confidence_min = float(profile.thresholds.get('go_to_farm_coord_heading_confidence_min', 0.12))
    # WARNING: Decompyle incomplete

    
    def _compute_heading_error(self = None, snapshot = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _set_navigation_state(self, state = None, reason = None, heading_error_deg = None, target_distance = ('state', 'str', 'reason', 'str', 'heading_error_deg', 'float | None', 'target_distance', 'float | None', 'return', 'None')):
        if self._nav_state == state:
            return None
    # WARNING: Decompyle incomplete

    
    def _select_navigation_state(self, snapshot = None, profile = None, route_intermediate = None, terminal_mode_active = ('profile', 'CalibrationProfile', 'route_intermediate', 'bool', 'terminal_mode_active', 'bool', 'return', 'tuple[str, tuple[float, float, float, float, float] | None, float | None]')):
        target_error = self._target_coord_error(snapshot, profile)
        final_error = self._final_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _apply_heading_turn(self = None, state = None, heading_error_deg = None, profile = ('state', 'str', 'heading_error_deg', 'float | None', 'profile', 'CalibrationProfile', 'return', 'None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _update_segment_progress(self = None, snapshot = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _is_stuck_from_segment_progress(self = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _coord_in_dock_zone(self = None, snapshot = None, profile = None):
        coord_error = self._route_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _compute_predictive_coord_offset(self = None, snapshot = None, profile = None):
        if not bool(profile.thresholds.get('go_to_farm_use_predictive_steering', 0)):
            self._last_predictive_offset = None
            self._last_predictive_align = None
            self._last_predictive_improvement = None
            return (None, None, None)
        target_error = None._steering_coord_error(self._target_coord_error(snapshot, profile), profile)
    # WARNING: Decompyle incomplete

    
    def _apply_coordinate_navigation(self = None, snapshot = None, profile = None, terminal_mode_active = ('profile', 'CalibrationProfile', 'terminal_mode_active', 'bool', 'return', 'tuple[bool, float | None, float | None, bool]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _observe_world_coords(self = None, snapshot = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _accept_distance_value(self = None, distance_value = None, now = None, profile = ('distance_value', 'int', 'now', 'float', 'profile', 'CalibrationProfile', 'return', 'int')):
        self._last_distance_value = distance_value
        self._last_distance_accept_at = now
    # WARNING: Decompyle incomplete

    
    def _filter_distance_value(self = None, raw_distance = None, enemy_count = None, profile = ('raw_distance', 'int | None', 'enemy_count', 'int', 'profile', 'CalibrationProfile', 'return', 'int | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _update_arrival_enemy_gate(self = None, snapshot = None, profile = None, arrival_gate_open = ('profile', 'CalibrationProfile', 'arrival_gate_open', 'bool', 'return', 'bool')):
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 2)))
        confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_confirm_frames', 2)))
        if not snapshot.nearby_enemy_count:
            enemy_count = max(len(snapshot.minimap_enemies), int(0))
            if arrival_gate_open and enemy_count >= enemy_min_count:
                pass
            else:
                0 = self, self._arrival_enemy_frames += 1, ._arrival_enemy_frames
        return self._arrival_enemy_frames >= confirm_frames

    
    def _has_arrival_enemy_support(self = None, profile = None, enemy_count = None):
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 2)))
        return max(enemy_count, self._recent_enemy_peak(profile)) >= enemy_min_count

    
    def _update_distance_plateau(self = None, snapshot = None, profile = None):
        distance_value = snapshot.distance_value
    # WARNING: Decompyle incomplete

    
    def _update_arrival_settle_tracking(self = None, snapshot = None, profile = None, enemy_count = ('profile', 'CalibrationProfile', 'enemy_count', 'int', 'return', 'None')):
        history_size = max(6, int(profile.thresholds.get('go_to_farm_arrival_enemy_window_frames', 16)))
        self._recent_enemy_counts.append(enemy_count)
        if len(self._recent_enemy_counts) > history_size:
            self._recent_enemy_counts = self._recent_enemy_counts[-history_size:]
        distance_value = snapshot.distance_value
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
        settle_distance = float(profile.thresholds.get('go_to_farm_arrival_settle_distance_m', 6))
        centered = False
    # WARNING: Decompyle incomplete

    
    def _update_arrival_brake_tracking(self = None, snapshot = None, profile = None):
        distance_value = snapshot.distance_value
        coord_error = self._route_coord_error(snapshot, profile)
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
    # WARNING: Decompyle incomplete

    
    def _update_terminal_mode(self = None, snapshot = None, profile = None, enemy_count = ('profile', 'CalibrationProfile', 'enemy_count', 'int', 'return', 'tuple[bool, bool, bool]')):
        distance_value = snapshot.distance_value
        coord_error = self._route_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _recent_enemy_peak(self = None, profile = None):
        history_size = max(6, int(profile.thresholds.get('go_to_farm_arrival_enemy_window_frames', 16)))
        if not self._recent_enemy_counts:
            return 0
        return None(self._recent_enemy_counts[-history_size:])

    
    def _update_arrival_gate(self = None, snapshot = None, profile = None, enemy_count = ('profile', 'CalibrationProfile', 'enemy_count', 'int', 'return', 'bool')):
        arm_distance = float(profile.thresholds.get('go_to_farm_arrival_arm_distance_m', 80))
        arm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_arm_confirm_frames', 3)))
        reset_distance = float(profile.thresholds.get('go_to_farm_arrival_gate_reset_distance_m', 160))
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3)))
        enemy_support = max(enemy_count, self._recent_enemy_peak(profile)) >= enemy_min_count
        distance = snapshot.distance_value
    # WARNING: Decompyle incomplete

    
    def _arrival_distance_stable(self = None, profile = None):
        stable_frames = max(2, int(profile.thresholds.get('go_to_farm_arrival_stable_confirm_frames', 4)))
        if len(self._recent_distance_values) < stable_frames:
            return False
        recent_values = None._recent_distance_values[-stable_frames:]
        stable_max_distance = float(profile.thresholds.get('go_to_farm_arrival_stable_max_distance_m', 18))
        stable_variation = float(profile.thresholds.get('go_to_farm_arrival_stable_variation_m', 14))
        if recent_values[-1] > stable_max_distance:
            return False
        return None(recent_values) - min(recent_values) <= stable_variation

    
    def _arrival_completion_ready(self, snapshot, profile, started_at = None, enemy_count = None, arrival_gate_open = None, arrival_enemy_open = ('profile', 'CalibrationProfile', 'started_at', 'float', 'enemy_count', 'int', 'arrival_gate_open', 'bool', 'arrival_enemy_open', 'bool', 'return', 'bool')):
        distance_value = snapshot.distance_value
    # WARNING: Decompyle incomplete

    
    def _arrival_settle_ready(self = None, profile = None, started_at = None):
        min_runtime_s = float(profile.timeouts.get('go_to_farm_min_arrival_runtime_seconds', 50))
        if time.monotonic() - started_at < min_runtime_s:
            return False
        settle_confirm_frames = None(2, int(profile.thresholds.get('go_to_farm_arrival_settle_confirm_frames', 5)))
        if self._arrival_close_frames < settle_confirm_frames:
            return False
        required_enemy_count = None(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3))))
        if self._recent_enemy_peak(profile) < required_enemy_count:
            return False

    
    def _coord_arrival_ready(self, snapshot = None, profile = None, marker_offset = None, move_forward = ('profile', 'CalibrationProfile', 'marker_offset', 'float | None', 'move_forward', 'bool', 'return', 'bool')):
        coord_error = self._route_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _coord_settled_nearby(self = None, snapshot = None, profile = None):
        coord_error = self._route_coord_error(snapshot, profile)
    # WARNING: Decompyle incomplete

    
    def _confirm_arrival_after_stop(self = None, profile = None, stop_event = None):
        self.compass.stop()
        self.input.safe_release_all()
        verify_delay_s = float(profile.timeouts.get('go_to_farm_arrival_verify_delay_seconds', 0.35))
        if not self._sleep_interruptible(verify_delay_s, stop_event):
            return False
        frame = None.capture.grab_bgr()
        snapshot = self.vision.analyze(frame, profile, include_distance = True, include_world_coords = True, include_inventory = False)
        if not snapshot.nearby_enemy_count:
            enemy_count = max(len(snapshot.minimap_enemies), int(0))
            snapshot.distance_value = self._filter_distance_value(snapshot.distance_value, enemy_count, profile)
            verify_distance = float(profile.thresholds.get('go_to_farm_arrival_verify_distance_m', 10))
            enemy_recent_min = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3))))
            enemy_peak = max(enemy_count, self._recent_enemy_peak(profile))
            terminal_confirm_distance = float(profile.thresholds.get('go_to_farm_terminal_confirm_distance_m', 10))
            if self._terminal_best_distance is not None:
                terminal_confirmed = self._terminal_best_distance <= terminal_confirm_distance
                coord_error = self._target_coord_error(snapshot, profile)
                coord_verify_distance = float(profile.thresholds.get('go_to_farm_final_radius', 10))
                coord_verify_axis = float(profile.thresholds.get('go_to_farm_final_axis_units', coord_verify_distance))
                if coord_error is not None:
                    if coord_error[3] <= coord_verify_distance:
                        coord_confirmed = max(abs(coord_error[0]), abs(coord_error[2])) <= coord_verify_axis
                        if coord_confirmed and self._coord_settled_nearby(snapshot, profile):
                            coord_confirmed = True
    # WARNING: Decompyle incomplete

    
    def _abort_if_stopped(self = None, stop_event = None):
        if not stop_event.is_set():
            return False
        None.compass.stop()
        self.input.safe_release_all()
        return True

    
    def _run_initial_departure(self = None, profile = None, stop_event = None):
        total_dx = int(profile.thresholds.get('go_to_farm_initial_turn_mouse_dx', -540))
        turn_steps = max(1, int(profile.thresholds.get('go_to_farm_initial_turn_steps', 6)))
        step_pause_s = float(profile.timeouts.get('go_to_farm_initial_turn_step_pause_seconds', 0.05))
        run_seconds = float(profile.timeouts.get('go_to_farm_initial_run_seconds', 5))
        settle_s = float(profile.timeouts.get('go_to_farm_initial_settle_seconds', 0.1))
        step_dx = int(round(total_dx / turn_steps))
        self.logger.info('Go to farm initial departure: total_dx=%s steps=%s run_seconds=%.1f', total_dx, turn_steps, run_seconds)
        for _ in range(turn_steps):
            if stop_event.is_set():
                return False
            None.input.move_mouse_relative(step_dx, 0)
            if not self._sleep_interruptible(step_pause_s, stop_event):
                return False
            self.input.press_key('W')
            self.input.press_key('SHIFT')
            if not self._sleep_interruptible(run_seconds, stop_event):
                return False
            None.input.release_key('W')
            self.input.release_key('SHIFT')
            return self._sleep_interruptible(settle_s, stop_event)

    
    def _motion_signature(self = None, frame = None, profile = None):
        (frame_h, frame_w) = frame.shape[:2]
        x_ratio = float(profile.thresholds.get('go_to_farm_motion_region_x_ratio', 0.34))
        y_ratio = float(profile.thresholds.get('go_to_farm_motion_region_y_ratio', 0.2))
        w_ratio = float(profile.thresholds.get('go_to_farm_motion_region_w_ratio', 0.32))
        h_ratio = float(profile.thresholds.get('go_to_farm_motion_region_h_ratio', 0.24))
        x = int(frame_w * x_ratio)
        y = int(frame_h * y_ratio)
        w = int(frame_w * w_ratio)
        h = int(frame_h * h_ratio)
        x = max(0, min(frame_w - 1, x))
        y = max(0, min(frame_h - 1, y))
        w = max(1, min(frame_w - x, w))
        h = max(1, min(frame_h - y, h))
        crop = frame[(y:y + h, x:x + w)]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.resize(gray, (96, 72), interpolation = cv2.INTER_AREA)

    
    def _update_progress_tracking(self, frame = None, snapshot = None, profile = None, distance_actionable = ('frame', 'np.ndarray', 'profile', 'CalibrationProfile', 'distance_actionable', 'bool', 'return', 'tuple[float, bool, bool, bool]')):
        now = time.monotonic()
        motion_signature = self._motion_signature(frame, profile)
        motion_score = 0
        progress = False
        distance_progress = False
        coord_progress = False
        motion_threshold = float(profile.thresholds.get('go_to_farm_motion_diff_threshold', 3.8))
        strong_motion_threshold = float(profile.thresholds.get('go_to_farm_motion_strong_progress_threshold', motion_threshold * 2.2))
        coord_visual_motion_threshold = float(profile.thresholds.get('go_to_farm_coord_visual_motion_progress_threshold', strong_motion_threshold))
        low_motion_threshold = float(profile.thresholds.get('go_to_farm_low_motion_threshold', 2))
        distance_step = int(profile.thresholds.get('go_to_farm_distance_progress_step', 2))
        coord_progress_step = int(profile.thresholds.get('go_to_farm_coord_progress_step_units', 4))
        coord_progress_soft_step = float(profile.thresholds.get('go_to_farm_coord_progress_soft_step_units', 1.2))
        coord_jump_max = int(profile.thresholds.get('go_to_farm_coord_jump_max_units', 120))
        coord_velocity_alpha = float(profile.thresholds.get('go_to_farm_coord_velocity_ema_alpha', 0.45))
        coord_forward_progress_threshold = float(profile.thresholds.get('go_to_farm_coord_forward_progress_units_per_s', 0.75))
        marker_progress_step = float(profile.thresholds.get('go_to_farm_marker_progress_step_px', 10))
        marker_progress_near_center_px = float(profile.thresholds.get('go_to_farm_marker_progress_near_center_px', 42))
        marker_progress = False
    # WARNING: Decompyle incomplete

    
    def _recover_from_stuck(self = None, snapshot = None, profile = None, stop_event = ('profile', 'CalibrationProfile', 'stop_event', 'Event', 'return', 'bool')):
        if self._abort_if_stopped(stop_event):
            return False
        None._set_navigation_state('RECOVERY', 'stuck-trigger', None, None)
        float(profile.timeouts.get('go_to_farm_recover_back_seconds', 0.45)) = self, self._stuck_attempt += 1, ._stuck_attempt
        strafe_seconds = float(profile.timeouts.get('go_to_farm_recover_strafe_seconds', 0.4))
        settle_seconds = float(profile.timeouts.get('go_to_farm_recover_settle_seconds', 0.2))
        turn_dx = int(profile.thresholds.get('go_to_farm_recover_turn_dx', 160))
        aligned_offset_px = float(profile.thresholds.get('go_to_farm_recover_aligned_offset_px', 22))
        aligned_no_turn_attempts = max(0, int(profile.thresholds.get('go_to_farm_recover_aligned_no_turn_attempts', 2)))
        aligned_turn_dx = int(profile.thresholds.get('go_to_farm_recover_aligned_turn_dx', 72))
        marker_turn_gain = float(profile.thresholds.get('go_to_farm_recover_marker_turn_gain', 0.55))
        strength_scale = min(2.4, 1 + 0.35 * max(0, self._stuck_attempt - 1))
        back_seconds *= min(1.9, strength_scale)
        strafe_seconds *= min(2.2, strength_scale)
        turn_dx = int(round(turn_dx * min(2.6, 1 + 0.45 * max(0, self._stuck_attempt - 1))))
        self.logger.info('Go to farm anti-stuck attempt=%s distance=%s marker=%s', self._stuck_attempt, snapshot.distance_value, snapshot.compass_marker)
        self.input.release_key('A')
        self.input.release_key('D')
        self.input.release_key('W')
        self.input.release_key('SHIFT')
        self.input.press_key('S')
        if not self._sleep_interruptible(back_seconds, stop_event):
            return False
        None.input.release_key('S')
        raw_offset_x = None
        aligned_recover = False
        direction = -1 if self._recover_escape_direction or self._stuck_attempt % 2 == 1 else 1
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
        target_coord_error = self._final_coord_error(snapshot, profile)
        coord_heading_min_speed = float(profile.thresholds.get('go_to_farm_coord_heading_min_speed_units_per_s', 3.5))
        coord_heading_cross_deadzone = float(profile.thresholds.get('go_to_farm_coord_heading_cross_deadzone', 0.05))
        coord_heading_speed = float(np.hypot(self._coord_velocity_x, self._coord_velocity_z))
    # WARNING: Decompyle incomplete

    
    def go_to_farm(self = None, profile = None, stop_event = None):
        start_delay_s = float(profile.timeouts.get('go_to_farm_start_delay_seconds', 5))
        timeout_s = float(profile.timeouts.get('go_to_farm_timeout_seconds', 1800))
        log_every_s = float(profile.timeouts.get('go_to_farm_status_log_seconds', 5))
        stuck_seconds = float(profile.timeouts.get('go_to_farm_stuck_seconds', 5))
        if self._abort_if_stopped(stop_event):
            self.compass.stop()
            self.input.safe_release_all()
            return False
        None.window.focus_game_window('go-to-farm')
        self.input.safe_release_all()
        if not self._ensure_camera_control(profile, stop_event):
            self.compass.stop()
            self.input.safe_release_all()
            return False
        None.input.tap_key('P', hold_s = 0.06)
        self.logger.info('Go to farm started: pressed P, waiting %.1fs before run', start_delay_s)
        if not self._sleep_interruptible(start_delay_s, stop_event):
            self.compass.stop()
            self.input.safe_release_all()
            return False
        use_initial_departure = None(profile.thresholds.get('go_to_farm_use_initial_departure', 0))
        if not use_initial_departure and self._run_initial_departure(profile, stop_event):
            self.compass.stop()
            self.input.safe_release_all()
            return False
        None.compass.reset()
        self._reset_progress_tracking()
        self._prepare_route(profile)
        route_target = self._route_target()
    # WARNING: Decompyle incomplete


