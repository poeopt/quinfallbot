# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\bot\\go_to_farm_controller.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

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
    def __init__(self, capture: ScreenCapture, vision: VisionEngine, input_controller: InputController, config: AppConfig) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.capture = capture
        self.vision = vision
        self.input = input_controller
        self.config = config
        self.window = GameWindowManager(config)
        self.compass = CompassReturnController(input_controller, config)
        self._previous_motion_signature = None
        self._last_progress_at = 0.0
        self._last_distance_value = None
        self._last_distance_progress_value = None
        self._last_distance_accept_at = 0.0
        self._last_distance_progress_at = 0.0
        self._plateau_anchor_distance = None
        self._plateau_anchor_started_at = 0.0
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
        self._last_world_coords_at = 0.0
        self._last_world_progress_at = 0.0
        self._last_target_coord_error = None
        self._coord_velocity_x = 0.0
        self._coord_velocity_z = 0.0
        self._coord_forward_speed = 0.0
        self._coord_lateral_speed = 0.0
        self._coord_arrival_frames = 0
        self._stable_world_coords = None
        self._world_coord_candidate = None
        self._world_coord_candidate_frames = 0
        self._steer_direction = 0
        self._steer_hold_until = 0.0
        self._last_mouse_turn_at = 0.0
        self._last_mouse_turn_direction = 0
        self._post_recover_steer_settle_until = 0.0
        self._dock_pulse_until = 0.0
        self._dock_pulse_next_at = 0.0
        self._recover_lock_direction = 0
        self._recover_lock_until = 0.0
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
    def _sleep_interruptible(self, seconds: float, stop_event: Event) -> bool:
        end_time = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end_time:
            if stop_event.is_set():
                return False
            time.sleep(0.05)
        return True
    def _camera_probe_region(self, frame_shape: tuple[int, ...], profile: CalibrationProfile) -> tuple[int, int, int, int]:
        frame_h, frame_w = frame_shape[:2]
        default = (0.25, 0.16, 0.5, 0.45)
        raw_region = profile.thresholds.get('go_to_farm_camera_probe_region', default)
        try:
            x_ratio, y_ratio, w_ratio, h_ratio = raw_region
        except Exception:
            x_ratio, y_ratio, w_ratio, h_ratio = default
        x = int(frame_w * float(x_ratio))
        y = int(frame_h * float(y_ratio))
        w = int(frame_w * float(w_ratio))
        h = int(frame_h * float(h_ratio))
        x = max(0, min(frame_w - 1, x))
        y = max(0, min(frame_h - 1, y))
        w = max(1, min(frame_w - x, w))
        h = max(1, min(frame_h - y, h))
        return (x, y, w, h)
    def _frame_motion_score(self, before: np.ndarray, after: np.ndarray, region: tuple[int, int, int, int]) -> float:
        x, y, w, h = region
        before_crop = before[y:y + h, x:x + w]
        after_crop = after[y:y + h, x:x + w]
        if before_crop.size == 0 or after_crop.size == 0:
            return 0.0
        else:
            before_gray = cv2.cvtColor(before_crop, cv2.COLOR_BGR2GRAY)
            after_gray = cv2.cvtColor(after_crop, cv2.COLOR_BGR2GRAY)
            before_small = cv2.resize(before_gray, (160, 90), interpolation=cv2.INTER_AREA)
            after_small = cv2.resize(after_gray, (160, 90), interpolation=cv2.INTER_AREA)
            return float(cv2.mean(cv2.absdiff(before_small, after_small))[0])
    def _probe_camera_motion(self, profile: CalibrationProfile, stop_event: Event) -> float | None:
        dx = int(profile.thresholds.get('go_to_farm_camera_probe_dx_px', 90.0))
        settle_s = float(profile.timeouts.get('go_to_farm_camera_probe_settle_seconds', 0.16))
        restore_s = float(profile.timeouts.get('go_to_farm_camera_probe_restore_seconds', 0.08))
        if dx == 0:
            return 0.0
        else:
            before = self.capture.grab_bgr()
            region = self._camera_probe_region(before.shape, profile)
            self.input.move_mouse_relative(dx, 0)
            if not self._sleep_interruptible(settle_s, stop_event):
                return None
            else:
                after = self.capture.grab_bgr()
                self.input.move_mouse_relative(-dx, 0)
                if not self._sleep_interruptible(restore_s, stop_event):
                    return None
                else:
                    return self._frame_motion_score(before, after, region)
    def _ensure_camera_control(self, profile: CalibrationProfile, stop_event: Event) -> bool:
        enabled = bool(int(profile.thresholds.get('go_to_farm_camera_control_check_enabled', 1.0)))
        if not enabled:
            self.logger.info('Go to farm camera control check disabled')
            return True
        else:
            threshold = float(profile.thresholds.get('go_to_farm_camera_probe_min_score', 4.0))
            retry_delay_s = float(profile.timeouts.get('go_to_farm_post_y_delay_seconds', 0.2))
            attempts = max(1, int(profile.thresholds.get('go_to_farm_camera_probe_attempts', 2.0)))
            for attempt in range(1, attempts + 1):
                score = self._probe_camera_motion(profile, stop_event)
                if score is None:
                    return False
                else:
                    self.logger.info('Go to farm camera control probe attempt=%s score=%.2f threshold=%.2f', attempt, score, threshold)
                    if score >= threshold:
                        return True
                    else:
                        if attempt >= attempts:
                            break
                        else:
                            self.logger.info('Go to farm camera did not react; toggling Y and probing again')
                            self.input.tap_key('Y', hold_s=0.06)
                            if not self._sleep_interruptible(retry_delay_s, stop_event):
                                return False
            self.logger.warning('Go to farm camera probe did not detect movement; continuing with current state')
            return True
    def _reset_progress_tracking(self) -> None:
        self._previous_motion_signature = None
        now = time.monotonic()
        self._last_progress_at = now
        self._last_distance_value = None
        self._last_distance_progress_value = None
        self._last_distance_accept_at = 0.0
        self._last_distance_progress_at = now
        self._plateau_anchor_distance = None
        self._plateau_anchor_started_at = 0.0
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
        self._last_world_coords_at = 0.0
        self._last_world_progress_at = now
        self._last_target_coord_error = None
        self._coord_velocity_x = 0.0
        self._coord_velocity_z = 0.0
        self._coord_forward_speed = 0.0
        self._coord_lateral_speed = 0.0
        self._coord_arrival_frames = 0
        self._stable_world_coords = None
        self._world_coord_candidate = None
        self._world_coord_candidate_frames = 0
        self._steer_direction = 0
        self._steer_hold_until = 0.0
        self._last_mouse_turn_at = 0.0
        self._last_mouse_turn_direction = 0
        self._post_recover_steer_settle_until = 0.0
        self._dock_pulse_until = 0.0
        self._dock_pulse_next_at = 0.0
        self._recover_lock_direction = 0
        self._recover_lock_until = 0.0
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
        self._coord_heading_confidence = 0.0
        self._coord_heading_at = 0.0
        self._coord_valid = False
        self._coord_validity_reason = 'init'
        self._coord_last_good_at = 0.0
        self._recent_coord_progress_at = 0.0
        self._nav_state = 'ALIGN'
        self._nav_state_since = 0.0
        self._route_transition_until = 0.0
        self._final_dwell_started_at = 0.0
        self._last_segment_metric = None
        self._last_segment_progress_at = 0.0
    def _load_route_waypoints(self, profile: CalibrationProfile) -> list[tuple[int, int | None, int]]:
        waypoints = []
        route_data = profile.get_active_go_to_farm_route()
        if not route_data:
            legacy_route_data = profile.templates.get('go_to_farm_route', [])
            if isinstance(legacy_route_data, list):
                for entry in legacy_route_data:
                    if not isinstance(entry, (list, tuple)):
                        continue
                    else:
                        if len(entry) >= 3:
                            x, y, z = (entry[0], entry[1], entry[2])
                        else:
                            if len(entry) >= 2:
                                x, z = (entry[0], entry[1])
                                y = None
                            else:
                                continue
                        try:
                            waypoint = (int(round(float(x))), None if y is None else int(round(float(y))), int(round(float(z))))
                        except (TypeError, ValueError):
                            continue
                        waypoints.append(waypoint)
        else:
            waypoints.extend(route_data)
        fallback = self._single_target_world_coordinates(profile)
        if fallback is not None:
            if not waypoints or waypoints[(-1)][0]!= fallback[0] or waypoints[(-1)][2]!= fallback[2]:
                waypoints.append(fallback)
        return waypoints
    def _prepare_route(self, profile: CalibrationProfile) -> None:
        now = time.monotonic()
        self._route_waypoints = self._load_route_waypoints(profile)
        self._route_index = 0
        self._route_aligned = False
        self._route_reach_frames = 0
        self._route_pass_frames = 0
        self._route_best_distance = None
        self._coord_heading_rad = None
        self._coord_heading_confidence = 0.0
        self._coord_heading_at = 0.0
        self._coord_valid = False
        self._coord_validity_reason = 'reset'
        self._coord_last_good_at = 0.0
        self._recent_coord_progress_at = now
        self._nav_state = 'ALIGN'
        self._nav_state_since = now
        self._route_transition_until = 0.0
        self._final_dwell_started_at = 0.0
        self._last_segment_metric = None
        self._last_segment_progress_at = now
    def _single_target_world_coordinates(self, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        target_x = profile.thresholds.get('go_to_farm_target_x')
        target_z = profile.thresholds.get('go_to_farm_target_z')
        if target_x is None or target_z is None:
            return None
        else:
            target_y = profile.thresholds.get('go_to_farm_target_y')
            return (int(round(target_x)), int(round(target_y)) if target_y is not None else None, int(round(target_z)))
    def _route_target(self) -> tuple[int, int | None, int] | None:
        if not self._route_waypoints:
            return None
        else:
            index = max(0, min(self._route_index, len(self._route_waypoints) - 1))
            return self._route_waypoints[index]
    def _route_previous_waypoint(self) -> tuple[int, int | None, int] | None:
        if not self._route_waypoints or self._route_index <= 0:
            return None
        else:
            return self._route_waypoints[self._route_index - 1]
    def _route_next_waypoint(self) -> tuple[int, int | None, int] | None:
        # ***<module>.GoToFarmController._route_next_waypoint: Failure: Different control flow
        if self._route_waypoints and self._route_index >= len(self._route_waypoints) - 1:
            return None
        else:
            return self._route_waypoints[self._route_index + 1]
    def _route_is_final(self) -> bool:
        return bool(self._route_waypoints) and self._route_index >= len(self._route_waypoints) - 1
    def _route_hard_anchor_count(self, profile: CalibrationProfile) -> int:
        if not self._route_waypoints:
            return 0
        else:
            configured = max(0, int(profile.thresholds.get('go_to_farm_route_hard_anchor_count', 3.0)))
            return min(len(self._route_waypoints), configured)
    def _route_in_hard_anchor_phase(self, profile: CalibrationProfile) -> bool:
        return bool(self._route_waypoints) and self._route_index < self._route_hard_anchor_count(profile)
    def _align_route_start(self, profile: CalibrationProfile) -> None:
        if self._route_aligned or not self._route_waypoints or self._stable_world_coords is None:
            return None
        else:
            rejoin_distance = float(profile.thresholds.get('go_to_farm_route_rejoin_distance_units', 140.0))
            hard_anchor_count = self._route_hard_anchor_count(profile)
            hard_anchor_start_distance = float(profile.thresholds.get('go_to_farm_route_hard_anchor_start_distance_units', 420.0))
            current_x, _current_y, current_z = self._stable_world_coords
            best_index = 0
            best_distance = float('inf')
            for index, waypoint in enumerate(self._route_waypoints):
                distance = float(np.hypot(float(waypoint[0] - current_x), float(waypoint[2] - current_z)))
                if distance < best_distance:
                    best_distance = distance
                    best_index = index
            if best_distance <= rejoin_distance:
                first_waypoint = self._route_waypoints[0]
                first_distance = float(np.hypot(float(first_waypoint[0] - current_x), float(first_waypoint[2] - current_z)))
                if hard_anchor_count > 0 and best_index >= hard_anchor_count and (first_distance <= hard_anchor_start_distance):
                    self._route_index = 0
                else:
                    self._route_index = best_index
            self._route_best_distance = None
            self._route_pass_frames = 0
            self._route_aligned = True
    def _route_segment_metrics(self, start: tuple[int, int | None, int] | None, end: tuple[int, int | None, int] | None) -> tuple[float | None, float | None]:
        if start is None or end is None or self._stable_world_coords is None:
            return (None, None)
        else:
            start_x, _start_y, start_z = start
            end_x, _end_y, end_z = end
            current_x, _current_y, current_z = self._stable_world_coords
            seg_x = float(end_x - start_x)
            seg_z = float(end_z - start_z)
            seg_len_sq = seg_x * seg_x + seg_z * seg_z
            if seg_len_sq <= 1e-06:
                return (None, None)
            else:
                rel_x = float(current_x - start_x)
                rel_z = float(current_z - start_z)
                projection = (rel_x * seg_x + rel_z * seg_z) / seg_len_sq
                seg_len = float(np.hypot(seg_x, seg_z))
                cross_track = abs(rel_x * seg_z - rel_z * seg_x) / max(seg_len, 1e-06)
                return (projection, cross_track)
    def _route_segment_lookahead_target(self, start: tuple[int, int | None, int] | None, end: tuple[int, int | None, int] | None, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        if start is None or end is None or self._stable_world_coords is None:
            return end
        else:
            start_x, _start_y, start_z = start
            end_x, end_y, end_z = end
            current_x, _current_y, current_z = self._stable_world_coords
            seg_x = float(end_x - start_x)
            seg_z = float(end_z - start_z)
            seg_len = float(np.hypot(seg_x, seg_z))
            if seg_len <= 1e-06:
                return end
            else:
                projection, cross_track = self._route_segment_metrics(start, end)
                projection_ratio = 0.0 if projection is None else float(np.clip(projection, 0.0, 1.0))
                projection_units = projection_ratio * seg_len
                lookahead_min = float(profile.thresholds.get('go_to_farm_route_lookahead_min_units', 72.0))
                lookahead_max = float(profile.thresholds.get('go_to_farm_route_lookahead_max_units', 220.0))
                lookahead_base = float(profile.thresholds.get('go_to_farm_route_lookahead_base_units', 92.0))
                lookahead_speed_gain = float(profile.thresholds.get('go_to_farm_route_lookahead_speed_gain', 1.8))
                cross_track_slow = float(profile.thresholds.get('go_to_farm_route_lookahead_cross_track_slow_units', 120.0))
                lookahead_units = lookahead_base + max(0.0, self._coord_forward_speed) * lookahead_speed_gain
                lookahead_units = float(np.clip(lookahead_units, lookahead_min, lookahead_max))
                if cross_track is not None and cross_track > cross_track_slow:
                        penalty = min(0.65, (cross_track - cross_track_slow) / max(cross_track_slow, 1e-06))
                        lookahead_units *= max(0.35, 1.0 - penalty)
                target_units = min(seg_len, projection_units + lookahead_units)
                target_ratio = float(np.clip(target_units / seg_len, 0.0, 1.0))
                target_x = int(round(start_x + seg_x * target_ratio))
                target_z = int(round(start_z + seg_z * target_ratio))
                _current_distance = float(np.hypot(float(end_x - current_x), float(end_z - current_z)))
                if _current_distance <= max(lookahead_min * 0.35, 28.0):
                    return end
                else:
                    return (target_x, end_y, target_z)
    def _route_guidance_target(self, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        current_target = self._route_target()
        if current_target is None:
            return self._single_target_world_coordinates(profile)
        else:
            if self._route_is_final():
                return current_target
            else:
                if self._route_in_hard_anchor_phase(profile):
                    return current_target
                else:
                    next_target = self._route_next_waypoint()
                    if next_target is None or self._stable_world_coords is None:
                        return current_target
                    else:
                        handoff_distance = float(profile.thresholds.get('go_to_farm_route_handoff_distance_units', 72.0))
                        handoff_projection = float(profile.thresholds.get('go_to_farm_route_handoff_projection_ratio', 0.94))
                        current_x, _current_y, current_z = self._stable_world_coords
                        current_distance = float(np.hypot(float(current_target[0] - current_x), float(current_target[2] - current_z)))
                        segment_progress, _cross_track = self._route_segment_metrics(self._route_previous_waypoint(), current_target)
                        handoff_ready = current_distance <= handoff_distance
                        if segment_progress is not None and segment_progress >= handoff_projection:
                                handoff_ready = True
                        if handoff_ready:
                            return self._route_segment_lookahead_target(current_target, next_target, profile) or next_target
                        else:
                            segment_start = self._route_previous_waypoint()
                            if segment_start is None:
                                segment_start = self._stable_world_coords
                            return self._route_segment_lookahead_target(segment_start, current_target, profile) or current_target
    def _try_advance_route(self, snapshot, profile: CalibrationProfile) -> bool:
        # ***<module>.GoToFarmController._try_advance_route: Failure: Different control flow
        if self._route_waypoints and self._route_is_final():
            self._route_reach_frames = 0
            self._route_pass_frames = 0
            self._route_best_distance = None
            return False
        else:
            coord_error = self._final_coord_error(snapshot, profile)
            if coord_error is None:
                self._route_reach_frames = 0
                self._route_pass_frames = 0
                return False
            else:
                waypoint_distance = float(profile.thresholds.get('go_to_farm_route_waypoint_distance_units', 42.0))
                waypoint_axis = float(profile.thresholds.get('go_to_farm_route_waypoint_axis_units', 34.0))
                waypoint_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_route_waypoint_confirm_frames', 2.0)))
                handoff_distance = float(profile.thresholds.get('go_to_farm_route_handoff_distance_units', 72.0))
                handoff_projection = float(profile.thresholds.get('go_to_farm_route_handoff_projection_ratio', 0.94))
                handoff_cross_track = float(profile.thresholds.get('go_to_farm_route_handoff_cross_track_units', 120.0))
                handoff_worsen = float(profile.thresholds.get('go_to_farm_route_handoff_worsen_units', 18.0))
                handoff_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_route_handoff_confirm_frames', 2.0)))
                hard_anchor_mode = self._route_in_hard_anchor_phase(profile)
                hard_anchor_confirm_frames = max(waypoint_confirm_frames, int(profile.thresholds.get('go_to_farm_route_hard_anchor_confirm_frames', 3.0)))
                current_distance = coord_error[3]
                if self._route_best_distance is None or current_distance < self._route_best_distance:
                    self._route_best_distance = current_distance
                if current_distance <= waypoint_distance and max(abs(coord_error[0]), abs(coord_error[2])) <= waypoint_axis:
                    self._route_reach_frames += 1
                else:
                    self._route_reach_frames = 0
                passed_waypoint = False
                segment_progress, cross_track = self._route_segment_metrics(self._route_previous_waypoint(), self._route_target())
                if self._route_best_distance is not None and self._route_best_distance <= handoff_distance and (segment_progress is not None) and (segment_progress >= handoff_projection) and (cross_track is not None) and (cross_track <= handoff_cross_track):
                                        if current_distance >= self._route_best_distance + handoff_worsen:
                                            passed_waypoint = True
                                        else:
                                            if current_distance <= handoff_distance:
                                                passed_waypoint = True
                if passed_waypoint and (not hard_anchor_mode):
                    self._route_pass_frames += 1
                else:
                    self._route_pass_frames = 0
                direct_reached = self._route_reach_frames >= (hard_anchor_confirm_frames if hard_anchor_mode else waypoint_confirm_frames)
                handoff_reached = not hard_anchor_mode and self._route_pass_frames >= handoff_confirm_frames
                if not direct_reached and (not handoff_reached):
                        return False
                reached_index = self._route_index
                self._route_index = min(self._route_index + 1, len(self._route_waypoints) - 1)
                self._route_reach_frames = 0
                self._route_pass_frames = 0
                self._route_best_distance = None
                self._last_target_coord_error = None
                self._recover_lock_direction = 0
                self._recover_lock_until = 0.0
                self._recover_lock_reference_error = None
                self._steer_direction = 0
                self._steer_hold_until = 0.0
                self._last_mouse_turn_direction = 0
                self._last_mouse_turn_at = 0.0
                self._coord_velocity_x = 0.0
                self._coord_velocity_z = 0.0
                self._coord_forward_speed = 0.0
                self._coord_lateral_speed = 0.0
                self._coord_heading_rad = None
                self._coord_heading_confidence = 0.0
                self._coord_heading_at = 0.0
                self._last_predictive_offset = None
                self._last_predictive_align = None
                self._last_predictive_improvement = None
                now = time.monotonic()
                self._last_progress_at = now
                self._recent_coord_progress_at = now
                transition_settle_s = float(profile.timeouts.get('go_to_farm_route_transition_settle_seconds', 1.25))
                if self._route_index < self._route_hard_anchor_count(profile):
                    transition_settle_s = max(transition_settle_s, float(profile.timeouts.get('go_to_farm_route_hard_anchor_transition_settle_seconds', 1.75)))
                self._route_transition_until = now + transition_settle_s
                self._final_dwell_started_at = 0.0
                self._last_segment_metric = None
                self._last_segment_progress_at = now
                reached = self._route_waypoints[reached_index]
                next_target = self._route_waypoints[self._route_index]
                self.logger.info('Go to farm waypoint reached: index=%s/%s reached=(%s,%s,%s) next=(%s,%s,%s) mode=%s', reached_index + 1, len(self._route_waypoints), reached[0], reached[1], reached[2], next_target[0], next_target[1], next_target[2], 'handoff' if handoff_reached else 'direct')
                return True
    def _target_world_coordinates(self, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        route_target = self._route_guidance_target(profile)
        if route_target is not None:
            return route_target
        else:
            return self._single_target_world_coordinates(profile)
    def _final_world_coordinates(self, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        route_target = self._route_target()
        if route_target is not None:
            return route_target
        else:
            return self._single_target_world_coordinates(profile)
    def _target_coord_error(self, snapshot, profile: CalibrationProfile) -> tuple[int, int | None, int, float] | None:
        target = self._target_world_coordinates(profile)
        current_world = self._stable_world_coords
        if target is None or current_world is None:
            return None
        else:
            target_x, target_y, target_z = target
            current_x, current_y, current_z = current_world
            dx = target_x - current_x
            dz = target_z - current_z
            dy = None
            if target_y is not None and current_y is not None:
                    dy = target_y - current_y
            distance_units = float((dx * dx + dz * dz) ** 0.5)
            return (dx, dy, dz, distance_units)
    def _route_coord_error(self, snapshot, profile: CalibrationProfile) -> tuple[int, int | None, int, float] | None:
        target = self._final_world_coordinates(profile)
        current_world = self._stable_world_coords
        if target is None or current_world is None:
            return None
        else:
            target_x, target_y, target_z = target
            current_x, current_y, current_z = current_world
            dx = target_x - current_x
            dz = target_z - current_z
            dy = None
            if target_y is not None and current_y is not None:
                    dy = target_y - current_y
            distance_units = float((dx * dx + dz * dz) ** 0.5)
            return (dx, dy, dz, distance_units)
    def _final_coord_error(self, snapshot, profile: CalibrationProfile) -> tuple[int, int | None, int, float] | None:
        target = self._final_world_coordinates(profile)
        current_world = self._stable_world_coords
        if target is None or current_world is None:
            return None
        else:
            target_x, target_y, target_z = target
            current_x, current_y, current_z = current_world
            dx = target_x - current_x
            dz = target_z - current_z
            dy = None
            if target_y is not None and current_y is not None:
                    dy = target_y - current_y
            distance_units = float((dx * dx + dz * dz) ** 0.5)
            return (dx, dy, dz, distance_units)
    def _steering_coord_error(self, coord_error: tuple[int, int | None, int, float] | None, profile: CalibrationProfile) -> tuple[int, int | None, int, float] | None:
        if coord_error is None:
            return None
        else:
            axis_deadband = float(profile.thresholds.get('go_to_farm_coord_steer_axis_deadband_units', 5.0))
            dx, dy, dz, _distance_units = coord_error
            steer_dx = 0 if abs(dx) <= axis_deadband else dx
            steer_dz = 0 if abs(dz) <= axis_deadband else dz
            steer_distance = float((steer_dx * steer_dx + steer_dz * steer_dz) ** 0.5)
            return (steer_dx, dy, steer_dz, steer_distance)
    @staticmethod
    def _wrap_angle_rad(angle: float) -> float:
        return float((angle + math.pi) % (2.0 * math.pi) - math.pi)
    def _set_coord_validity(self, valid: bool, reason: str) -> None:
        if self._coord_valid == valid and self._coord_validity_reason == reason:
                return None
        self._coord_valid = valid
        self._coord_validity_reason = reason
        if valid:
            self._coord_last_good_at = time.monotonic()
        self.logger.info('Go to farm coord validity: valid=%s reason=%s', valid, reason)
    def _read_validated_coordinates(self, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        if self._stable_world_coords is None:
            self._set_coord_validity(False, 'missing')
            return None
        else:
            stale_timeout_s = float(profile.timeouts.get('go_to_farm_coord_stale_timeout_sec', 0.75))
            now = time.monotonic()
            if self._last_world_coords_at <= 0.0 or now - self._last_world_coords_at > stale_timeout_s:
                self._set_coord_validity(False, 'stale')
                return None
            else:
                self._set_coord_validity(True, 'ok')
                return self._stable_world_coords
    def _estimate_heading(self, snapshot, profile: CalibrationProfile) -> tuple[float | None, float]:
        now = time.monotonic()
        speed = float(np.hypot(self._coord_velocity_x, self._coord_velocity_z))
        min_speed = float(profile.thresholds.get('go_to_farm_heading_min_speed_units_per_s', profile.thresholds.get('go_to_farm_coord_heading_min_speed_units_per_s', 3.5)))
        smoothing_alpha = float(profile.thresholds.get('go_to_farm_heading_smoothing_alpha', 0.38))
        hold_timeout_s = float(profile.timeouts.get('go_to_farm_heading_hold_timeout_sec', 0.9))
        minimap_heading_confidence_min = float(profile.thresholds.get('go_to_farm_coord_heading_confidence_min', 0.12))
        if speed >= min_speed:
            measured_heading = math.atan2(self._coord_velocity_x, self._coord_velocity_z)
            if self._coord_heading_rad is None:
                self._coord_heading_rad = measured_heading
            else:
                delta = self._wrap_angle_rad(measured_heading - self._coord_heading_rad)
                self._coord_heading_rad = self._wrap_angle_rad(self._coord_heading_rad + delta * smoothing_alpha)
            self._coord_heading_confidence = min(1.0, speed / max(min_speed * 2.0, 1e-06))
            self._coord_heading_at = now
            return (self._coord_heading_rad, self._coord_heading_confidence)
        else:
            if snapshot.minimap_heading_vector is not None and snapshot.minimap_heading_confidence >= minimap_heading_confidence_min:
                measured_heading = math.atan2(float(snapshot.minimap_heading_vector[0]), float(-snapshot.minimap_heading_vector[1]))
                if self._coord_heading_rad is None:
                    self._coord_heading_rad = measured_heading
                else:
                    delta = self._wrap_angle_rad(measured_heading - self._coord_heading_rad)
                    self._coord_heading_rad = self._wrap_angle_rad(self._coord_heading_rad + delta * smoothing_alpha)
                self._coord_heading_confidence = max(0.35, min(1.0, float(snapshot.minimap_heading_confidence)))
                self._coord_heading_at = now
                return (self._coord_heading_rad, self._coord_heading_confidence)
            else:
                if self._coord_heading_rad is not None and now - self._coord_heading_at <= hold_timeout_s:
                    return (self._coord_heading_rad, max(0.2, self._coord_heading_confidence * 0.65))
                else:
                    return (None, 0.0)
    def _compute_heading_error(self, snapshot, profile: CalibrationProfile) -> tuple[float, float, float, float, float] | None:
        if self._read_validated_coordinates(profile) is None:
            return None
        else:
            target_error = self._target_coord_error(snapshot, profile)
            if target_error is None or target_error[3] <= 1e-06:
                return None
            else:
                current_heading, heading_confidence = self._estimate_heading(snapshot, profile)
                if current_heading is None:
                    return None
                else:
                    desired_heading = math.atan2(float(target_error[0]), float(target_error[2]))
                    heading_error = self._wrap_angle_rad(desired_heading - current_heading)
                    heading_error_deg = math.degrees(heading_error)
                    sanity_abs_deg = float(profile.thresholds.get('go_to_farm_heading_sanity_max_deg', 120.0))
                    sanity_forward_min = float(profile.thresholds.get('go_to_farm_heading_sanity_forward_min_units_per_s', 4.0))
                    if abs(heading_error_deg) >= sanity_abs_deg and self._coord_forward_speed >= sanity_forward_min:
                        self.logger.info('Go to farm heading rejected: error=%.1f forward=%.1f desired=%.1f current=%.1f', heading_error_deg, self._coord_forward_speed, math.degrees(desired_heading), math.degrees(current_heading))
                        self._coord_heading_rad = None
                        self._coord_heading_confidence = 0.0
                        self._coord_heading_at = 0.0
                        return None
                    else:
                        return (heading_error, heading_error_deg, desired_heading, current_heading, heading_confidence)
    def _set_navigation_state(self, state: str, reason: str, heading_error_deg: float | None, target_distance: float | None) -> None:
        if self._nav_state == state:
            return None
        else:
            self.logger.info('Go to farm nav state: %s -> %s reason=%s heading_error=%.1f distance=%.1f', self._nav_state, state, reason, 0.0 if heading_error_deg is None else heading_error_deg, (-1.0) if target_distance is None else target_distance)
            self._nav_state = state
            self._nav_state_since = time.monotonic()
    def _select_navigation_state(self, snapshot, profile: CalibrationProfile, route_intermediate: bool, terminal_mode_active: bool) -> tuple[str, tuple[float, float, float, float, float] | None, float | None]:
        target_error = self._target_coord_error(snapshot, profile)
        final_error = self._final_coord_error(snapshot, profile)
        if target_error is None or self._read_validated_coordinates(profile) is None:
            self._set_navigation_state('ALIGN', 'coords-invalid', None, None)
            return ('ALIGN', None, None)
        else:
            heading_info = self._compute_heading_error(snapshot, profile)
            active_distance = target_error[3]
            final_distance = active_distance if final_error is None else final_error[3]
            final_approach_distance = float(profile.thresholds.get('go_to_farm_final_approach_distance_units', 72.0))
            final_align_hold_distance = float(profile.thresholds.get('go_to_farm_final_align_hold_distance_units', 18.0))
            align_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_align_threshold_deg', 35.0))
            sprint_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_sprint_threshold_deg', 12.0))
            turn_in_place_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_turn_in_place_threshold_deg', 60.0))
            final_turn_in_place_threshold_deg = float(profile.thresholds.get('go_to_farm_final_turn_in_place_threshold_deg', max(turn_in_place_threshold_deg + 30.0, 95.0)))
            if not route_intermediate and final_distance <= final_approach_distance:
                if heading_info is None:
                    self._set_navigation_state('FINAL_APPROACH', 'final-no-heading', None, final_distance)
                    return ('FINAL_APPROACH', None, final_distance)
                else:
                    heading_error_deg = abs(heading_info[1])
                    if heading_error_deg >= final_turn_in_place_threshold_deg and final_distance > final_align_hold_distance:
                        self._set_navigation_state('ALIGN', 'final-large-error', heading_info[1], final_distance)
                        return ('ALIGN', heading_info, final_distance)
                    else:
                        self._set_navigation_state('FINAL_APPROACH', 'final-distance', heading_info[1], final_distance)
                        return ('FINAL_APPROACH', heading_info, final_distance)
            else:
                if heading_info is None:
                    missing_heading_coast_distance = float(profile.thresholds.get('go_to_farm_heading_missing_coast_distance_units', 35.0))
                    fallback_state = 'COAST' if self._coord_forward_speed > 1.0 or (route_intermediate and active_distance > missing_heading_coast_distance) else 'ALIGN'
                    self._set_navigation_state(fallback_state, 'heading-missing', None, active_distance)
                    return (fallback_state, None, active_distance)
                else:
                    now = time.monotonic()
                    heading_error_deg = abs(heading_info[1])
                    transition_active = now < self._route_transition_until
                    run_exit_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_run_exit_threshold_deg', max(sprint_threshold_deg + 8.0, 18.0)))
                    align_recover_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_align_recover_threshold_deg', max(sprint_threshold_deg + 6.0, align_threshold_deg - 8.0)))
                    coast_realign_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_coast_realign_threshold_deg', align_threshold_deg + 8.0))
                    if transition_active and route_intermediate:
                        if heading_error_deg >= turn_in_place_threshold_deg:
                            self._set_navigation_state('ALIGN', 'transition-large-error', heading_info[1], active_distance)
                            return ('ALIGN', heading_info, active_distance)
                        else:
                            self._set_navigation_state('COAST', 'route-transition', heading_info[1], active_distance)
                            return ('COAST', heading_info, active_distance)
                    else:
                        if heading_error_deg >= turn_in_place_threshold_deg:
                            self._set_navigation_state('ALIGN', 'large-heading-error', heading_info[1], active_distance)
                            return ('ALIGN', heading_info, active_distance)
                        else:
                            current_state = self._nav_state
                            if current_state == 'RUN':
                                if heading_error_deg <= run_exit_threshold_deg and (not terminal_mode_active):
                                    self._set_navigation_state('RUN', 'run-hold', heading_info[1], active_distance)
                                    return ('RUN', heading_info, active_distance)
                                else:
                                    if heading_error_deg <= coast_realign_threshold_deg:
                                        self._set_navigation_state('COAST', 'run-to-coast', heading_info[1], active_distance)
                                        return ('COAST', heading_info, active_distance)
                                    else:
                                        self._set_navigation_state('ALIGN', 'run-realign', heading_info[1], active_distance)
                                        return ('ALIGN', heading_info, active_distance)
                            else:
                                if current_state == 'COAST':
                                    if heading_error_deg <= sprint_threshold_deg and (not terminal_mode_active):
                                        self._set_navigation_state('RUN', 'good-align', heading_info[1], active_distance)
                                        return ('RUN', heading_info, active_distance)
                                    else:
                                        if heading_error_deg <= coast_realign_threshold_deg:
                                            self._set_navigation_state('COAST', 'coast-hold', heading_info[1], active_distance)
                                            return ('COAST', heading_info, active_distance)
                                        else:
                                            self._set_navigation_state('ALIGN', 're-align', heading_info[1], active_distance)
                                            return ('ALIGN', heading_info, active_distance)
                                else:
                                    if heading_error_deg <= sprint_threshold_deg and (not terminal_mode_active):
                                        self._set_navigation_state('RUN', 'good-align', heading_info[1], active_distance)
                                        return ('RUN', heading_info, active_distance)
                                    else:
                                        if heading_error_deg <= align_recover_threshold_deg:
                                            self._set_navigation_state('COAST', 'moderate-align', heading_info[1], active_distance)
                                            return ('COAST', heading_info, active_distance)
                                        else:
                                            self._set_navigation_state('ALIGN', 're-align', heading_info[1], active_distance)
                                            return ('ALIGN', heading_info, active_distance)
    def _apply_heading_turn(self, state: str, heading_error_deg: float | None, profile: CalibrationProfile) -> None:
        if heading_error_deg is None:
            return None
        else:
            deadzone_deg = float(profile.thresholds.get('go_to_farm_heading_turn_deadzone_deg', 2.0))
            if abs(heading_error_deg) <= deadzone_deg:
                return None
            else:
                base_gain = float(profile.thresholds.get('go_to_farm_heading_turn_gain_px_per_deg', 1.35))
                min_dx = int(profile.thresholds.get('go_to_farm_heading_turn_min_dx', 4.0))
                max_dx = int(profile.thresholds.get('go_to_farm_heading_turn_max_dx', 56.0))
                cooldown_s = float(profile.timeouts.get('go_to_farm_heading_turn_cooldown_seconds', 0.12))
                flip_hold_s = float(profile.timeouts.get('go_to_farm_heading_flip_hold_seconds', 0.32))
                state_scale = {'ALIGN': float(profile.thresholds.get('go_to_farm_heading_turn_align_scale', 1.0)), 'RUN': float(profile.thresholds.get('go_to_farm_heading_turn_run_scale', 0.35)), 'COAST': float(profile.thresholds.get('go_to_farm_heading_turn_coast_scale', 0.55)), 'FINAL_APPROACH': float(profile.thresholds.get('go_to_farm_heading_turn_final_scale', 0.25))}.get(state, 0.45)
                now = time.monotonic()
                if now < self._last_mouse_turn_at + cooldown_s:
                    return None
                else:
                    raw_turn_dx = int(round(heading_error_deg * base_gain * state_scale))
                    if abs(raw_turn_dx) < min_dx:
                        raw_turn_dx = min_dx if raw_turn_dx > 0 else -min_dx
                    raw_turn_dx = max(-max_dx, min(max_dx, raw_turn_dx))
                    turn_direction = 1 if raw_turn_dx > 0 else (-1)
                    if self._last_mouse_turn_direction!= 0 and turn_direction!= self._last_mouse_turn_direction and (now < self._steer_hold_until):
                                return None
                    self.input.move_mouse_relative(raw_turn_dx, 0)
                    self._last_mouse_turn_at = now
                    self._last_mouse_turn_direction = turn_direction
                    self._steer_direction = turn_direction
                    self._steer_hold_until = now + flip_hold_s
    def _update_segment_progress(self, snapshot, profile: CalibrationProfile) -> bool:
        if self._read_validated_coordinates(profile) is None:
            return False
        else:
            now = time.monotonic()
            metric = None
            if self._route_waypoints and (not self._route_is_final()) and (self._route_index > 0):
                segment_progress, _cross_track = self._route_segment_metrics(self._route_previous_waypoint(), self._route_target())
                if segment_progress is not None:
                    metric = segment_progress
            else:
                final_error = self._final_coord_error(snapshot, profile)
                if final_error is not None:
                    metric = -final_error[3]
            if metric is None:
                return False
            else:
                progress_step = float(profile.thresholds.get('go_to_farm_segment_progress_step', 0.015))
                if self._last_segment_metric is None or metric >= self._last_segment_metric + progress_step:
                    self._last_segment_progress_at = now
                    self._last_segment_metric = metric
                    return True
                else:
                    if metric > self._last_segment_metric:
                        self._last_segment_metric = metric
                    return False
    def _is_stuck_from_segment_progress(self, profile: CalibrationProfile) -> bool:
        if self._last_world_coords is None or not self._coord_valid:
            return False
        else:
            if self._nav_state not in {'COAST', 'RUN'}:
                return False
            else:
                now = time.monotonic()
                if now < self._route_transition_until:
                    return False
                else:
                    timeout_s = float(profile.timeouts.get('go_to_farm_stuck_progress_timeout_sec', 2.0))
                    recent_progress_grace_s = float(profile.timeouts.get('go_to_farm_recent_progress_recover_grace_seconds', 1.6))
                    if now - self._recent_coord_progress_at <= recent_progress_grace_s:
                        return False
                    else:
                        if self._route_in_hard_anchor_phase(profile):
                            timeout_s = max(timeout_s, float(profile.timeouts.get('go_to_farm_route_hard_anchor_stuck_timeout_sec', 4.0)))
                            if now - self._last_progress_at <= recent_progress_grace_s:
                                return False
                        return now - self._last_segment_progress_at >= timeout_s
    def _coord_in_dock_zone(self, snapshot, profile: CalibrationProfile) -> bool:
        coord_error = self._route_coord_error(snapshot, profile)
        if coord_error is None:
            return False
        else:
            dock_distance = float(profile.thresholds.get('go_to_farm_coord_dock_distance_units', 24.0))
            dock_axis = float(profile.thresholds.get('go_to_farm_coord_dock_axis_units', 18.0))
            return coord_error[3] <= dock_distance and max(abs(coord_error[0]), abs(coord_error[2])) <= dock_axis
    def _compute_predictive_coord_offset(self, snapshot, profile: CalibrationProfile) -> tuple[float | None, float | None, float | None]:
        if not bool(profile.thresholds.get('go_to_farm_use_predictive_steering', 0.0)):
            self._last_predictive_offset = None
            self._last_predictive_align = None
            self._last_predictive_improvement = None
            return (None, None, None)
        else:
            target_error = self._steering_coord_error(self._target_coord_error(snapshot, profile), profile)
            if target_error is None:
                self._last_predictive_offset = None
                self._last_predictive_align = None
                self._last_predictive_improvement = None
                return (None, None, None)
            else:
                dx_to_target, _dy, dz_to_target, coord_distance = target_error
                coord_heading_speed = float(np.hypot(self._coord_velocity_x, self._coord_velocity_z))
                coord_heading_min_speed = float(profile.thresholds.get('go_to_farm_coord_heading_min_speed_units_per_s', 3.5))
                coord_predictive_min_distance = float(profile.thresholds.get('go_to_farm_coord_predictive_min_distance_units', 18.0))
                if coord_distance <= coord_predictive_min_distance or coord_heading_speed < coord_heading_min_speed:
                    self._last_predictive_offset = None
                    self._last_predictive_align = None
                    self._last_predictive_improvement = None
                    return (None, None, None)
                else:
                    lookahead_seconds = float(profile.thresholds.get('go_to_farm_coord_lookahead_seconds', 1.2))
                    virtual_offset_scale = float(profile.thresholds.get('go_to_farm_coord_heading_virtual_offset_scale_px', 240.0))
                    virtual_offset_max = float(profile.thresholds.get('go_to_farm_coord_heading_virtual_offset_max_px', 240.0))
                    cross_deadzone = float(profile.thresholds.get('go_to_farm_coord_heading_cross_deadzone', 0.05))
                    predictive_min_align = float(profile.thresholds.get('go_to_farm_coord_predictive_min_align', 0.45))
                    reverse_dot = float(profile.thresholds.get('go_to_farm_coord_heading_reverse_dot', (-0.18)))
                    predictive_min_progress = float(profile.thresholds.get('go_to_farm_coord_predictive_min_progress_units', 4.0))
                    reverse_turn_min_px = float(profile.thresholds.get('go_to_farm_coord_reverse_turn_min_px', 120.0))
                    predicted_dx = float(dx_to_target) - self._coord_velocity_x * lookahead_seconds
                    predicted_dz = float(dz_to_target) - self._coord_velocity_z * lookahead_seconds
                    predicted_distance = float(np.hypot(predicted_dx, predicted_dz))
                    if predicted_distance <= 1e-06:
                        self._last_predictive_offset = None
                        self._last_predictive_align = None
                        self._last_predictive_improvement = None
                        return (None, None, None)
                    else:
                        hx = self._coord_velocity_x / coord_heading_speed
                        hz = self._coord_velocity_z / coord_heading_speed
                        ux = predicted_dx / predicted_distance
                        uz = predicted_dz / predicted_distance
                        align = hx * ux + hz * uz
                        cross = hx * uz - hz * ux
                        predicted_improvement = coord_distance - predicted_distance
                        if abs(cross) < cross_deadzone and align > reverse_dot and (predicted_improvement >= predictive_min_progress):
                            self._last_predictive_offset = 0.0
                            self._last_predictive_align = align
                            self._last_predictive_improvement = predicted_improvement
                            return (0.0, align, predicted_improvement)
                        else:
                            offset = float(np.clip(-cross * virtual_offset_scale, -virtual_offset_max, virtual_offset_max))
                            if align < predictive_min_align:
                                poor_align_scale = 1.0 + min(1.2, max(0.0, predictive_min_align - align) / max(0.1, predictive_min_align))
                                offset = float(np.clip(offset * poor_align_scale, -virtual_offset_max, virtual_offset_max))
                            if align < reverse_dot:
                                if abs(offset) < reverse_turn_min_px:
                                    direction = 0.0
                                    if abs(cross) >= cross_deadzone:
                                        direction = 1.0 if offset > 0.0 else (-1.0)
                                    else:
                                        if self._steer_direction!= 0:
                                            direction = float(self._steer_direction)
                                        else:
                                            if self._last_mouse_turn_direction!= 0:
                                                direction = float(self._last_mouse_turn_direction)
                                    if direction!= 0.0:
                                        offset = reverse_turn_min_px * direction
                            else:
                                if predicted_improvement < predictive_min_progress:
                                    offset *= 1.25
                            self._last_predictive_offset = offset
                            self._last_predictive_align = align
                            self._last_predictive_improvement = predicted_improvement
                            return (offset, align, predicted_improvement)
    def _apply_coordinate_navigation(self, snapshot, profile: CalibrationProfile, terminal_mode_active: bool) -> tuple[bool, float | None, float | None, bool]:
        route_intermediate = bool(self._route_waypoints) and (not self._route_is_final())
        validated_coords = self._read_validated_coordinates(profile)
        target_error = self._target_coord_error(snapshot, profile)
        final_error = self._final_coord_error(snapshot, profile)
        self.input.release_key('A')
        self.input.release_key('D')
        if validated_coords is None or target_error is None:
            now = time.monotonic()
            stale_hold_s = float(profile.timeouts.get('go_to_farm_coord_stale_hold_sec', 1.1))
            if self._coord_validity_reason == 'stale' and self._coord_last_good_at > 0.0 and (now - self._coord_last_good_at <= stale_hold_s) and (self._nav_state in {'COAST', 'RUN'}):
                self._last_nav_source = 'coord-stale-hold'
                if self._nav_state == 'RUN':
                    self.input.press_key('W')
                    if snapshot.stamina_ratio is not None and snapshot.stamina_ratio >= float(profile.thresholds.get('stamina_shift_threshold', 0.55)):
                        self.input.press_key('SHIFT')
                    else:
                        self.input.release_key('SHIFT')
                    return (True, None, None, True)
                else:
                    self.input.press_key('W')
                    self.input.release_key('SHIFT')
                    return (True, None, None, True)
            else:
                self._last_nav_source = 'coord-invalid-fallback'
                self._set_navigation_state('ALIGN', 'coords-unavailable', None, None)
                self.input.release_key('W')
                self.input.release_key('SHIFT')
                return (False, None, None, False)
        else:
            state, heading_info, target_distance = self._select_navigation_state(snapshot, profile, route_intermediate=route_intermediate, terminal_mode_active=terminal_mode_active)
            heading_error_deg = None if heading_info is None else heading_info[1]
            heading_error_abs = None if heading_error_deg is None else abs(heading_error_deg)
            active_distance = target_error[3]
            if final_error is not None and (not route_intermediate):
                    active_distance = final_error[3]
            self._apply_heading_turn(state, heading_error_deg, profile)
            final_radius = float(profile.thresholds.get('go_to_farm_final_radius', 10.0))
            sprint_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_sprint_threshold_deg', 12.0))
            align_threshold_deg = float(profile.thresholds.get('go_to_farm_heading_align_threshold_deg', 35.0))
            move_forward_now = False
            sprint = False
            if state == 'ALIGN':
                align_move_threshold = float(profile.thresholds.get('go_to_farm_align_move_threshold_deg', 58.0))
                align_move_min_distance = float(profile.thresholds.get('go_to_farm_align_move_min_distance_units', 28.0))
                align_can_drift = heading_error_abs is not None and heading_error_abs <= align_move_threshold and (active_distance > align_move_min_distance) and (not terminal_mode_active)
                if align_can_drift:
                    self.input.press_key('W')
                    move_forward_now = True
                else:
                    self.input.release_key('W')
                self.input.release_key('SHIFT')
            else:
                if state == 'RUN':
                    self.input.press_key('W')
                    move_forward_now = True
                    sprint = not terminal_mode_active and heading_error_abs is not None and (heading_error_abs <= sprint_threshold_deg) and (snapshot.stamina_ratio is not None) and (snapshot.stamina_ratio >= float(profile.thresholds.get('stamina_shift_threshold', 0.55)))
                    if sprint:
                        self.input.press_key('SHIFT')
                    else:
                        self.input.release_key('SHIFT')
                else:
                    if state == 'COAST':
                        self.input.press_key('W')
                        move_forward_now = True
                        self.input.release_key('SHIFT')
                    else:
                        self.input.release_key('SHIFT')
                        if final_error is not None and final_error[3] <= final_radius:
                            self.input.release_key('W')
                            move_forward_now = False
                        else:
                            if heading_error_abs is not None and heading_error_abs > align_threshold_deg:
                                self.input.release_key('W')
                                move_forward_now = False
                            else:
                                self.input.press_key('W')
                                move_forward_now = True
            self._last_nav_source = f'state:{state.lower()}'
            return (True, active_distance, heading_error_abs, move_forward_now)
    def _observe_world_coords(self, snapshot, profile: CalibrationProfile) -> tuple[int, int | None, int] | None:
        if snapshot.world_x is None or snapshot.world_z is None:
            return self._stable_world_coords
        else:
            coord_abs_max = int(profile.thresholds.get('go_to_farm_coord_abs_max_units', 20000.0))
            coord_height_abs_max = int(profile.thresholds.get('go_to_farm_coord_height_abs_max_units', 4000.0))
            coord_confirm_frames = max(2, int(profile.thresholds.get('go_to_farm_coord_confirm_frames', 2.0)))
            coord_accept_delta = int(profile.thresholds.get('go_to_farm_coord_accept_delta_units', 80.0))
            coord_replace_jump = int(profile.thresholds.get('go_to_farm_coord_replace_jump_units', 220.0))
            coord_replace_worsen_tolerance = float(profile.thresholds.get('go_to_farm_coord_replace_worsen_tolerance_units', 18.0))
            bootstrap_max_dx = float(profile.thresholds.get('go_to_farm_coord_bootstrap_max_abs_dx_units', 1800.0))
            bootstrap_max_dz = float(profile.thresholds.get('go_to_farm_coord_bootstrap_max_abs_dz_units', 3200.0))
            bootstrap_max_distance = float(profile.thresholds.get('go_to_farm_coord_bootstrap_max_distance_units', 2600.0))
            raw_x = int(snapshot.world_x)
            raw_y = int(snapshot.world_y) if snapshot.world_y is not None else None
            raw_z = int(snapshot.world_z)
            if abs(raw_x) > coord_abs_max or abs(raw_z) > coord_abs_max:
                return self._stable_world_coords
            else:
                if raw_y is not None:
                    if abs(raw_y) > coord_height_abs_max:
                        return self._stable_world_coords
                candidate = (raw_x, raw_y, raw_z)
                target = self._target_world_coordinates(profile)
                if self._stable_world_coords is None and target is not None:
                    target_x, _target_y, target_z = target
                    abs_dx = abs(raw_x - target_x)
                    abs_dz = abs(raw_z - target_z)
                    coord_distance = float(np.hypot(abs_dx, abs_dz))
                    if abs_dx > bootstrap_max_dx or abs_dz > bootstrap_max_dz or coord_distance > bootstrap_max_distance:
                        return self._stable_world_coords
                if self._stable_world_coords is None:
                    if self._world_coord_candidate is not None:
                        candidate_delta = max(abs(candidate[0] - self._world_coord_candidate[0]), abs(candidate[2] - self._world_coord_candidate[2]))
                        if candidate_delta <= coord_accept_delta:
                            self._world_coord_candidate = candidate
                            self._world_coord_candidate_frames += 1
                        else:
                            self._world_coord_candidate = candidate
                            self._world_coord_candidate_frames = 1
                    else:
                        self._world_coord_candidate = candidate
                        self._world_coord_candidate_frames = 1
                    if self._world_coord_candidate_frames >= coord_confirm_frames:
                        self._stable_world_coords = self._world_coord_candidate
                    return self._stable_world_coords
                else:
                    stable_delta = max(abs(candidate[0] - self._stable_world_coords[0]), abs(candidate[2] - self._stable_world_coords[2]))
                    current_error = None
                    candidate_error = None
                    if target is not None:
                        target_x, _target_y, target_z = target
                        current_error = float(np.hypot(float(target_x - self._stable_world_coords[0]), float(target_z - self._stable_world_coords[2])))
                        candidate_error = float(np.hypot(float(target_x - candidate[0]), float(target_z - candidate[2])))
                    worsening_jump = current_error is not None and candidate_error is not None and (candidate_error > current_error + coord_replace_worsen_tolerance)
                    if stable_delta <= coord_replace_jump and (not worsening_jump):
                        self._stable_world_coords = candidate
                        self._world_coord_candidate = candidate
                        self._world_coord_candidate_frames = coord_confirm_frames
                        return self._stable_world_coords
                    else:
                        if self._world_coord_candidate is not None:
                            candidate_delta = max(abs(candidate[0] - self._world_coord_candidate[0]), abs(candidate[2] - self._world_coord_candidate[2]))
                            if candidate_delta <= coord_accept_delta:
                                self._world_coord_candidate = candidate
                                self._world_coord_candidate_frames += 1
                            else:
                                self._world_coord_candidate = candidate
                                self._world_coord_candidate_frames = 1
                        else:
                            self._world_coord_candidate = candidate
                            self._world_coord_candidate_frames = 1
                        if self._world_coord_candidate_frames >= coord_confirm_frames:
                            replacement_delta = max(abs(self._world_coord_candidate[0] - self._stable_world_coords[0]), abs(self._world_coord_candidate[2] - self._stable_world_coords[2]))
                            if replacement_delta <= coord_replace_jump:
                                self._stable_world_coords = self._world_coord_candidate
                        return self._stable_world_coords
    def _accept_distance_value(self, distance_value: int, now: float, profile: CalibrationProfile) -> int:
        self._last_distance_value = distance_value
        self._last_distance_accept_at = now
        if distance_value > 0:
            history_size = max(4, int(profile.thresholds.get('go_to_farm_arrival_history_size', 8.0)))
            self._recent_distance_values.append(distance_value)
            if len(self._recent_distance_values) > history_size:
                self._recent_distance_values = self._recent_distance_values[-history_size:]
            start_distance_min = float(profile.thresholds.get('go_to_farm_start_distance_min_m', profile.thresholds.get('go_to_farm_distance_bootstrap_min_m', 300.0)))
            if self._start_distance_value is None and distance_value >= start_distance_min:
                    self._start_distance_value = distance_value
        return distance_value
    def _filter_distance_value(self, raw_distance: int | None, enemy_count: int, profile: CalibrationProfile) -> int | None:
        if raw_distance is None or raw_distance <= 0:
            return self._last_distance_value
        else:
            now = time.monotonic()
            bootstrap_min_distance = float(profile.thresholds.get('go_to_farm_distance_bootstrap_min_m', 300.0))
            bootstrap_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_distance_bootstrap_confirm_frames', 3.0)))
            bootstrap_variation = float(profile.thresholds.get('go_to_farm_distance_bootstrap_variation_m', 60.0))
            false_small_distance = float(profile.thresholds.get('go_to_farm_distance_false_small_m', 180.0))
            arrival_enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 2.0)))
            large_distance_recover_min = float(profile.thresholds.get('go_to_farm_distance_large_recover_min_m', max(260.0, bootstrap_min_distance * 0.7)))
            if self._last_distance_value is not None and self._last_distance_value <= false_small_distance and (enemy_count < arrival_enemy_min_count) and (raw_distance >= large_distance_recover_min):
                self.logger.info('Go to farm recovering from poisoned close distance raw=%s last=%s enemy_count=%s', raw_distance, self._last_distance_value, enemy_count)
                return self._accept_distance_value(raw_distance, now, profile)
            else:
                if self._last_distance_value is None or self._last_distance_accept_at <= 0.0:
                    if raw_distance >= bootstrap_min_distance:
                        self._distance_bootstrap_value = raw_distance
                        self._distance_bootstrap_frames = 0
                        return self._accept_distance_value(raw_distance, now, profile)
                    else:
                        if raw_distance <= false_small_distance and enemy_count >= arrival_enemy_min_count and self._arrival_gate_open:
                            self._distance_bootstrap_value = raw_distance
                            self._distance_bootstrap_frames = 0
                            return self._accept_distance_value(raw_distance, now, profile)
                        else:
                            if raw_distance <= false_small_distance and enemy_count < arrival_enemy_min_count:
                                self.logger.info('Go to farm rejecting unsupported close bootstrap distance raw=%s enemy_count=%s', raw_distance, enemy_count)
                                return self._last_distance_value
                            else:
                                if self._distance_bootstrap_value is not None and abs(raw_distance - self._distance_bootstrap_value) <= bootstrap_variation:
                                    self._distance_bootstrap_frames += 1
                                else:
                                    self._distance_bootstrap_value = raw_distance
                                    self._distance_bootstrap_frames = 1
                                if self._distance_bootstrap_frames >= bootstrap_confirm_frames:
                                    accepted_value = self._distance_bootstrap_value
                                    self._distance_bootstrap_value = None
                                    self._distance_bootstrap_frames = 0
                                    if accepted_value is not None:
                                        return self._accept_distance_value(accepted_value, now, profile)
                                    else:
                                        return self._last_distance_value
                                else:
                                    self.logger.info('Go to farm holding bootstrap distance raw=%s frames=%s enemy_count=%s', raw_distance, self._distance_bootstrap_frames, enemy_count)
                                    return self._last_distance_value
                else:
                    if self._distance_bootstrap_value is not None:
                        self._distance_bootstrap_value = None
                        self._distance_bootstrap_frames = 0
                    if self._last_distance_value is None or self._last_distance_accept_at <= 0.0:
                        return self._accept_distance_value(raw_distance, now, profile)
                    else:
                        elapsed = max(0.05, now - self._last_distance_accept_at)
                        jump_base = float(profile.thresholds.get('go_to_farm_distance_jump_base_m', 220.0))
                        jump_speed = float(profile.thresholds.get('go_to_farm_distance_jump_speed_mps', 35.0))
                        max_jump = jump_base + jump_speed * elapsed
                        suspicious_small = enemy_count < arrival_enemy_min_count and raw_distance <= false_small_distance
                        if suspicious_small or abs(raw_distance - self._last_distance_value) > max_jump:
                            self.logger.info('Go to farm ignoring suspicious distance raw=%s last=%s max_jump=%.1f gate=%s', raw_distance, self._last_distance_value, max_jump, self._arrival_gate_open)
                            return self._last_distance_value
                        else:
                            return self._accept_distance_value(raw_distance, now, profile)
    def _update_arrival_enemy_gate(self, snapshot, profile: CalibrationProfile, arrival_gate_open: bool) -> bool:
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 2.0)))
        confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_confirm_frames', 2.0)))
        enemy_count = max(len(snapshot.minimap_enemies), int(snapshot.nearby_enemy_count or 0))
        if arrival_gate_open and enemy_count >= enemy_min_count:
            self._arrival_enemy_frames += 1
        else:
            self._arrival_enemy_frames = 0
        return self._arrival_enemy_frames >= confirm_frames
    def _has_arrival_enemy_support(self, profile: CalibrationProfile, enemy_count: int) -> bool:
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 2.0)))
        return max(enemy_count, self._recent_enemy_peak(profile)) >= enemy_min_count
    def _update_distance_plateau(self, snapshot, profile: CalibrationProfile) -> bool:
        distance_value = snapshot.distance_value
        if distance_value is None or distance_value <= 0:
            self._plateau_anchor_distance = None
            self._plateau_anchor_started_at = 0.0
            return False
        else:
            tolerance_m = float(profile.thresholds.get('go_to_farm_distance_plateau_tolerance_m', 18.0))
            now = time.monotonic()
            if self._plateau_anchor_distance is None:
                self._plateau_anchor_distance = distance_value
                self._plateau_anchor_started_at = now
                return False
            else:
                if abs(distance_value - self._plateau_anchor_distance) > tolerance_m:
                    self._plateau_anchor_distance = distance_value
                    self._plateau_anchor_started_at = now
                    return False
                else:
                    plateau_seconds = float(profile.timeouts.get('go_to_farm_distance_plateau_seconds', 8.0))
                    return now - self._plateau_anchor_started_at >= plateau_seconds
    def _update_arrival_settle_tracking(self, snapshot, profile: CalibrationProfile, enemy_count: int) -> None:
        history_size = max(6, int(profile.thresholds.get('go_to_farm_arrival_enemy_window_frames', 16.0)))
        self._recent_enemy_counts.append(enemy_count)
        if len(self._recent_enemy_counts) > history_size:
            self._recent_enemy_counts = self._recent_enemy_counts[-history_size:]
        distance_value = snapshot.distance_value
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
        settle_distance = float(profile.thresholds.get('go_to_farm_arrival_settle_distance_m', 6.0))
        centered = False
        if center is not None and marker is not None:
                centered_tolerance = float(profile.thresholds.get('compass_center_tolerance_px', 12.0)) * 3.0
                centered = abs(marker[0] - center[0]) <= centered_tolerance
        low_motion_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_low_motion_confirm_frames', 3.0)))
        if distance_value is not None and distance_value <= settle_distance and centered and (self._low_motion_frames >= low_motion_confirm_frames):
            self._arrival_close_frames += 1
        else:
            self._arrival_close_frames = 0
    def _update_arrival_brake_tracking(self, snapshot, profile: CalibrationProfile) -> bool:
        distance_value = snapshot.distance_value
        coord_error = self._route_coord_error(snapshot, profile)
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
        if center is None or marker is None:
            self._arrival_brake_frames = 0
            return False
        else:
            brake_distance = float(profile.thresholds.get('go_to_farm_arrival_brake_distance_m', 8.0))
            brake_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_brake_confirm_frames', 2.0)))
            centered_tolerance = float(profile.thresholds.get('compass_center_tolerance_px', 12.0)) * 4.0
            enemy_recent_min = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0))))
            enemy_peak = self._recent_enemy_peak(profile)
            distance_close = distance_value is not None and distance_value > 0 and (distance_value <= brake_distance)
            coord_close = coord_error is not None and coord_error[3] <= brake_distance
            if (distance_close or coord_close) and abs(marker[0] - center[0]) <= centered_tolerance and (enemy_peak >= enemy_recent_min):
                self._arrival_brake_frames += 1
            else:
                self._arrival_brake_frames = 0
            return self._arrival_brake_frames >= brake_confirm_frames
    def _update_terminal_mode(self, snapshot, profile: CalibrationProfile, enemy_count: int) -> tuple[bool, bool, bool]:
        distance_value = snapshot.distance_value
        coord_error = self._route_coord_error(snapshot, profile)
        effective_distance = coord_error[3] if coord_error is not None else distance_value
        if effective_distance is None or effective_distance <= 0:
            if not self._terminal_mode_active:
                return (False, False, False)
            else:
                return (True, self._terminal_overshoot_detected, False)
        else:
            enter_distance = float(profile.thresholds.get('go_to_farm_terminal_enter_distance_m', 20.0))
            exit_distance = float(profile.thresholds.get('go_to_farm_terminal_exit_distance_m', 32.0))
            stop_distance = float(profile.thresholds.get('go_to_farm_terminal_stop_distance_m', 12.0))
            confirm_distance = float(profile.thresholds.get('go_to_farm_terminal_confirm_distance_m', 10.0))
            overshoot_margin = float(profile.thresholds.get('go_to_farm_terminal_overshoot_margin_m', 4.0))
            stop_confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_terminal_stop_confirm_frames', 2.0)))
            confirm_frames = max(1, int(profile.thresholds.get('go_to_farm_terminal_confirm_frames', 3.0)))
            enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0)))
            enemy_support = max(enemy_count, self._recent_enemy_peak(profile)) >= enemy_min_count
            center_spec = profile.points.get('compass_center')
            center = center_spec.as_pixels(profile.screen_size) if center_spec else None
            marker = snapshot.compass_marker
            marker_centered = False
            if center is not None and marker is not None:
                    centered_tolerance = float(profile.thresholds.get('compass_center_tolerance_px', 12.0)) * 4.0
                    marker_centered = abs(marker[0] - center[0]) <= centered_tolerance
            if not self._terminal_mode_active and effective_distance <= enter_distance and enemy_support:
                        self._terminal_mode_active = True
                        self._terminal_best_distance = effective_distance
                        self._terminal_overshoot_detected = False
                        self._arrival_brake_frames = 0
                        self._terminal_confirm_frames = 0
                        self.logger.info('Go to farm terminal mode entered: distance=%s coord_error=%.1f', distance_value, effective_distance)
            if not self._terminal_mode_active:
                return (False, False, False)
            else:
                if self._terminal_best_distance is None:
                    self._terminal_best_distance = effective_distance
                else:
                    self._terminal_best_distance = min(self._terminal_best_distance, effective_distance)
                if self._terminal_best_distance <= confirm_distance and effective_distance >= self._terminal_best_distance + overshoot_margin:
                        self._terminal_overshoot_detected = True
                if effective_distance >= exit_distance and self._terminal_best_distance is not None and (self._terminal_best_distance > enter_distance):
                    self._terminal_mode_active = False
                    self._terminal_best_distance = None
                    self._terminal_overshoot_detected = False
                    self._arrival_brake_frames = 0
                    self._terminal_confirm_frames = 0
                    self.logger.info('Go to farm terminal mode exited: distance=%s coord_error=%.1f', distance_value, effective_distance)
                    return (False, False, False)
                else:
                    should_brake = self._terminal_overshoot_detected or (effective_distance <= stop_distance and marker_centered)
                    if should_brake:
                        self._arrival_brake_frames += 1
                    else:
                        self._arrival_brake_frames = 0
                    should_release_forward = self._arrival_brake_frames >= stop_confirm_frames
                    near_confirm = self._terminal_best_distance is not None and self._terminal_best_distance <= confirm_distance and (marker_centered or self._terminal_overshoot_detected)
                    if should_release_forward and near_confirm:
                        self._terminal_confirm_frames += 1
                    else:
                        self._terminal_confirm_frames = 0
                    should_confirm_arrival = self._terminal_confirm_frames >= confirm_frames
                    return (True, should_release_forward, should_confirm_arrival)
    def _recent_enemy_peak(self, profile: CalibrationProfile) -> int:
        history_size = max(6, int(profile.thresholds.get('go_to_farm_arrival_enemy_window_frames', 16.0)))
        if not self._recent_enemy_counts:
            return 0
        else:
            return max(self._recent_enemy_counts[-history_size:])
    def _update_arrival_gate(self, snapshot, profile: CalibrationProfile, enemy_count: int) -> bool:
        arm_distance = float(profile.thresholds.get('go_to_farm_arrival_arm_distance_m', 80.0))
        arm_frames = max(1, int(profile.thresholds.get('go_to_farm_arrival_arm_confirm_frames', 3.0)))
        reset_distance = float(profile.thresholds.get('go_to_farm_arrival_gate_reset_distance_m', 160.0))
        enemy_min_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0)))
        enemy_support = max(enemy_count, self._recent_enemy_peak(profile)) >= enemy_min_count
        distance = snapshot.distance_value
        if distance is None or distance <= 0:
            self._arrival_gate_frames = 0
            return self._arrival_gate_open
        else:
            if distance <= arm_distance and enemy_support:
                self._arrival_gate_frames += 1
                if self._arrival_gate_frames >= arm_frames:
                    self._arrival_gate_open = True
            else:
                if distance >= reset_distance:
                    self._arrival_gate_frames = 0
                    self._arrival_gate_open = False
                else:
                    self._arrival_gate_frames = 0
            return self._arrival_gate_open
    def _arrival_distance_stable(self, profile: CalibrationProfile) -> bool:
        stable_frames = max(2, int(profile.thresholds.get('go_to_farm_arrival_stable_confirm_frames', 4.0)))
        if len(self._recent_distance_values) < stable_frames:
            return False
        else:
            recent_values = self._recent_distance_values[-stable_frames:]
            stable_max_distance = float(profile.thresholds.get('go_to_farm_arrival_stable_max_distance_m', 18.0))
            stable_variation = float(profile.thresholds.get('go_to_farm_arrival_stable_variation_m', 14.0))
            if recent_values[(-1)] > stable_max_distance:
                return False
            else:
                return max(recent_values) - min(recent_values) <= stable_variation
    def _arrival_completion_ready(self, snapshot, profile: CalibrationProfile, started_at: float, enemy_count: int, arrival_gate_open: bool, arrival_enemy_open: bool) -> bool:
        distance_value = snapshot.distance_value
        if distance_value is None or distance_value <= 0:
            return False
        else:
            if not arrival_gate_open or not arrival_enemy_open:
                return False
            else:
                if not self._arrival_distance_stable(profile):
                    return False
                else:
                    min_runtime_s = float(profile.timeouts.get('go_to_farm_min_arrival_runtime_seconds', 50.0))
                    if time.monotonic() - started_at < min_runtime_s:
                        return False
                    else:
                        required_enemy_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0))))
                        if max(enemy_count, self._recent_enemy_peak(profile)) < required_enemy_count:
                            return False
                        else:
                            if self._start_distance_value is None:
                                return False
                            else:
                                min_progress_m = float(profile.thresholds.get('go_to_farm_arrival_min_progress_m', 900.0))
                                if self._start_distance_value - distance_value < min_progress_m:
                                    return False
                                else:
                                    return True
    def _arrival_settle_ready(self, profile: CalibrationProfile, started_at: float) -> bool:
        min_runtime_s = float(profile.timeouts.get('go_to_farm_min_arrival_runtime_seconds', 50.0))
        if time.monotonic() - started_at < min_runtime_s:
            return False
        else:
            settle_confirm_frames = max(2, int(profile.thresholds.get('go_to_farm_arrival_settle_confirm_frames', 5.0)))
            if self._arrival_close_frames < settle_confirm_frames:
                return False
            else:
                required_enemy_count = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0))))
                if self._recent_enemy_peak(profile) < required_enemy_count:
                    return False
                else:
                    return True
    def _coord_arrival_ready(self, snapshot, profile: CalibrationProfile, marker_offset: float | None, move_forward: bool) -> bool:
        coord_error = self._route_coord_error(snapshot, profile)
        if coord_error is None:
            self._coord_arrival_frames = 0
            self._final_dwell_started_at = 0.0
            return False
        else:
            dx, _dy, dz, coord_distance = coord_error
            final_radius = float(profile.thresholds.get('go_to_farm_final_radius', 10.0))
            final_axis = float(profile.thresholds.get('go_to_farm_final_axis_units', final_radius))
            final_dwell_s = float(profile.timeouts.get('go_to_farm_final_dwell_sec', 0.7))
            forward_max = float(profile.thresholds.get('go_to_farm_coord_arrival_forward_max_units_per_s', 18.0))
            inside_final_box = coord_distance <= final_radius and max(abs(dx), abs(dz)) <= final_axis and (self._coord_forward_speed <= forward_max) and (marker_offset is None or marker_offset <= 180.0)
            now = time.monotonic()
            if inside_final_box and (not move_forward or self._low_motion_frames >= 1):
                if self._final_dwell_started_at <= 0.0:
                    self._final_dwell_started_at = now
                if now - self._final_dwell_started_at >= final_dwell_s:
                    self._coord_arrival_frames += 1
            else:
                self._coord_arrival_frames = 0
                self._final_dwell_started_at = 0.0
            if self._coord_arrival_frames >= 1:
                self.input.release_key('A')
                self.input.release_key('D')
                self.input.release_key('W')
                self.input.release_key('SHIFT')
                return True
            else:
                return False
    def _coord_settled_nearby(self, snapshot, profile: CalibrationProfile) -> bool:
        coord_error = self._route_coord_error(snapshot, profile)
        if coord_error is None:
            return False
        else:
            settle_distance = float(profile.thresholds.get('go_to_farm_coord_arrival_settle_distance_units', 16.0))
            settle_axis = float(profile.thresholds.get('go_to_farm_coord_arrival_settle_axis_units', 12.0))
            forward_max = float(profile.thresholds.get('go_to_farm_coord_arrival_forward_max_units_per_s', 4.5))
            return coord_error[3] <= settle_distance and max(abs(coord_error[0]), abs(coord_error[2])) <= settle_axis and (self._coord_forward_speed <= forward_max) and (self._low_motion_frames >= 1)
    def _confirm_arrival_after_stop(self, profile: CalibrationProfile, stop_event: Event) -> bool:
        # ***<module>.GoToFarmController._confirm_arrival_after_stop: Failure: Different control flow
        self.compass.stop()
        self.input.safe_release_all()
        verify_delay_s = float(profile.timeouts.get('go_to_farm_arrival_verify_delay_seconds', 0.35))
        if not self._sleep_interruptible(verify_delay_s, stop_event):
            return False
        else:
            frame = self.capture.grab_bgr()
            snapshot = self.vision.analyze(frame, profile, include_distance=True, include_world_coords=True, include_inventory=False)
            enemy_count = max(len(snapshot.minimap_enemies), int(snapshot.nearby_enemy_count or 0))
            snapshot.distance_value = self._filter_distance_value(snapshot.distance_value, enemy_count, profile)
            verify_distance = float(profile.thresholds.get('go_to_farm_arrival_verify_distance_m', 10.0))
            enemy_recent_min = max(1, int(profile.thresholds.get('go_to_farm_arrival_enemy_recent_min_count', profile.thresholds.get('go_to_farm_arrival_enemy_min_count', 3.0))))
            enemy_peak = max(enemy_count, self._recent_enemy_peak(profile))
            terminal_confirm_distance = float(profile.thresholds.get('go_to_farm_terminal_confirm_distance_m', 10.0))
            terminal_confirmed = self._terminal_best_distance is not None and self._terminal_best_distance <= terminal_confirm_distance
            coord_error = self._target_coord_error(snapshot, profile)
            coord_verify_distance = float(profile.thresholds.get('go_to_farm_final_radius', 10.0))
            coord_verify_axis = float(profile.thresholds.get('go_to_farm_final_axis_units', coord_verify_distance))
            coord_confirmed = coord_error is not None and coord_error[3] <= coord_verify_distance and (max(abs(coord_error[0]), abs(coord_error[2])) <= coord_verify_axis)
            if not coord_confirmed and self._coord_settled_nearby(snapshot, profile):
                    coord_confirmed = True
            confirmed = coord_confirmed or (snapshot.distance_value is not None and snapshot.distance_value <= verify_distance or (coord_error is not None and coord_error[3] <= coord_verify_distance)) and (enemy_peak >= enemy_recent_min or terminal_confirmed)
            if confirmed:
                self.window.focus_game_window('go-to-farm-arrival')
                final_p_hold_s = float(profile.timeouts.get('go_to_farm_arrival_final_p_hold_seconds', 0.12))
                self.input.tap_key('P', hold_s=final_p_hold_s)
                post_p_delay_s = float(profile.timeouts.get('go_to_farm_arrival_post_p_delay_seconds', 0.35))
                if not self._sleep_interruptible(post_p_delay_s, stop_event):
                    return False
                else:
                    self.input.safe_release_all()
                    self.logger.info('Go to farm arrival verified after stop: distance=%s coord_error=%s enemies=%s enemy_peak=%s final_p_hold=%.2f', snapshot.distance_value, None if coord_error is None else round(coord_error[3], 1), enemy_count, enemy_peak, final_p_hold_s)
                    return True
            else:
                self.logger.info('Go to farm arrival verification rejected: distance=%s coord_error=%s enemies=%s enemy_peak=%s', snapshot.distance_value, None if coord_error is None else round(coord_error[3], 1), enemy_count, enemy_peak)
                self._arrival_close_frames = 0
                self._arrival_brake_frames = 0
                self._terminal_confirm_frames = 0
                self._previous_motion_signature = None
                now = time.monotonic()
                self._last_progress_at = now
                self._last_distance_progress_at = now
                self.compass.reset()
                return False
    def _abort_if_stopped(self, stop_event: Event) -> bool:
        if not stop_event.is_set():
            return False
        else:
            self.compass.stop()
            self.input.safe_release_all()
            return True
    def _run_initial_departure(self, profile: CalibrationProfile, stop_event: Event) -> bool:
        total_dx = int(profile.thresholds.get('go_to_farm_initial_turn_mouse_dx', (-540.0)))
        turn_steps = max(1, int(profile.thresholds.get('go_to_farm_initial_turn_steps', 6.0)))
        step_pause_s = float(profile.timeouts.get('go_to_farm_initial_turn_step_pause_seconds', 0.05))
        run_seconds = float(profile.timeouts.get('go_to_farm_initial_run_seconds', 5.0))
        settle_s = float(profile.timeouts.get('go_to_farm_initial_settle_seconds', 0.1))
        step_dx = int(round(total_dx / turn_steps))
        self.logger.info('Go to farm initial departure: total_dx=%s steps=%s run_seconds=%.1f', total_dx, turn_steps, run_seconds)
        for _ in range(turn_steps):
            if stop_event.is_set():
                return False
            else:
                self.input.move_mouse_relative(step_dx, 0)
                if not self._sleep_interruptible(step_pause_s, stop_event):
                    return False
        self.input.press_key('W')
        self.input.press_key('SHIFT')
        if not self._sleep_interruptible(run_seconds, stop_event):
            return False
        else:
            self.input.release_key('W')
            self.input.release_key('SHIFT')
            return self._sleep_interruptible(settle_s, stop_event)
    def _motion_signature(self, frame: np.ndarray, profile: CalibrationProfile) -> np.ndarray:
        frame_h, frame_w = frame.shape[:2]
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
        crop = frame[y:y + h, x:x + w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.resize(gray, (96, 72), interpolation=cv2.INTER_AREA)
    def _update_progress_tracking(self, frame: np.ndarray, snapshot, profile: CalibrationProfile, distance_actionable: bool) -> tuple[float, bool, bool, bool]:
        now = time.monotonic()
        motion_signature = self._motion_signature(frame, profile)
        motion_score = 0.0
        progress = False
        distance_progress = False
        coord_progress = False
        motion_threshold = float(profile.thresholds.get('go_to_farm_motion_diff_threshold', 3.8))
        strong_motion_threshold = float(profile.thresholds.get('go_to_farm_motion_strong_progress_threshold', motion_threshold * 2.2))
        coord_visual_motion_threshold = float(profile.thresholds.get('go_to_farm_coord_visual_motion_progress_threshold', strong_motion_threshold))
        low_motion_threshold = float(profile.thresholds.get('go_to_farm_low_motion_threshold', 2.0))
        distance_step = int(profile.thresholds.get('go_to_farm_distance_progress_step', 2.0))
        coord_progress_step = int(profile.thresholds.get('go_to_farm_coord_progress_step_units', 4.0))
        coord_progress_soft_step = float(profile.thresholds.get('go_to_farm_coord_progress_soft_step_units', 1.2))
        coord_jump_max = int(profile.thresholds.get('go_to_farm_coord_jump_max_units', 120.0))
        coord_velocity_alpha = float(profile.thresholds.get('go_to_farm_coord_velocity_ema_alpha', 0.45))
        coord_forward_progress_threshold = float(profile.thresholds.get('go_to_farm_coord_forward_progress_units_per_s', 0.75))
        marker_progress_step = float(profile.thresholds.get('go_to_farm_marker_progress_step_px', 10.0))
        marker_progress_near_center_px = float(profile.thresholds.get('go_to_farm_marker_progress_near_center_px', 42.0))
        marker_progress = False
        if self._previous_motion_signature is not None:
            diff = cv2.absdiff(motion_signature, self._previous_motion_signature)
            motion_score = float(np.mean(diff))
        self._previous_motion_signature = motion_signature
        visual_route_motion = self._last_world_coords is not None and self._route_waypoints and (self._nav_state in {'RUN', 'COAST'}) and (motion_score >= coord_visual_motion_threshold)
        if snapshot.distance_value is not None:
            if self._last_distance_progress_value is None:
                distance_progress = True
            else:
                if snapshot.distance_value <= self._last_distance_progress_value - distance_step:
                    distance_progress = True
            self._last_distance_progress_value = snapshot.distance_value
            if distance_progress:
                self._last_distance_progress_at = now
        stable_world = self._stable_world_coords
        if stable_world is not None:
            current_world = (stable_world[0], stable_world[2])
            if self._last_world_coords is None:
                self._last_world_coords = current_world
                self._last_world_coords_at = now
                self._last_world_progress_at = now
                target_coord_error = self._target_coord_error(snapshot, profile)
                if target_coord_error is not None:
                    self._last_target_coord_error = target_coord_error[3]
                coord_progress = True
            else:
                dx_world = current_world[0] - self._last_world_coords[0]
                dz_world = current_world[1] - self._last_world_coords[1]
                coord_delta = max(abs(dx_world), abs(dz_world))
                dt = max(0.001, now - self._last_world_coords_at)
                max_coord_jump_per_sec = float(profile.thresholds.get('go_to_farm_max_coord_jump_per_sec', 250.0))
                dynamic_coord_jump_limit = max(coord_jump_max, dt * max_coord_jump_per_sec)
                if coord_delta <= dynamic_coord_jump_limit:
                    vx = float(dx_world) / dt
                    vz = float(dz_world) / dt
                    self._coord_velocity_x = (1.0 - coord_velocity_alpha) * self._coord_velocity_x + coord_velocity_alpha * vx
                    self._coord_velocity_z = (1.0 - coord_velocity_alpha) * self._coord_velocity_z + coord_velocity_alpha * vz
                    target_coord_error = self._final_coord_error(snapshot, profile)
                    if target_coord_error is not None:
                        current_coord_error = target_coord_error[3]
                        error_forward_speed = 0.0
                        if self._last_target_coord_error is not None:
                            error_forward_speed = (self._last_target_coord_error - current_coord_error) / dt
                        target_norm = float(np.hypot(float(target_coord_error[0]), float(target_coord_error[2])))
                        effective_forward_speed = error_forward_speed
                        if target_norm > 1e-06:
                            ux = float(target_coord_error[0]) / target_norm
                            uz = float(target_coord_error[2]) / target_norm
                            vector_forward_speed = vx * ux + vz * uz
                            lateral_speed = abs(vx * -uz + vz * ux)
                            effective_forward_speed = max(error_forward_speed, vector_forward_speed)
                            self._coord_forward_speed = (1.0 - coord_velocity_alpha) * self._coord_forward_speed + coord_velocity_alpha * effective_forward_speed
                            self._coord_lateral_speed = (1.0 - coord_velocity_alpha) * self._coord_lateral_speed + coord_velocity_alpha * lateral_speed
                        else:
                            self._coord_forward_speed = (1.0 - coord_velocity_alpha) * self._coord_forward_speed + coord_velocity_alpha * error_forward_speed
                        if self._last_target_coord_error is None:
                            coord_progress = True
                        else:
                            if current_coord_error <= self._last_target_coord_error - coord_progress_step:
                                coord_progress = True
                            else:
                                if current_coord_error <= self._last_target_coord_error - coord_progress_soft_step:
                                    coord_progress = True
                                else:
                                    if self._coord_forward_speed >= coord_forward_progress_threshold:
                                        coord_progress = True
                        self._last_target_coord_error = current_coord_error
                    else:
                        coord_progress = coord_delta >= coord_progress_step
                    self._last_world_coords = current_world
                    self._last_world_coords_at = now
                    if coord_progress:
                        self._last_world_progress_at = now
        center_spec = profile.points.get('compass_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        marker = snapshot.compass_marker
        if center is not None and marker is not None:
            marker_offset_abs = float(abs(marker[0] - center[0]))
            if self._last_marker_offset_abs is not None:
                marker_improvement = self._last_marker_offset_abs - marker_offset_abs
                marker_progress = marker_improvement >= marker_progress_step
                if not marker_progress and self._last_marker_offset_abs > marker_progress_near_center_px and (marker_offset_abs <= marker_progress_near_center_px):
                            marker_progress = True
            self._last_marker_offset_abs = marker_offset_abs
        else:
            self._last_marker_offset_abs = None
        if distance_progress and distance_actionable:
            progress = True
        else:
            if coord_progress:
                progress = True
            else:
                if visual_route_motion:
                    progress = True
                else:
                    if snapshot.distance_value is not None and distance_actionable:
                        progress = marker_progress
                    else:
                        if self._last_world_coords is None and motion_score >= strong_motion_threshold:
                            progress = True
                        else:
                            if self._last_world_coords is None and motion_score >= motion_threshold:
                                    progress = True
        if progress:
            self._last_progress_at = now
            if visual_route_motion:
                self._last_segment_progress_at = now
            if coord_progress:
                self._recent_coord_progress_at = now
            self._stuck_attempt = 0
            self._low_motion_frames = 0
            self._recover_escape_direction = 0
            if distance_actionable and snapshot.distance_value is not None and (snapshot.distance_value > 0):
                        self._plateau_anchor_distance = snapshot.distance_value
                        self._plateau_anchor_started_at = now
        else:
            if motion_score <= low_motion_threshold:
                self._low_motion_frames += 1
            else:
                self._low_motion_frames = 0
        return (motion_score, progress, distance_progress, coord_progress)
    def _recover_from_stuck(self, snapshot, profile: CalibrationProfile, stop_event: Event) -> bool:
        if self._abort_if_stopped(stop_event):
            return False
        else:
            self._set_navigation_state('RECOVERY', 'stuck-trigger', None, None)
            self._stuck_attempt += 1
            back_seconds = float(profile.timeouts.get('go_to_farm_recover_back_seconds', 0.45))
            strafe_seconds = float(profile.timeouts.get('go_to_farm_recover_strafe_seconds', 0.4))
            settle_seconds = float(profile.timeouts.get('go_to_farm_recover_settle_seconds', 0.2))
            turn_dx = int(profile.thresholds.get('go_to_farm_recover_turn_dx', 160.0))
            aligned_offset_px = float(profile.thresholds.get('go_to_farm_recover_aligned_offset_px', 22.0))
            aligned_no_turn_attempts = max(0, int(profile.thresholds.get('go_to_farm_recover_aligned_no_turn_attempts', 2.0)))
            aligned_turn_dx = int(profile.thresholds.get('go_to_farm_recover_aligned_turn_dx', 72.0))
            marker_turn_gain = float(profile.thresholds.get('go_to_farm_recover_marker_turn_gain', 0.55))
            strength_scale = min(2.4, 1.0 + 0.35 * max(0, self._stuck_attempt - 1))
            back_seconds *= min(1.9, strength_scale)
            strafe_seconds *= min(2.2, strength_scale)
            turn_dx = int(round(turn_dx * min(2.6, 1.0 + 0.45 * max(0, self._stuck_attempt - 1))))
            self.logger.info('Go to farm anti-stuck attempt=%s distance=%s marker=%s', self._stuck_attempt, snapshot.distance_value, snapshot.compass_marker)
            self.input.release_key('A')
            self.input.release_key('D')
            self.input.release_key('W')
            self.input.release_key('SHIFT')
            self.input.press_key('S')
            if not self._sleep_interruptible(back_seconds, stop_event):
                return False
            else:
                self.input.release_key('S')
                raw_offset_x = None
                aligned_recover = False
                direction = self._recover_escape_direction or ((-1) if self._stuck_attempt % 2 == 1 else 1)
                center_spec = profile.points.get('compass_center')
                center = center_spec.as_pixels(profile.screen_size) if center_spec else None
                marker = snapshot.compass_marker
                target_coord_error = self._final_coord_error(snapshot, profile)
                coord_heading_min_speed = float(profile.thresholds.get('go_to_farm_coord_heading_min_speed_units_per_s', 3.5))
                coord_heading_cross_deadzone = float(profile.thresholds.get('go_to_farm_coord_heading_cross_deadzone', 0.05))
                coord_heading_speed = float(np.hypot(self._coord_velocity_x, self._coord_velocity_z))
                if target_coord_error is not None and target_coord_error[3] > 0.001 and (coord_heading_speed >= coord_heading_min_speed):
                            ux = float(target_coord_error[0]) / target_coord_error[3]
                            uz = float(target_coord_error[2]) / target_coord_error[3]
                            hx = self._coord_velocity_x / coord_heading_speed
                            hz = self._coord_velocity_z / coord_heading_speed
                            cross = hx * uz - hz * ux
                            if abs(cross) >= coord_heading_cross_deadzone:
                                direction = 1 if cross < 0 else (-1)
                                self._recover_escape_direction = direction
                if center is not None and marker is not None:
                    raw_offset_x = float(marker[0] - center[0])
                    aligned_recover = abs(raw_offset_x) <= aligned_offset_px
                    if self._recover_escape_direction == 0 and (not aligned_recover) and (abs(raw_offset_x) >= 4):
                        direction = 1 if raw_offset_x > 0 else (-1)
                        self._recover_escape_direction = 0
                    else:
                        if aligned_recover:
                            if self._recover_escape_direction == 0:
                                self._recover_escape_direction = direction
                            direction = self._recover_escape_direction
                        else:
                            self._recover_escape_direction = direction
                else:
                    self._recover_escape_direction = direction
                strafe_key = 'A' if direction < 0 else 'D'
                self.input.press_key(strafe_key)
                if not self._sleep_interruptible(strafe_seconds, stop_event):
                    return False
                else:
                    self.input.release_key(strafe_key)
                    turn_dx_signed = 0
                    if aligned_recover:
                        if self._stuck_attempt > aligned_no_turn_attempts:
                            turn_dx_signed = aligned_turn_dx * direction
                    else:
                        if raw_offset_x is not None:
                            turn_strength = max(aligned_turn_dx, int(round(abs(raw_offset_x) * marker_turn_gain)))
                            turn_dx_signed = min(turn_dx, turn_strength) * direction
                        else:
                            turn_dx_signed = aligned_turn_dx * direction
                    if turn_dx_signed!= 0:
                        self.input.move_mouse_relative(turn_dx_signed, 0)
                    if not self._sleep_interruptible(settle_seconds, stop_event):
                        return False
                    else:
                        self._previous_motion_signature = None
                        now = time.monotonic()
                        self._last_progress_at = now
                        self._last_distance_progress_at = now
                        self._plateau_anchor_distance = snapshot.distance_value
                        self._plateau_anchor_started_at = now
                        self._coord_velocity_x = 0.0
                        self._coord_velocity_z = 0.0
                        self._coord_forward_speed = 0.0
                        self._coord_lateral_speed = 0.0
                        self._coord_heading_rad = None
                        self._coord_heading_confidence = 0.0
                        self._coord_heading_at = 0.0
                        self._final_dwell_started_at = 0.0
                        self._last_segment_metric = None
                        self._last_segment_progress_at = now
                        recover_settle_seconds = float(profile.timeouts.get('go_to_farm_post_recover_steer_settle_seconds', 0.55))
                        recover_lock_seconds = float(profile.timeouts.get('go_to_farm_recover_lock_seconds', max(recover_settle_seconds, 0.85)))
                        target_coord_error = self._target_coord_error(snapshot, profile)
                        self._steer_direction = direction
                        self._steer_hold_until = now + recover_settle_seconds
                        self._last_mouse_turn_at = now
                        self._last_mouse_turn_direction = direction
                        self._post_recover_steer_settle_until = now + recover_settle_seconds
                        self._recover_lock_direction = direction
                        self._recover_lock_until = now + recover_lock_seconds
                        self._recover_lock_reference_error = None if target_coord_error is None else target_coord_error[3]
                        self._set_navigation_state('ALIGN', 'recover-finished', None, None)
                        return True
    def go_to_farm(self, profile: CalibrationProfile, stop_event: Event) -> bool:
        # irreducible cflow, using cdg fallback
        # ***<module>.GoToFarmController.go_to_farm: Failure: Compilation Error
        start_delay_s = float(profile.timeouts.get('go_to_farm_start_delay_seconds', 5.0))
        timeout_s = float(profile.timeouts.get('go_to_farm_timeout_seconds', 1800.0))
        log_every_s = float(profile.timeouts.get('go_to_farm_status_log_seconds', 5.0))
        stuck_seconds = float(profile.timeouts.get('go_to_farm_stuck_seconds', 5.0))
        if self._abort_if_stopped(stop_event):
            return
            self.compass.stop()
            self.input.safe_release_all()
            self.window.focus_game_window('go-to-farm')
            self.input.safe_release_all()
            if not self._ensure_camera_control(profile, stop_event):
                return False
                self.input.tap_key('P', hold_s=0.06)
                self.logger.info('Go to farm started: pressed P, waiting %.1fs before run', start_delay_s)
                if not self._sleep_interruptible(start_delay_s, stop_event):
                    return False
                    use_initial_departure = bool(profile.thresholds.get('go_to_farm_use_initial_departure', 0.0))
                    if use_initial_departure:
                        if not self._run_initial_departure(profile, stop_event):
                            return False
                            self.compass.reset()
                            self._reset_progress_tracking()
                            self._prepare_route(profile)
                            route_target = self._route_target()
                            if route_target is not None:
                                self.logger.info('Go to farm route prepared: points=%s start_target=(%s,%s,%s) final_target=(%s,%s,%s)', len(self._route_waypoints), route_target[0], route_target[1], route_target[2], self._route_waypoints[(-1)][0], self._route_waypoints[(-1)][1], self._route_waypoints[(-1)][2])
                            started_at = time.monotonic()
                            next_log_at = started_at
                            while time.monotonic() - started_at <= timeout_s:
                                if self._abort_if_stopped(stop_event):
                                    return False
                                    frame = self.capture.grab_bgr()
                                    if self._abort_if_stopped(stop_event):
                                        return False
                                        snapshot = self.vision.analyze(frame, profile, include_distance=True, include_world_coords=True, include_inventory=False)
                                        stable_world = self._observe_world_coords(snapshot, profile)
                                        if self._abort_if_stopped(stop_event):
                                            return False
                                            self._align_route_start(profile)
                                            self._try_advance_route(snapshot, profile)
                                            self._update_segment_progress(snapshot, profile)
                                            target_coord_error = self._target_coord_error(snapshot, profile)
                                            coord_control_active = target_coord_error is not None
                                            route_final_target = self._route_is_final() or not self._route_waypoints
                                            final_target_coord_error = self._final_coord_error(snapshot, profile) if coord_control_active else None
                                            heading_info = self._compute_heading_error(snapshot, profile) if coord_control_active else None
                                            heading_error_deg = None if heading_info is None else heading_info[1]
                                            near_target_mode_distance = float(profile.thresholds.get('go_to_farm_near_target_mode_distance_units', 180.0))
                                            near_target_control = coord_control_active and route_final_target and (final_target_coord_error is not None) and (final_target_coord_error[3] <= near_target_mode_distance)
                                            enemy_count = max(len(snapshot.minimap_enemies), int(snapshot.nearby_enemy_count or 0))
                                            raw_distance_value = snapshot.distance_value
                                            if coord_control_active:
                                                snapshot.distance_value = None
                                                self._recent_distance_values = []
                                                self._arrival_gate_frames = 0
                                                self._arrival_gate_open = False
                                                self._arrival_enemy_frames = 0
                                                self._terminal_mode_active = False
                                                self._terminal_best_distance = None
                                                self._terminal_overshoot_detected = False
                                                self._terminal_confirm_frames = 0
                                                self._arrival_brake_frames = 0
                                                self._arrival_close_frames = 0
                                                self._plateau_anchor_distance = None
                                                self._plateau_anchor_started_at = 0.0
                                                enemy_support = False
                                                terminal_mode_active = False
                                                terminal_release_forward = False
                                                terminal_confirm_arrival = False
                                                arrival_gate_open = False
                                                arrival_enemy_open = False
                                                distance_actionable = False
                                                distance_plateau_active = False
                                                arrival_brake_ready = False
                                            else:
                                                snapshot.distance_value = self._filter_distance_value(snapshot.distance_value, enemy_count, profile)
                                                self._update_arrival_settle_tracking(snapshot, profile, enemy_count)
                                                enemy_support = self._has_arrival_enemy_support(profile, enemy_count)
                                                terminal_mode_active, terminal_release_forward, terminal_confirm_arrival = self._update_terminal_mode(snapshot, profile, enemy_count)
                                                arrival_gate_open = self._update_arrival_gate(snapshot, profile, enemy_count)
                                                arrival_enemy_open = self._update_arrival_enemy_gate(snapshot, profile, arrival_gate_open)
                                                distance_actionable = enemy_support or arrival_gate_open or terminal_mode_active
                                                distance_plateau_active = self._update_distance_plateau(snapshot, profile) if distance_actionable else False
                                                arrival_brake_ready = self._update_arrival_brake_tracking(snapshot, profile)
                                            coord_navigation_active, coord_navigation_distance, coord_navigation_marker_offset, coord_navigation_move_forward = self._apply_coordinate_navigation(snapshot, profile, terminal_mode_active=terminal_mode_active)
                                            if coord_navigation_active:
                                                arrived = False
                                            else:
                                                arrived = self.compass.update_long(snapshot, profile, distance_gate_open=arrival_gate_open or terminal_mode_active)
                                            if self._abort_if_stopped(stop_event):
                                                return False
                                                motion_score, progress, distance_progress, coord_progress = self._update_progress_tracking(frame, snapshot, profile, distance_actionable=distance_actionable or arrival_gate_open)
                                                coord_settled_nearby = self._coord_settled_nearby(snapshot, profile)
                                                coord_dock_nearby = self._coord_in_dock_zone(snapshot, profile)
                                                now = time.monotonic()
                                                if now >= next_log_at:
                                                    logged_world = stable_world
                                                    route_target = self._route_target()
                                                    return self.logger.info('Go to farm progress: distance=%s raw_distance=%s coords=(%s,%s,%s) coord_error=%s final_error=%s route=%s/%s route_target=(%s,%s,%s) marker=%s nav_offset=%s nav_source=%s nav_state=%s coord_valid=%s coord_reason=%s heading_error=%s pred_offset=%s pred_align=%s pred_gain=%s speed=(%.1f,%.1f) forward=%.1f lateral=%.1f stamina=%.2f enemies=%s motion=%.2f progress=%s distance_progress=%s coord_progress=%s gate=%s enemy_gate=%s coord_mode=%s route_final=%s', snapshot.distance_value, raw_distance_value, None if logged_world is None else logged_world[0], None if logged_world is None else logged_world[1], None if logged_world is None else logged_world[1], None if logged_world is None else logged_world[1], None if logged_world is None else self._nav_state, self._coord_valid, self._coord_validity_reason, self.heading_error_deg, self._last_predictive_offset, self._last_predictive_align, self._last_predictive_improvement, self._coord_velocity_x, self._coord_velocity_z, self._coord_forward_speed, self._coord_lateral_speed, self.stamina_ratio, self.(-1.0), self.enemy_count, self.motion_score, self.progress, self.distance_progress, self.coord_progress, self.arrival_gate_open, self.arrival_enemy_open, self.coord_control_active, self.route_final_target, self.<Code311 code object _camera_probe_region at 0x708366527570, file mmobot\bot\go_to_farm_controller.py>, line 104, self.before, self.np.ndarray, self.after, self.region, self.<Code311 code object _frame_motion_score at 0x708366527680, file mmobot\bot\go_to_farm_controller.py>, line 126, self.float | None, self.<Code311 code object _probe_camera_motion at 0x708366527790, file mmobot\bot\go_to_farm_controller.py>, line 143, self
                                                    next_log_at = now + log_every_s
                                                if terminal_mode_active:
                                                    self.input.release_key('SHIFT')
                                                if terminal_release_forward:
                                                    self.input.release_key('W')
                                                if route_final_target and terminal_confirm_arrival and self._confirm_arrival_after_stop(profile, stop_event):
                                                    self.logger.info('Go to farm terminal stop at destination: distance=%s best_distance=%s overshoot=%s', snapshot.distance_value, self._terminal_best_distance, self._terminal_overshoot_detected)
                                                        return True
                                                    if route_final_target and arrival_brake_ready:
                                                        self.input.release_key('W')
                                                        self.input.release_key('SHIFT')
                                                        if self._confirm_arrival_after_stop(profile, stop_event):
                                                            self.logger.info('Go to farm braking stop at destination: distance=%s enemy_peak=%s brake_frames=%s', snapshot.distance_value, self._recent_enemy_peak(profile), self._arrival_brake_frames)
                                                                return True
                                                            if route_final_target and coord_navigation_active and self._coord_arrival_ready(snapshot, profile, coord_navigation_marker_offset, coord_navigation_move_forward) and self._confirm_arrival_after_stop(profile, stop_event):
                                                                self.logger.info('Go to farm coordinate finish: coords=(%s,%s,%s) coord_error=%s marker=%s', None if stable_world is None else stable_world[0], None if stable_world is None else stable_world[1], None if stable_world is None else stable_world[2], None if final_target_coord_error is None else round(final_target_coord_error[3], 1), snapshot.compass_marker)
                                                                    return True
                                                                if route_final_target and arrived:
                                                                    if self._arrival_completion_ready(snapshot, profile, started_at, enemy_count, arrival_gate_open, arrival_enemy_open):
                                                                        if self._confirm_arrival_after_stop(profile, stop_event):
                                                                            self.logger.info('Go to farm completed successfully')
                                                                                return True
                                                                            self.logger.info('Go to farm suppressed premature arrival: distance=%s start_distance=%s enemies=%s gate=%s enemy_gate=%s history=%s', snapshot.distance_value, self._start_distance_value, enemy_count, arrival_gate_open, arrival_enemy_open, self._recent_distance_values[(-4):])
                                                                            self.compass.arrival_frames = 0
                                                                                if route_final_target and self._arrival_settle_ready(profile, started_at) and self._confirm_arrival_after_stop(profile, stop_event):
                                                                                    self.logger.info('Go to farm settled at destination: distance=%s enemy_peak=%s close_frames=%s', snapshot.distance_value, self._recent_enemy_peak(profile), self._arrival_close_frames)
                                                                                        return True
                                                                                    if not terminal_mode_active and distance_plateau_active:
                                                                                        self.logger.info('Go to farm distance plateau detected: distance=%s marker=%s anchor=%s', snapshot.distance_value, snapshot.compass_marker, self._plateau_anchor_distance)
                                                                                        if not self._recover_from_stuck(snapshot, profile, stop_event):
                                                                                            return False
                                                                                            center_spec = profile.points.get('compass_center')
                                                                                            center = center_spec.as_pixels(profile.screen_size) if center_spec else None
                                                                                            marker_centered = False
                                                                                            marker_near_center = False
                                                                                            if center is not None and snapshot.compass_marker is not None:
                                                                                                    marker_offset_x = abs(snapshot.compass_marker[0] - center[0])
                                                                                                    base_tolerance = float(profile.thresholds.get('compass_center_tolerance_px', 12.0))
                                                                                                    marker_centered = marker_offset_x <= base_tolerance * 2.0
                                                                                                    marker_near_center = marker_offset_x <= base_tolerance * 4.0
                                                                                            distance_stuck_seconds = float(profile.timeouts.get('go_to_farm_distance_stuck_seconds', max(3.5, stuck_seconds - 1.0)))
                                                                                            low_motion_confirm_frames = max(2, int(profile.thresholds.get('go_to_farm_low_motion_confirm_frames', 6.0)))
                                                                                            low_motion_ready = self._low_motion_frames >= low_motion_confirm_frames
                                                                                            current_low_motion = motion_score <= float(profile.thresholds.get('go_to_farm_low_motion_threshold', 2.0))
                                                                                            coord_stalled = self._is_stuck_from_segment_progress(profile)
                                                                                            recent_progress_grace_s = float(profile.timeouts.get('go_to_farm_recent_progress_recover_grace_seconds', 1.6))
                                                                                            recent_coord_progress = coord_progress or now - self._recent_coord_progress_at <= recent_progress_grace_s
                                                                                            route_transition_active = now < self._route_transition_until
                                                                                            recovery_state_active = self._nav_state in {'COAST', 'RUN'}
                                                                                            coord_stuck_marker_threshold = float(profile.thresholds.get('go_to_farm_compass_stuck_offset_px', 34.0))
                                                                                            coord_initial_grace_seconds = float(profile.timeouts.get('go_to_farm_coord_initial_grace_seconds', max(6.0, stuck_seconds + 1.0)))
                                                                                            if near_target_control:
                                                                                                coord_initial_grace_seconds = max(coord_initial_grace_seconds, float(profile.timeouts.get('go_to_farm_near_target_no_recover_seconds', 8.0)))
                                                                                            coord_navigation_near_aligned = coord_navigation_active and coord_navigation_marker_offset is not None and (coord_navigation_marker_offset <= coord_stuck_marker_threshold)
                                                                                            coord_navigation_no_marker = coord_navigation_active and snapshot.compass_marker is None
                                                                                            coord_navigation_ready = not coord_navigation_active or now - started_at >= coord_initial_grace_seconds or coord_progress
                                                                                            obstacle_recover_offset = float(profile.thresholds.get('go_to_farm_compass_obstacle_recover_offset_px', profile.thresholds.get('go_to_farm_compass_stop_forward_turn_px', 92.0)))
                                                                                            obstacle_recover_seconds = float(profile.timeouts.get('go_to_farm_obstacle_recover_seconds', max(2.5, stuck_seconds - 2.0)))
                                                                                            obstacle_forward_min = float(profile.thresholds.get('go_to_farm_coord_obstacle_forward_min_units_per_s', 6.0))
                                                                                            obstacle_blocked = not terminal_mode_active and recovery_state_active and (not route_transition_active) and coord_navigation_active and coord_navigation_move_forward and (snapshot.compass_marker is None or coord_navigation_marker_offset is not None and coord_navigation_marker_offset <= obstacle_recover_offset) and low_motion_ready and current_low_motion and (self._coord_forward_speed <= obstacle_forward_min) and (now - self._last_progress_at >= obstacle_recover_seconds) and (not recent_coord_progress)
                                                                                            coord_no_marker_recover = not terminal_mode_active and recovery_state_active and (not route_transition_active) and coord_navigation_no_marker and (coord_navigation_ready and coord_stalled or (low_motion_ready and current_low_motion and (now - self._last_progress_at >= stuck_seconds))) and (not recent_coord_progress)
                                                                                            recover_cooldown_active = now < self._recover_lock_until
                                                                                            if not recover_cooldown_active and (not coord_dock_nearby) and (not near_target_control or now - started_at >= coord_initial_grace_seconds) and (not obstacle_blocked) and (not terminal_mode_active) and (not recovery_state_active) and (not coord_navigation_ready) and (not coord_stalled) and (not current_low_motion) and (not marker_centered) and (now - self._last_distance_progress_at >= distance_stuck_seconds):
                                                                                                if not self._recover_from_stuck(snapshot, profile, stop_event):
                                                                                                    return False
                                                                                                        self.logger.warning('Go to farm failed: timeout %.1fs reached', timeout_s)
                                                                                                            return False