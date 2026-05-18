# Source Generated with Decompyle++
# File: navigation_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from mmobot.bot.gather_logic_modes import DEFAULT_GATHER_LOGIC_MODE, normalize_gather_logic_mode
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import MinimapEnemyCandidate, VisionSnapshot
GatherMemoryNode = <NODE:12>()
GatherCluster = <NODE:12>()
GatherRouteStep = <NODE:12>()

class NavigationController:
    
    def __init__(self = None, input_controller = None, config = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.input = input_controller
        self.config = config
        self.visited_targets = []
        self.distance_history = deque(maxlen = 30)
        self.world_coord_history = deque(maxlen = 60)
        self.active_target = None
        self.active_target_started_at = 0
        self.active_target_missing_frames = 0
        self.active_target_last_move_at = 0
        self.active_target_stable_frames = 0
        self.active_target_initial_distance = None
        self.active_target_best_distance = None
        self.search_direction = 1
        self.search_step = 0
        self.anti_stuck_attempt = 0
        self.memory_nodes = []
        self.route_steps = []
        self.route_index = 0
        self.last_route_build_at = 0
        self.route_step_missing_started_at = 0
        self.reach_confirm_frames = 0
        self.active_target_stuck_attempts = 0
        self.last_reached_count = 0
        self._last_gather_steering_log_at = 0

    
    def reset(self = None):
        self.visited_targets.clear()
        self.distance_history.clear()
        self.world_coord_history.clear()
        self.active_target = None
        self.active_target_started_at = 0
        self.active_target_missing_frames = 0
        self.active_target_last_move_at = 0
        self.active_target_stable_frames = 0
        self.active_target_initial_distance = None
        self.active_target_best_distance = None
        self.search_direction = 1
        self.search_step = 0
        self.anti_stuck_attempt = 0
        self.memory_nodes.clear()
        self.route_steps.clear()
        self.route_index = 0
        self.last_route_build_at = 0
        self.route_step_missing_started_at = 0
        self.reach_confirm_frames = 0
        self.active_target_stuck_attempts = 0
        self.last_reached_count = 0
        self._last_gather_steering_log_at = 0

    
    def _purge_visited(self = None, ttl_s = None):
        pass
    # WARNING: Decompyle incomplete

    _distance = (lambda a = None, b = None: math.hypot(a[0] - b[0], a[1] - b[1]))()
    _signed_angle = (lambda forward = None, target_vec = None: cross = forward[0] * target_vec[1] - forward[1] * target_vec[0]dot = forward[0] * target_vec[0] + forward[1] * target_vec[1]math.atan2(cross, dot))()
    
    def _center(self = None, profile = None):
        center_spec = profile.points.get('minimap_center')
        return center_spec.as_pixels(profile.screen_size) if center_spec else None

    
    def _gather_logic_mode(self = None, profile = None):
        return normalize_gather_logic_mode(profile.settings.get('gather_logic_mode', DEFAULT_GATHER_LOGIC_MODE))

    
    def _effective_memory_half_extent(self = None, profile = None):
        half_extent = float(profile.thresholds.get('gather_memory_half_extent_px', 0))
        if half_extent > 0:
            return half_extent
        minimap_spec = None.zones.get('minimap_region')
        minimap_rect = minimap_spec.as_pixels(profile.screen_size) if minimap_spec else None
    # WARNING: Decompyle incomplete

    
    def _forward_vector(self = None, snapshot = None, profile = None):
        confidence_threshold = float(profile.thresholds.get('minimap_heading_confidence_threshold', 0.18))
    # WARNING: Decompyle incomplete

    
    def _set_active_target(self = None, target = None, track_distance = None):
        now = time.monotonic()
    # WARNING: Decompyle incomplete

    
    def clear_active_target(self = None):
        self._set_active_target(None)
        self.distance_history.clear()
        self.world_coord_history.clear()

    
    def consume_reached_count(self = None):
        count = self.last_reached_count
        self.last_reached_count = 0
        return count

    
    def _track_active_target(self = None, snapshot = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _is_recently_visited(self = None, point = None, reuse_distance = None):
        pass
    # WARNING: Decompyle incomplete

    
    def _remember_collected_enemies(self = None, snapshot = None, center = None, profile = ('snapshot', 'VisionSnapshot', 'center', 'tuple[int, int]', 'profile', 'CalibrationProfile', 'return', 'None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _find_matching_node(self = None, point = None, match_distance = None):
        best_node = None
        best_distance = float('inf')
        for node in self.memory_nodes:
            if node.reached:
                continue
            distance = self._distance(node.current_point, point)
            if distance <= match_distance and distance < best_distance:
                best_node = node
                best_distance = distance
            return best_node

    
    def _observed_enemy_candidates(self, snapshot = None, center = None, half_extent = None, reuse_distance = ('snapshot', 'VisionSnapshot', 'center', 'tuple[int, int]', 'half_extent', 'float', 'reuse_distance', 'float', 'return', 'list[MinimapEnemyCandidate]')):
        pass
    # WARNING: Decompyle incomplete

    _angle_delta_deg = (lambda a_deg = None, b_deg = None: abs(((a_deg - b_deg) + 180) % 360 - 180))()
    
    def _score_candidate_for_anchor(self = None, anchor = None, candidate = None, center = ('anchor', 'tuple[int, int]', 'candidate', 'MinimapEnemyCandidate', 'center', 'tuple[int, int] | None', 'outward_tolerance_px', 'float', 'angle_threshold_deg', 'float', 'return', 'tuple[float, float, float, float] | None'), *, outward_tolerance_px, angle_threshold_deg):
        distance = self._distance(anchor, candidate.point)
    # WARNING: Decompyle incomplete

    
    def _find_matching_node_consistent(self = None, point = None, match_distance = None, center = ('point', 'tuple[int, int]', 'match_distance', 'float', 'center', 'tuple[int, int] | None', 'outward_tolerance_px', 'float', 'angle_threshold_deg', 'float', 'return', 'GatherMemoryNode | None'), *, outward_tolerance_px, angle_threshold_deg):
        best_node = None
        best_score = None
    # WARNING: Decompyle incomplete

    
    def _update_memory(self = None, snapshot = None, profile = None, center = ('snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'center', 'tuple[int, int]', 'return', 'None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _route_cost(self, current_point = None, node = None, remaining = None, profile = ('current_point', 'tuple[int, int]', 'node', 'GatherMemoryNode', 'remaining', 'list[GatherMemoryNode]', 'profile', 'CalibrationProfile', 'return', 'tuple[float, int, float]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _build_clusters(self = None, candidates = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    _cluster_point = (lambda cluster = None: (int(round(cluster.centroid[0])), int(round(cluster.centroid[1]))))()
    
    def _cluster_representative(self = None, cluster = None, entry_point = None, pinned_node = (None,)):
        pass
    # WARNING: Decompyle incomplete

    
    def _cluster_score(self, center, forward_vector = None, cluster = None, clusters = None, profile = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'cluster', 'GatherCluster', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'float')):
        return self._cluster_route_value(current_point = center, current_direction = forward_vector, cluster = cluster, remaining = clusters, profile = profile)

    
    def _rank_clusters(self, center = None, forward_vector = None, clusters = None, profile = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _cluster_radius(self = None, center = None, cluster = None):
        return self._distance(center, self._cluster_point(cluster))

    
    def _cluster_angle(self = None, center = None, cluster = None):
        point = self._cluster_point(cluster)
        dx = float(point[0] - center[0])
        dy = float(point[1] - center[1])
        return math.atan2(dy, dx)

    
    def _cluster_forward_alignment(self = None, center = None, forward_vector = None, cluster = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'cluster', 'GatherCluster', 'return', 'float')):
        pass
    # WARNING: Decompyle incomplete

    
    def _sort_clusters_clockwise(self = None, center = None, clusters = None, clockwise = ('center', 'tuple[int, int]', 'clusters', 'list[GatherCluster]', 'clockwise', 'bool', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _order_clusters_for_logic(self, center, forward_vector, selected_clusters = None, pinned_cluster = None, profile = None, mode = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'selected_clusters', 'list[GatherCluster]', 'pinned_cluster', 'GatherCluster | None', 'profile', 'CalibrationProfile', 'mode', 'str', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _candidate_clusters_for_logic(self, center, forward_vector, clusters, profile = None, mode = None, candidate_limit = None, pinned_cluster = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'mode', 'str', 'candidate_limit', 'int', 'pinned_cluster', 'GatherCluster | None', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    _normalize_vector = (lambda x = None, y = None: norm = math.hypot(x, y)if norm <= 1e-06:
None(None / norm, y / norm))()
    
    def _cluster_cost(self, current_point, current_direction = None, cluster = None, remaining = None, profile = ('current_point', 'tuple[int, int]', 'current_direction', 'tuple[float, float] | None', 'cluster', 'GatherCluster', 'remaining', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'tuple[float, float, float]')):
        cluster_point = self._cluster_point(cluster)
        distance = self._distance(current_point, cluster_point)
        score = self._cluster_route_value(current_point = current_point, current_direction = current_direction, cluster = cluster, remaining = remaining, profile = profile)
        return (-score, -len(cluster.members), distance)

    
    def _cluster_density_mass(self = None, cluster = None, remaining = None, profile = ('cluster', 'GatherCluster', 'remaining', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'float')):
        sigma_px = float(profile.thresholds.get('gather_cluster_density_sigma_px', 28))
        member_mass_scale = float(profile.thresholds.get('gather_cluster_member_mass_scale', 0.55))
        cluster_point = self._cluster_point(cluster)
        mass = 1 + max(0, len(cluster.members) - 1) * member_mass_scale
        sigma_sq = max(1, sigma_px * sigma_px)
        for other in remaining:
            if other is cluster:
                continue
            other_point = self._cluster_point(other)
            distance_sq = float(cluster_point[0] - other_point[0]) ** 2 + float(cluster_point[1] - other_point[1]) ** 2
            gaussian = math.exp(-distance_sq / (2 * sigma_sq))
            mass += (1 + max(0, len(other.members) - 1) * member_mass_scale) * gaussian
            return mass

    
    def _corridor_covered_clusters(self, current_point = None, cluster = None, remaining = None, profile = ('current_point', 'tuple[int, int]', 'cluster', 'GatherCluster', 'remaining', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'list[GatherCluster]')):
        cluster_point = self._cluster_point(cluster)
        dx = float(cluster_point[0] - current_point[0])
        dy = float(cluster_point[1] - current_point[1])
        distance = math.hypot(dx, dy)
        axis = self._normalize_vector(dx, dy)
    # WARNING: Decompyle incomplete

    
    def _cluster_route_value(self, current_point, current_direction = None, cluster = None, remaining = None, profile = (1,), direction_weight_scale = ('current_point', 'tuple[int, int]', 'current_direction', 'tuple[float, float] | None', 'cluster', 'GatherCluster', 'remaining', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'direction_weight_scale', 'float', 'return', 'float')):
        pass
    # WARNING: Decompyle incomplete

    
    def _filter_route_clusters(self, center = None, clusters = None, profile = None, pinned_cluster = ('center', 'tuple[int, int]', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'pinned_cluster', 'GatherCluster | None', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _expand_focus_group(self = None, root_cluster = None, clusters = None, profile = ('root_cluster', 'GatherCluster', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _focus_group_score(self, start_point, start_direction = None, root_cluster = None, group = None, profile = ('start_point', 'tuple[int, int]', 'start_direction', 'tuple[float, float] | None', 'root_cluster', 'GatherCluster', 'group', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'return', 'float')):
        pass
    # WARNING: Decompyle incomplete

    
    def _select_focus_clusters(self, start_point = None, start_direction = None, clusters = None, profile = (None,), pinned_cluster = ('start_point', 'tuple[int, int]', 'start_direction', 'tuple[float, float] | None', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'pinned_cluster', 'GatherCluster | None', 'return', 'list[GatherCluster]')):
        if not clusters:
            return []
    # WARNING: Decompyle incomplete

    
    def _order_cluster_members(self = None, cluster = None, entry_point = None, pinned_node = (None,)):
        pass
    # WARNING: Decompyle incomplete

    
    def _plan_cluster_sequence(self, start_point = None, start_direction = None, clusters = None, profile = (None,), pinned_cluster = ('start_point', 'tuple[int, int]', 'start_direction', 'tuple[float, float] | None', 'clusters', 'list[GatherCluster]', 'profile', 'CalibrationProfile', 'pinned_cluster', 'GatherCluster | None', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _candidate_nodes_for_state(self = None, current_point = None, remaining_nodes = None, profile = ('current_point', 'tuple[int, int]', 'remaining_nodes', 'list[GatherMemoryNode]', 'profile', 'CalibrationProfile', 'return', 'list[GatherMemoryNode]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _build_reward_route(self, start_point = None, start_direction = None, candidates = None, profile = ('start_point', 'tuple[int, int]', 'start_direction', 'tuple[float, float] | None', 'candidates', 'list[GatherMemoryNode]', 'profile', 'CalibrationProfile', 'return', 'list[GatherMemoryNode]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _select_terminal_cluster(self, center = None, clusters = None, pinned_cluster = None, profile = ('center', 'tuple[int, int]', 'clusters', 'list[GatherCluster]', 'pinned_cluster', 'GatherCluster | None', 'profile', 'CalibrationProfile', 'return', 'GatherCluster | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _order_route_clusters(self, center, forward_vector, clusters = None, pinned_cluster = None, terminal_cluster = None, profile = ('center', 'tuple[int, int]', 'forward_vector', 'tuple[float, float] | None', 'clusters', 'list[GatherCluster]', 'pinned_cluster', 'GatherCluster | None', 'terminal_cluster', 'GatherCluster | None', 'profile', 'CalibrationProfile', 'return', 'list[GatherCluster]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _build_route(self = None, center = None, profile = None, forward_vector = (None,)):
        pass
    # WARNING: Decompyle incomplete

    
    def _needs_route_rebuild(self = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def has_route(self = None):
        return bool(self.route_steps)

    
    def has_memory_targets(self = None):
        return (lambda .0: pass# WARNING: Decompyle incomplete
)(self.memory_nodes())

    
    def route_progress(self = None):
        return (min(self.route_index, len(self.route_steps)), len(self.route_steps))

    
    def route_finished(self = None):
        if bool(self.route_steps):
            pass
        return self.route_index >= len(self.route_steps)

    
    def route_debug_points(self = None, profile = None):
        if not self.route_steps:
            return []
        center = None._center(profile)
        route_missing_frames = int(profile.thresholds.get('gather_route_missing_frames', 8))
        points = []
        reference_point = center
    # WARNING: Decompyle incomplete

    
    def route_debug_terminal(self = None, profile = None):
        points = self.route_debug_points(profile)
        if not points:
            return None
        return None[-1]

    
    def route_debug_weights(self = None):
        return self.route_steps()

    _round_point = (lambda x = None, y = None: (int(round(x)), int(round(y))))()
    _blend_point = (lambda current = None, target = None, alpha = staticmethod, max_step = ('current', 'tuple[int, int]', 'target', 'tuple[int, int]', 'alpha', 'float', 'max_step', 'float', 'return', 'tuple[int, int]'): dx = float(target[0] - current[0])dy = float(target[1] - current[1])distance = math.hypot(dx, dy)if distance <= 0.001:
currentstep = None(distance, max_step, max(1, distance * alpha))scale = step / distance(int(round(current[0] + dx * scale)), int(round(current[1] + dy * scale))))()
    
    def _clamp_live_point_outward(self, current_point = None, live_point = None, center = None, outward_tolerance_px = ('current_point', 'tuple[int, int]', 'live_point', 'tuple[int, int]', 'center', 'tuple[int, int] | None', 'outward_tolerance_px', 'float', 'return', 'tuple[int, int]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _route_step_live_point(self, step, route_missing_frames = None, profile = None, reference_point = None, center = (None, None, None, True), commit = ('step', 'GatherRouteStep', 'route_missing_frames', 'int', 'profile', 'CalibrationProfile | None', 'reference_point', 'tuple[int, int] | None', 'center', 'tuple[int, int] | None', 'commit', 'bool', 'return', 'tuple[int, int] | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _resolve_route_target(self = None, profile = None):
        center = self._center(profile)
        min_target_radius = float(profile.thresholds.get('gather_route_min_target_radius_px', max(profile.thresholds.get('gather_collected_memory_radius_px', 22) + 8, profile.thresholds.get('visit_distance_px', 12) + 16)))
        route_missing_frames = int(profile.thresholds.get('gather_route_missing_frames', 8))
        track_distance = max(float(profile.thresholds.get('gather_target_track_move_px', 18)), float(profile.thresholds.get('gather_target_hold_match_distance_px', 36)))
        missing_grace_s = float(profile.timeouts.get('gather_route_step_missing_grace_seconds', 1.2))
        now = time.monotonic()
    # WARNING: Decompyle incomplete

    
    def choose_target(self = None, snapshot = None, profile = None, current_target = (None,)):
        center = self._center(profile)
    # WARNING: Decompyle incomplete

    
    def _local_enemy_density(self = None, point = None, enemies = None, profile = ('point', 'tuple[int, int]', 'enemies', 'list[tuple[int, int]]', 'profile', 'CalibrationProfile', 'return', 'tuple[float, int]')):
        sigma_px = float(profile.thresholds.get('gather_aggro_density_sigma_px', 24))
        near_radius = float(profile.thresholds.get('gather_aggro_nearby_radius_px', 30))
        sigma_sq = max(1, sigma_px * sigma_px)
        density = 0
        near_count = 0
        for enemy in enemies:
            distance = self._distance(point, enemy)
            if distance <= near_radius:
                near_count += 1
            density += math.exp(-(distance * distance) / (2 * sigma_sq))
            return (density, near_count)

    
    def mark_visited_if_reached(self = None, target = None, snapshot = None, profile = ('target', 'tuple[int, int] | None', 'snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'return', 'bool')):
        pass
    # WARNING: Decompyle incomplete

    
    def update_gather(self = None, target = None, snapshot = None, profile = ('target', 'tuple[int, int] | None', 'snapshot', 'VisionSnapshot', 'profile', 'CalibrationProfile', 'return', 'tuple[str, bool]')):
        center = self._center(profile)
    # WARNING: Decompyle incomplete

    
    def is_stuck(self = None, profile = None, heading_error_deg = None, target_distance = (None, None, None), heading_confidence = ('profile', 'CalibrationProfile', 'heading_error_deg', 'float | None', 'target_distance', 'float | None', 'heading_confidence', 'float | None', 'return', 'bool')):
        pass
    # WARNING: Decompyle incomplete

    
    def _abandon_active_target(self = None):
        pass
    # WARNING: Decompyle incomplete

    
    def anti_stuck(self = None, profile = None):
        -1 if self.anti_stuck_attempt % 2 == 0 else 1 = self, self.active_target_stuck_attempts += 1, .active_target_stuck_attempts
        strafe_key = 'A' if direction < 0 else 'D'
        mouse_dx = self.config.anti_stuck_mouse_dx * direction
        self.logger.warning('Anti-stuck triggered: attempt=%s strafe=%s mouse_dx=%s', self.anti_stuck_attempt, strafe_key, mouse_dx)
        self.stop_motion()
        self.input.tap_key('S', hold_s = 0.22)
        self.input.tap_key(strafe_key, hold_s = 0.18)
        self.input.move_mouse_relative(mouse_dx, 0)
        self.input.tap_key('SPACE', hold_s = 0.06)
        self.distance_history.clear()
        self.world_coord_history.clear()
    # WARNING: Decompyle incomplete

    
    def update_pack(self = None, snapshot = None, profile = None):
        self.input.press_key('W')
        stamina_threshold = float(profile.thresholds.get('stamina_shift_threshold', 0.55))
    # WARNING: Decompyle incomplete

    
    def search_for_targets(self = None, snapshot = None, profile = None):
        self.input.press_key('W')
        stamina_threshold = float(profile.thresholds.get('stamina_shift_threshold', 0.55))
    # WARNING: Decompyle incomplete

    
    def target_distance(self = None, target = None, profile = None):
        pass
    # WARNING: Decompyle incomplete

    
    def stop_motion(self = None):
        self.input.release_key('W')
        self.input.release_key('A')
        self.input.release_key('S')
        self.input.release_key('D')
        self.input.release_key('SHIFT')
        self.input.release_key('SPACE')


