# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\bot\\navigation_controller.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

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
@dataclass
class GatherMemoryNode:
    seed_point: tuple[int, int]
    current_point: tuple[int, int]
    first_seen_at: float
    last_seen_at: float
    seen_frames: int = 1
    missing_frames: int = 0
    reached: bool = False
@dataclass
class GatherCluster:
    members: list[GatherMemoryNode]
    centroid: tuple[float, float]
    spread: float
@dataclass
class GatherRouteStep:
    node: GatherMemoryNode
    planned_point: tuple[int, int]
    current_point: tuple[int, int]
    cluster_size: int
    cluster_node_ids: set[int]
    centroid: tuple[float, float]
class NavigationController:
    def __init__(self, input_controller: InputController, config: AppConfig) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.input = input_controller
        self.config = config
        self.visited_targets = []
        self.distance_history = deque(maxlen=30)
        self.world_coord_history = deque(maxlen=60)
        self.active_target = None
        self.active_target_started_at = 0.0
        self.active_target_missing_frames = 0
        self.active_target_last_move_at = 0.0
        self.active_target_stable_frames = 0
        self.active_target_initial_distance = None
        self.active_target_best_distance = None
        self.search_direction = 1
        self.search_step = 0
        self.anti_stuck_attempt = 0
        self.memory_nodes = []
        self.route_steps = []
        self.route_index = 0
        self.last_route_build_at = 0.0
        self.route_step_missing_started_at = 0.0
        self.reach_confirm_frames = 0
        self.active_target_stuck_attempts = 0
        self.last_reached_count = 0
        self._last_gather_steering_log_at = 0.0
    def reset(self) -> None:
        self.visited_targets.clear()
        self.distance_history.clear()
        self.world_coord_history.clear()
        self.active_target = None
        self.active_target_started_at = 0.0
        self.active_target_missing_frames = 0
        self.active_target_last_move_at = 0.0
        self.active_target_stable_frames = 0
        self.active_target_initial_distance = None
        self.active_target_best_distance = None
        self.search_direction = 1
        self.search_step = 0
        self.anti_stuck_attempt = 0
        self.memory_nodes.clear()
        self.route_steps.clear()
        self.route_index = 0
        self.last_route_build_at = 0.0
        self.route_step_missing_started_at = 0.0
        self.reach_confirm_frames = 0
        self.active_target_stuck_attempts = 0
        self.last_reached_count = 0
        self._last_gather_steering_log_at = 0.0
    def _purge_visited(self, ttl_s: float) -> None:
        now = time.monotonic()
        self.visited_targets = [(pt, ts) for pt, ts in self.visited_targets if now - ts <= ttl_s]
    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])
    @staticmethod
    def _signed_angle(forward: tuple[float, float], target_vec: tuple[float, float]) -> float:
        cross = forward[0] * target_vec[1] - forward[1] * target_vec[0]
        dot = forward[0] * target_vec[0] + forward[1] * target_vec[1]
        return math.atan2(cross, dot)
    def _center(self, profile: CalibrationProfile) -> tuple[int, int] | None:
        center_spec = profile.points.get('minimap_center')
        return center_spec.as_pixels(profile.screen_size) if center_spec else None
    def _gather_logic_mode(self, profile: CalibrationProfile) -> str:
        return normalize_gather_logic_mode(profile.settings.get('gather_logic_mode', DEFAULT_GATHER_LOGIC_MODE))
    def _effective_memory_half_extent(self, profile: CalibrationProfile) -> float:
        half_extent = float(profile.thresholds.get('gather_memory_half_extent_px', 0.0))
        if half_extent > 0.0:
            return half_extent
        else:
            minimap_spec = profile.zones.get('minimap_region')
            minimap_rect = minimap_spec.as_pixels(profile.screen_size) if minimap_spec else None
            if minimap_rect is not None:
                _, _, w, h = minimap_rect
                return min(w, h) * 0.48
            else:
                return 150.0
    def _forward_vector(self, snapshot: VisionSnapshot, profile: CalibrationProfile) -> tuple[float, float]:
        confidence_threshold = float(profile.thresholds.get('minimap_heading_confidence_threshold', 0.18))
        if snapshot.minimap_heading_vector is not None and snapshot.minimap_heading_confidence >= confidence_threshold:
            return snapshot.minimap_heading_vector
        else:
            return (0.0, (-1.0))
    def _set_active_target(self, target: tuple[int, int] | None, track_distance: float | None=None) -> None:
        now = time.monotonic()
        if target == self.active_target:
            self.active_target_missing_frames = 0
            if target is not None:
                self.active_target_stable_frames += 1
            return None
        else:
            if track_distance is not None and self.active_target is not None and (target is not None) and (self._distance(self.active_target, target) <= track_distance):
                self.active_target = target
                self.active_target_missing_frames = 0
                self.active_target_stable_frames += 1
                return None
            else:
                if self.active_target is not None and target is not None:
                    self.logger.info('Switching gather target: %s -> %s', self.active_target, target)
                else:
                    if target is not None:
                        self.logger.info('Locking gather target: %s', target)
                    else:
                        if self.active_target is not None:
                            self.logger.info('Clearing gather target: %s', self.active_target)
                self.active_target = target
                self.active_target_started_at = now
                self.active_target_missing_frames = 0
                self.active_target_last_move_at = now if target is not None else 0.0
                self.active_target_stable_frames = 0
                self.active_target_initial_distance = None
                self.active_target_best_distance = None
                self.reach_confirm_frames = 0
                self.active_target_stuck_attempts = 0
                self.distance_history.clear()
                self.world_coord_history.clear()
    def clear_active_target(self) -> None:
        self._set_active_target(None)
        self.distance_history.clear()
        self.world_coord_history.clear()
    def consume_reached_count(self) -> int:
        count = self.last_reached_count
        self.last_reached_count = 0
        return count
    def _track_active_target(self, snapshot: VisionSnapshot, profile: CalibrationProfile) -> tuple[int, int] | None:
        if self.active_target is None:
            return None
        else:
            center = self._center(profile)
            track_distance = float(profile.thresholds.get('gather_target_track_move_px', 18.0))
            hold_match_distance = float(profile.thresholds.get('gather_target_hold_match_distance_px', 36.0))
            active_node = self._find_matching_node_consistent(self.active_target, max(track_distance, hold_match_distance), center, outward_tolerance_px=float(profile.thresholds.get('gather_target_match_outward_tolerance_px', 14.0)), angle_threshold_deg=float(profile.thresholds.get('gather_target_match_angle_threshold_deg', 34.0)))
            if active_node is not None:
                target_shift_ignore_px = float(profile.thresholds.get('gather_stuck_target_shift_ignore_px', 4.0))
                if self._distance(self.active_target, active_node.current_point) >= target_shift_ignore_px:
                    self.active_target_last_move_at = time.monotonic()
                    self.active_target_stable_frames = 0
                    self.distance_history.clear()
                self.active_target_missing_frames = 0
                self._set_active_target(active_node.current_point, track_distance=max(track_distance, hold_match_distance))
                return active_node.current_point
            else:
                self.active_target_missing_frames += 1
                missing_limit = max(1, int(profile.thresholds.get('gather_target_missing_frames', 10.0)))
                if self.active_target_missing_frames < missing_limit:
                    return self.active_target
                else:
                    self._set_active_target(None)
    def _is_recently_visited(self, point: tuple[int, int], reuse_distance: float) -> bool:
        return any((self._distance(point, visited_point) <= reuse_distance for visited_point, _ in self.visited_targets))
    def _remember_collected_enemies(self, snapshot: VisionSnapshot, center: tuple[int, int], profile: CalibrationProfile) -> None:
        collected_radius = float(profile.thresholds.get('gather_collected_memory_radius_px', max(profile.thresholds.get('gather_collect_radius_px', 18.0), profile.thresholds.get('visit_distance_px', 12.0) * 1.8)))
        match_distance = float(profile.thresholds.get('gather_collected_memory_match_distance_px', max(profile.thresholds.get('visited_reuse_distance_px', 12.0), profile.thresholds.get('gather_collect_radius_px', 18.0))))
        raw_candidates = list(getattr(snapshot, 'minimap_enemy_candidates', []) or [])
        if not raw_candidates:
            raw_candidates = [MinimapEnemyCandidate(point=enemy, radius=self._distance(center, enemy), angle_deg=(math.degrees(math.atan2(enemy[0] - center[0], center[1] - enemy[1])) + 360.0) % 360.0, stack_count=1, template_score=0.0, source='legacy') for enemy in snapshot.minimap_enemies]
        now = time.monotonic()
        protected_points = []
        if self.active_target is not None:
            protected_points.append(self.active_target)
        if self.route_index < len(self.route_steps):
            current_step = self.route_steps[self.route_index]
            protected_points.extend((point for point in [current_step.current_point, current_step.planned_point, current_step.node.current_point] if point is not None))
        for candidate in raw_candidates:
            if candidate.radius > collected_radius:
                continue
            else:
                if any((self._distance(candidate.point, point) <= match_distance for point in protected_points)):
                    continue
                else:
                    if not self._is_recently_visited(candidate.point, match_distance):
                        self.visited_targets.append((candidate.point, now))
    def _find_matching_node(self, point: tuple[int, int], match_distance: float) -> GatherMemoryNode | None:
        best_node = None
        best_distance = float('inf')
        for node in self.memory_nodes:
            if node.reached:
                continue
            else:
                distance = self._distance(node.current_point, point)
                if distance <= match_distance and distance < best_distance:
                        best_node = node
                        best_distance = distance
        return best_node
    def _observed_enemy_candidates(self, snapshot: VisionSnapshot, center: tuple[int, int], half_extent: float, reuse_distance: float) -> list[MinimapEnemyCandidate]:
        raw_candidates = list(getattr(snapshot, 'minimap_enemy_candidates', []) or [])
        if not raw_candidates:
            raw_candidates = [MinimapEnemyCandidate(point=enemy, radius=self._distance(center, enemy), angle_deg=(math.degrees(math.atan2(enemy[0] - center[0], center[1] - enemy[1])) + 360.0) % 360.0, stack_count=1, template_score=0.0, source='legacy') for enemy in snapshot.minimap_enemies]
        candidates = [candidate for candidate in raw_candidates if not (abs(candidate.point[0] - center[0]) <= half_extent and abs(candidate.point[1] - center[1]) <= half_extent and self._is_recently_visited(candidate.point, reuse_distance))]
        candidates.sort(key=lambda candidate: (candidate.radius, -candidate.template_score, candidate.point[1], candidate.point[0]))
        return candidates
    @staticmethod
    def _angle_delta_deg(a_deg: float, b_deg: float) -> float:
        return abs((a_deg - b_deg + 180.0) % 360.0 - 180.0)
    def _score_candidate_for_anchor(self, anchor: tuple[int, int], candidate: MinimapEnemyCandidate, center: tuple[int, int] | None, *, outward_tolerance_px: float, angle_threshold_deg: float) -> tuple[float, float, float, float] | None:
        distance = self._distance(anchor, candidate.point)
        if center is None:
            return (distance, 0.0, 0.0, -candidate.template_score)
        else:
            anchor_radius = self._distance(center, anchor)
            anchor_angle = (math.degrees(math.atan2(anchor[0] - center[0], center[1] - anchor[1])) + 360.0) % 360.0
            radius_delta = candidate.radius - anchor_radius
            if radius_delta > outward_tolerance_px:
                return None
            else:
                angle_delta_deg = self._angle_delta_deg(anchor_angle, candidate.angle_deg)
                if angle_delta_deg > angle_threshold_deg:
                    return None
                else:
                    outward_penalty = max(0.0, radius_delta)
                    return (outward_penalty, angle_delta_deg, distance, -candidate.template_score)
    def _find_matching_node_consistent(self, point: tuple[int, int], match_distance: float, center: tuple[int, int] | None, *, outward_tolerance_px: float, angle_threshold_deg: float) -> GatherMemoryNode | None:
        best_node = None
        best_score = None
        point_radius = self._distance(center, point) if center is not None else 0.0
        point_angle = (math.degrees(math.atan2(point[0] - center[0], center[1] - point[1])) + 360.0) % 360.0 if center is not None else 0.0
        for node in self.memory_nodes:
            if node.reached:
                continue
            else:
                distance = self._distance(node.current_point, point)
                if distance > match_distance:
                    continue
                else:
                    outward_penalty = 0.0
                    angle_penalty = 0.0
                    if center is not None:
                        node_radius = self._distance(center, node.current_point)
                        radius_delta = node_radius - point_radius
                        if radius_delta > outward_tolerance_px:
                            continue
                        else:
                            node_angle = (math.degrees(math.atan2(node.current_point[0] - center[0], center[1] - node.current_point[1])) + 360.0) % 360.0
                            angle_penalty = self._angle_delta_deg(point_angle, node_angle)
                            if angle_penalty > angle_threshold_deg:
                                continue
                            else:
                                outward_penalty = max(0.0, radius_delta)
                    score = (outward_penalty, angle_penalty, distance)
                    if best_score is None or score < best_score:
                        best_node = node
                        best_score = score
        return best_node
    def _update_memory(self, snapshot: VisionSnapshot, profile: CalibrationProfile, center: tuple[int, int]) -> None:
        now = time.monotonic()
        ttl_s = profile.timeouts.get('visited_ttl_seconds', 12.0)
        self._purge_visited(ttl_s)
        self._remember_collected_enemies(snapshot, center, profile)
        half_extent = self._effective_memory_half_extent(profile)
        merge_distance = float(profile.thresholds.get('gather_memory_merge_distance_px', 10.0))
        missing_frames_limit = int(profile.thresholds.get('gather_memory_missing_frames', 8))
        reuse_distance = float(profile.thresholds.get('visited_reuse_distance_px', 12.0))
        observed_candidates = self._observed_enemy_candidates(snapshot, center, half_extent, reuse_distance)
        matched_node_ids = set()
        remaining_observed = list(observed_candidates)
        locked_match_distance = max(merge_distance, float(profile.thresholds.get('gather_locked_target_match_distance_px', 18.0)))
        route_locked_match_distance = max(locked_match_distance, float(profile.thresholds.get('gather_route_locked_match_distance_px', locked_match_distance * 2.5)))
        locked_outward_tolerance_px = float(profile.thresholds.get('gather_target_match_outward_tolerance_px', 14.0))
        locked_angle_threshold_deg = float(profile.thresholds.get('gather_target_match_angle_threshold_deg', 34.0))
        route_locked_angle_threshold_deg = float(profile.thresholds.get('gather_route_target_match_angle_threshold_deg', 42.0))
        locked_nodes = []
        current_route_node = None
        if self.route_steps and self.route_index < len(self.route_steps):
                current_route_node = self.route_steps[self.route_index].node
                locked_nodes.append(current_route_node)
        if self.active_target is not None:
            active_node = self._find_matching_node_consistent(self.active_target, max(merge_distance, 18.0), center, outward_tolerance_px=locked_outward_tolerance_px, angle_threshold_deg=locked_angle_threshold_deg)
            if active_node is not None and active_node not in locked_nodes:
                    locked_nodes.append(active_node)
        for node in locked_nodes:
            if node.reached:
                continue
            else:
                node_match_distance = locked_match_distance
                node_angle_threshold_deg = locked_angle_threshold_deg
                if current_route_node is not None and node is current_route_node:
                        node_match_distance = route_locked_match_distance
                        node_angle_threshold_deg = route_locked_angle_threshold_deg
                best_index = None
                best_score = None
                for index, candidate in enumerate(remaining_observed):
                    distance = self._distance(node.current_point, candidate.point)
                    if distance > node_match_distance:
                        continue
                    else:
                        score = self._score_candidate_for_anchor(node.current_point, candidate, center, outward_tolerance_px=locked_outward_tolerance_px, angle_threshold_deg=node_angle_threshold_deg)
                        if score is None:
                            continue
                        else:
                            if best_score is None or score < best_score:
                                best_index = index
                                best_score = score
                if best_index is None:
                    continue
                else:
                    candidate = remaining_observed.pop(best_index)
                    node.current_point = candidate.point
                    node.last_seen_at = now
                    node.seen_frames += 1
                    node.missing_frames = 0
                    matched_node_ids.add(id(node))
        for candidate in remaining_observed:
            enemy = candidate.point
            best_node = None
            best_distance = float('inf')
            for node in self.memory_nodes:
                if node.reached or id(node) in matched_node_ids:
                    continue
                else:
                    distance = self._distance(node.current_point, enemy)
                    if distance <= merge_distance and distance < best_distance:
                            best_node = node
                            best_distance = distance
            if best_node is None:
                self.memory_nodes.append(GatherMemoryNode(seed_point=enemy, current_point=enemy, first_seen_at=now, last_seen_at=now))
            else:
                best_node.current_point = enemy
                best_node.last_seen_at = now
                best_node.seen_frames += 1
                best_node.missing_frames = 0
                matched_node_ids.add(id(best_node))
        for node in self.memory_nodes:
            if id(node) not in matched_node_ids and node.last_seen_at < now:
                    node.missing_frames += 1
        kept_nodes = []
        for node in self.memory_nodes:
            if node.reached:
                continue
            else:
                if self._is_recently_visited(node.current_point, reuse_distance):
                    continue
                else:
                    if node.missing_frames > missing_frames_limit:
                        continue
                    else:
                        kept_nodes.append(node)
        self.memory_nodes = kept_nodes
        memory_ids = {id(node) for node in self.memory_nodes}
        self.route_steps = [step for step in self.route_steps if step.cluster_node_ids & memory_ids and (not step.node.reached)]
        self.route_index = min(self.route_index, len(self.route_steps))
    def _route_cost(self, current_point: tuple[int, int], node: GatherMemoryNode, remaining: list[GatherMemoryNode], profile: CalibrationProfile) -> tuple[float, int, float]:
        density_radius = float(profile.thresholds.get('gather_route_neighbor_radius_px', 18.0))
        density_bonus = float(profile.thresholds.get('gather_route_density_bonus_px', 12.0))
        distance = self._distance(current_point, node.current_point)
        density = sum((1 for other in remaining if other is not node and self._distance(node.current_point, other.current_point) <= density_radius))
        effective_cost = max(0.0, distance - density * density_bonus + node.missing_frames * 6.0)
        return (effective_cost, -density, distance)
    def _build_clusters(self, candidates: list[GatherMemoryNode], profile: CalibrationProfile) -> list[GatherCluster]:
        cluster_distance = float(profile.thresholds.get('gather_cluster_distance_px', 14.0))
        pending = list(candidates)
        clusters = []
        while pending:
            seed = pending.pop(0)
            cluster_members = [seed]
            queue = [seed]
            while queue:
                node = queue.pop(0)
                attached = []
                for other in pending:
                    if self._distance(node.current_point, other.current_point) <= cluster_distance:
                        attached.append(other)
                if not attached:
                    continue
                for member in attached:
                    pending.remove(member)
                    cluster_members.append(member)
                    queue.append(member)
            centroid = (sum((member.current_point[0] for member in cluster_members)) / len(cluster_members), sum((member.current_point[1] for member in cluster_members)) / len(cluster_members))
            spread = sum((self._distance(member.current_point, (int(round(centroid[0])), int(round(centroid[1])))) for member in cluster_members)) / max(1, len(cluster_members))
            clusters.append(GatherCluster(members=cluster_members, centroid=centroid, spread=spread))
        return clusters
    @staticmethod
    def _cluster_point(cluster: GatherCluster) -> tuple[int, int]:
        return (int(round(cluster.centroid[0])), int(round(cluster.centroid[1])))
    def _cluster_representative(self, cluster: GatherCluster, entry_point: tuple[int, int], pinned_node: GatherMemoryNode | None=None) -> GatherMemoryNode:
        if pinned_node is not None and pinned_node in cluster.members:
            return pinned_node
        else:
            centroid = self._cluster_point(cluster)
            return min(cluster.members, key=lambda member: (self._distance(member.current_point, centroid), self._distance(member.current_point, entry_point)))
    def _cluster_score(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, cluster: GatherCluster, clusters: list[GatherCluster], profile: CalibrationProfile) -> float:
        return self._cluster_route_value(current_point=center, current_direction=forward_vector, cluster=cluster, remaining=clusters, profile=profile)
    def _rank_clusters(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, clusters: list[GatherCluster], profile: CalibrationProfile) -> list[GatherCluster]:
        return sorted(clusters, key=lambda cluster: (-self._cluster_score(center, forward_vector, cluster, clusters, profile), self._distance(center, self._cluster_point(cluster))))
    def _cluster_radius(self, center: tuple[int, int], cluster: GatherCluster) -> float:
        return self._distance(center, self._cluster_point(cluster))
    def _cluster_angle(self, center: tuple[int, int], cluster: GatherCluster) -> float:
        point = self._cluster_point(cluster)
        dx = float(point[0] - center[0])
        dy = float(point[1] - center[1])
        return math.atan2(dy, dx)
    def _cluster_forward_alignment(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, cluster: GatherCluster) -> float:
        if forward_vector is None:
            return 0.0
        else:
            point = self._cluster_point(cluster)
            next_direction = self._normalize_vector(point[0] - center[0], point[1] - center[1])
            if next_direction is None:
                return 0.0
            else:
                return forward_vector[0] * next_direction[0] + forward_vector[1] * next_direction[1]
    def _sort_clusters_clockwise(self, center: tuple[int, int], clusters: list[GatherCluster], clockwise: bool) -> list[GatherCluster]:
        return sorted(clusters, key=lambda cluster: (-self._cluster_angle(center, cluster) if clockwise else self._cluster_angle(center, cluster), self._cluster_radius(center, cluster), -len(cluster.members)))
    def _order_clusters_for_logic(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, selected_clusters: list[GatherCluster], pinned_cluster: GatherCluster | None, profile: CalibrationProfile, mode: str) -> list[GatherCluster]:
        if not selected_clusters:
            return []
        else:
            if mode == 'nearest_target':
                ordered = sorted(selected_clusters, key=lambda cluster: (self._cluster_radius(center, cluster), -len(cluster.members), abs(self._cluster_angle(center, cluster))))
                return ordered[:1]
            else:
                if mode == 'densest_cluster':
                    ordered = sorted(selected_clusters, key=lambda cluster: (-len(cluster.members), -self._cluster_density_mass(cluster, selected_clusters, profile), self._cluster_radius(center, cluster)))
                    return ordered
                else:
                    if mode == 'forward_sweep':
                        ordered = sorted(selected_clusters, key=lambda cluster: (-self._cluster_forward_alignment(center, forward_vector, cluster), self._cluster_radius(center, cluster), -len(cluster.members)))
                        return ordered
                    else:
                        if mode == 'clockwise_sweep':
                            return self._sort_clusters_clockwise(center, selected_clusters, clockwise=True)
                        else:
                            if mode == 'counter_clockwise_sweep':
                                return self._sort_clusters_clockwise(center, selected_clusters, clockwise=False)
                            else:
                                if mode == 'inward_pull':
                                    ordered = sorted(selected_clusters, key=lambda cluster: (self._cluster_radius(center, cluster), -len(cluster.members), -self._cluster_forward_alignment(center, forward_vector, cluster)))
                                    return ordered
                                else:
                                    if mode == 'stable_lock':
                                        if pinned_cluster is not None:
                                            return [pinned_cluster]
                                        else:
                                            ordered = sorted(selected_clusters, key=lambda cluster: (self._cluster_radius(center, cluster), abs(self._cluster_angle(center, cluster)), -len(cluster.members)))
                                            return ordered[:1]
                                    else:
                                        if mode == 'pack_builder':
                                            focus_clusters = self._select_focus_clusters(start_point=center, start_direction=forward_vector, clusters=selected_clusters, profile=profile, pinned_cluster=pinned_cluster)
                                            planned = self._plan_cluster_sequence(start_point=center, start_direction=forward_vector, clusters=focus_clusters, profile=profile, pinned_cluster=pinned_cluster)
                                            return planned or focus_clusters
                                        else:
                                            if mode == 'terminal_push':
                                                ordered = sorted(selected_clusters, key=lambda cluster: (-self._cluster_radius(center, cluster), -len(cluster.members), -self._cluster_forward_alignment(center, forward_vector, cluster)))
                                                if pinned_cluster is not None and pinned_cluster in ordered:
                                                        ordered.remove(pinned_cluster)
                                                        ordered.insert(0, pinned_cluster)
                                                return ordered
                                            else:
                                                planned = self._plan_cluster_sequence(start_point=center, start_direction=forward_vector, clusters=selected_clusters, profile=profile, pinned_cluster=pinned_cluster)
                                                if planned:
                                                    return planned
                                                else:
                                                    terminal_cluster = self._select_terminal_cluster(center, selected_clusters, pinned_cluster, profile)
                                                    return self._order_route_clusters(center=center, forward_vector=forward_vector, clusters=selected_clusters, pinned_cluster=pinned_cluster, terminal_cluster=terminal_cluster, profile=profile)
    def _candidate_clusters_for_logic(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, clusters: list[GatherCluster], profile: CalibrationProfile, mode: str, candidate_limit: int, pinned_cluster: GatherCluster | None) -> list[GatherCluster]:
        if not clusters:
            return []
        else:
            if mode in {'terminal_push', 'inward_pull', 'clockwise_sweep', 'forward_sweep', 'counter_clockwise_sweep'}:
                ordered = self._order_clusters_for_logic(center=center, forward_vector=forward_vector, selected_clusters=list(clusters), pinned_cluster=pinned_cluster, profile=profile, mode=mode)
                return ordered[:max(candidate_limit, min(len(ordered), 6))]
            else:
                if mode == 'densest_cluster':
                    ordered = sorted(clusters, key=lambda cluster: (-len(cluster.members), -self._cluster_density_mass(cluster, clusters, profile), self._cluster_radius(center, cluster)))
                    return ordered[:max(candidate_limit, 5)]
                else:
                    if mode in {'nearest_target', 'stable_lock'}:
                        ordered = sorted(clusters, key=lambda cluster: (self._cluster_radius(center, cluster), -len(cluster.members)))
                        return ordered[:max(candidate_limit, 4)]
                    else:
                        ranked_clusters = self._rank_clusters(center, None, clusters, profile)
                        return ranked_clusters[:candidate_limit]
    @staticmethod
    def _normalize_vector(x: float, y: float) -> tuple[float, float] | None:
        norm = math.hypot(x, y)
        if norm <= 1e-06:
            return None
        else:
            return (x / norm, y / norm)
    def _cluster_cost(self, current_point: tuple[int, int], current_direction: tuple[float, float] | None, cluster: GatherCluster, remaining: list[GatherCluster], profile: CalibrationProfile) -> tuple[float, float, float]:
        cluster_point = self._cluster_point(cluster)
        distance = self._distance(current_point, cluster_point)
        score = self._cluster_route_value(current_point=current_point, current_direction=current_direction, cluster=cluster, remaining=remaining, profile=profile)
        return (-score, -len(cluster.members), distance)
    def _cluster_density_mass(self, cluster: GatherCluster, remaining: list[GatherCluster], profile: CalibrationProfile) -> float:
        sigma_px = float(profile.thresholds.get('gather_cluster_density_sigma_px', 28.0))
        member_mass_scale = float(profile.thresholds.get('gather_cluster_member_mass_scale', 0.55))
        cluster_point = self._cluster_point(cluster)
        mass = 1.0 + max(0, len(cluster.members) - 1) * member_mass_scale
        sigma_sq = max(1.0, sigma_px * sigma_px)
        for other in remaining:
            if other is cluster:
                continue
            else:
                other_point = self._cluster_point(other)
                distance_sq = float(cluster_point[0] - other_point[0]) ** 2 + float(cluster_point[1] - other_point[1]) ** 2
                gaussian = math.exp(-distance_sq / (2.0 * sigma_sq))
                mass += (1.0 + max(0, len(other.members) - 1) * member_mass_scale) * gaussian
        return mass
    def _corridor_covered_clusters(self, current_point: tuple[int, int], cluster: GatherCluster, remaining: list[GatherCluster], profile: CalibrationProfile) -> list[GatherCluster]:
        cluster_point = self._cluster_point(cluster)
        dx = float(cluster_point[0] - current_point[0])
        dy = float(cluster_point[1] - current_point[1])
        distance = math.hypot(dx, dy)
        axis = self._normalize_vector(dx, dy)
        if axis is None:
            return [cluster]
        else:
            corridor_half_width = float(profile.thresholds.get('gather_cluster_sweep_half_width_px', profile.thresholds.get('gather_cluster_corridor_half_width_px', 34.0)))
            sweep_forward_padding = float(profile.thresholds.get('gather_cluster_sweep_forward_padding_px', 18.0))
            sweep_backtrack = float(profile.thresholds.get('gather_cluster_sweep_backtrack_px', profile.thresholds.get('gather_cluster_corridor_backtrack_px', 16.0)))
            lateral_axis = (-axis[1], axis[0])
            covered = [cluster]
            for other in remaining:
                if other is cluster:
                    continue
                else:
                    other_point = self._cluster_point(other)
                    rel_x = float(other_point[0] - current_point[0])
                    rel_y = float(other_point[1] - current_point[1])
                    projection = rel_x * axis[0] + rel_y * axis[1]
                    if projection < -sweep_backtrack or projection > distance + sweep_forward_padding:
                        continue
                    else:
                        lateral = abs(rel_x * lateral_axis[0] + rel_y * lateral_axis[1])
                        allowance = corridor_half_width + max(0.0, other.spread * 0.35)
                        if lateral > allowance:
                            continue
                        else:
                            covered.append(other)
            return covered
    def _cluster_route_value(self, current_point: tuple[int, int], current_direction: tuple[float, float] | None, cluster: GatherCluster, remaining: list[GatherCluster], profile: CalibrationProfile, direction_weight_scale: float=1.0) -> float:
        # irreducible cflow, using cdg fallback
        # ***<module>.NavigationController._cluster_route_value: Failure: Different control flow
        cluster_point = self._cluster_point(cluster)
        dx = float(cluster_point[0] - current_point[0])
        dy = float(cluster_point[1] - current_point[1])
        distance = math.hypot(dx, dy)
        next_direction = self._normalize_vector(dx, dy)
        density_reward = float(profile.thresholds.get('gather_cluster_density_reward', 22.0))
        compact_radius = float(profile.thresholds.get('gather_cluster_compact_radius_px', 22.0))
        compact_bonus = float(profile.thresholds.get('gather_cluster_compact_bonus', 1.6))
        strong_pack_size = max(2, int(profile.thresholds.get('gather_cluster_strong_pack_size', 3.0)))
        strong_pack_bonus = float(profile.thresholds.get('gather_cluster_strong_pack_bonus', 45.0))
        corridor_reward = float(profile.thresholds.get('gather_cluster_corridor_member_reward', 14.0))
        distance_penalty = float(profile.thresholds.get('gather_cluster_distance_penalty', 1.15))
        turn_penalty = float(profile.thresholds.get('gather_cluster_turn_penalty_deg', 0.32))
        alignment_bonus = float(profile.thresholds.get('gather_cluster_alignment_bonus', 18.0))
        forward_bonus = float(profile.thresholds.get('gather_cluster_forward_bonus_score', 8.0))
        preferred_min_distance = float(profile.thresholds.get('gather_cluster_preferred_min_distance_px', 26.0))
        preferred_max_distance = float(profile.thresholds.get('gather_cluster_preferred_max_distance_px', 96.0))
        preferred_ring_bonus = float(profile.thresholds.get('gather_cluster_preferred_ring_bonus', 18.0))
        far_distance_start = float(profile.thresholds.get('gather_cluster_far_distance_start_px', 108.0))
        far_distance_penalty = float(profile.thresholds.get('gather_cluster_far_distance_penalty', 2.8))
        close_distance_penalty = float(profile.thresholds.get('gather_cluster_close_distance_penalty', 0.45))
        density_mass = self._cluster_density_mass(cluster, remaining, profile)
        heading_error_deg = 0.0
        direction_alignment = 0.0
        axis = next_direction
        if current_direction is not None and next_direction is not None:
                heading_error_deg = abs(math.degrees(self._signed_angle(current_direction, (dx, dy))))
                direction_alignment = current_direction[0] * next_direction[0] + current_direction[1] * next_direction[1]
        corridor_members = 0
        if axis is not None:
            corridor_clusters = self._corridor_covered_clusters(current_point, cluster, remaining, profile)
            corridor_members = sum((len(other.members) for other in corridor_clusters if other is not cluster))
        score = density_mass * density_reward
        score += max(0.0, compact_radius - cluster.spread) * compact_bonus
        if len(cluster.members) >= strong_pack_size:
            score += strong_pack_bonus
        score += corridor_members * corridor_reward
        score -= distance * distance_penalty
        if preferred_min_distance <= distance <= preferred_max_distance:
                score += preferred_ring_bonus
                if distance > far_distance_start:
                    score -= (distance - far_distance_start) * far_distance_penalty
                else:
                    if distance < preferred_min_distance:
                        score -= (preferred_min_distance - distance) * close_distance_penalty
        score -= heading_error_deg * turn_penalty * direction_weight_scale
        score += max(0.0, direction_alignment) * alignment_bonus * direction_weight_scale
        if heading_error_deg <= 28.0:
            score += forward_bonus * direction_weight_scale
        return score
    def _filter_route_clusters(self, center: tuple[int, int], clusters: list[GatherCluster], profile: CalibrationProfile, pinned_cluster: GatherCluster | None) -> list[GatherCluster]:
        if not clusters:
            return []
        else:
            preferred_max_distance = float(profile.thresholds.get('gather_cluster_preferred_max_distance_px', 96.0))
            isolated_max_distance = float(profile.thresholds.get('gather_cluster_isolated_max_distance_px', 118.0))
            min_pack_size = max(1, int(profile.thresholds.get('gather_cluster_min_pack_chase_size', 2.0)))
            min_pack_support = max(0, int(profile.thresholds.get('gather_cluster_min_pack_support', 1.0)))
            strong_pack_size = max(2, int(profile.thresholds.get('gather_cluster_strong_pack_size', 3.0)))
            strong_pack_max_distance = float(profile.thresholds.get('gather_cluster_strong_pack_max_distance_px', 170.0))
            neighbor_radius = float(profile.thresholds.get('gather_cluster_neighbor_radius_px', 34.0))
            local_exists = any((self._distance(center, self._cluster_point(cluster)) <= preferred_max_distance for cluster in clusters))
            filtered = []
            for cluster in clusters:
                if cluster is pinned_cluster:
                    filtered.append(cluster)
                    continue
                else:
                    cluster_point = self._cluster_point(cluster)
                    distance = self._distance(center, cluster_point)
                    nearby_support = sum((len(other.members) for other in clusters if other is not cluster and self._distance(self._cluster_point(other), cluster_point) <= neighbor_radius))
                    if distance <= preferred_max_distance:
                        filtered.append(cluster)
                    else:
                        if len(cluster.members) >= strong_pack_size and distance <= strong_pack_max_distance:
                            filtered.append(cluster)
                        else:
                            if not local_exists:
                                if distance <= isolated_max_distance:
                                    filtered.append(cluster)
                            else:
                                if distance <= isolated_max_distance and (len(cluster.members) >= min_pack_size or nearby_support >= min_pack_support):
                                        filtered.append(cluster)
            if filtered:
                return filtered
            else:
                if pinned_cluster is not None:
                    return [pinned_cluster]
                else:
                    return []
    def _expand_focus_group(self, root_cluster: GatherCluster, clusters: list[GatherCluster], profile: CalibrationProfile) -> list[GatherCluster]:
        neighbor_radius = float(profile.thresholds.get('gather_cluster_neighbor_radius_px', 34.0))
        max_clusters = max(1, int(profile.thresholds.get('gather_focus_group_max_clusters', 3.0)))
        queue = [root_cluster]
        component = [root_cluster]
        visited_ids = {id(root_cluster)}
        while queue:
            cluster = queue.pop(0)
            for other in clusters:
                if id(other) in visited_ids:
                    continue
                else:
                    if math.hypot(cluster.centroid[0] - other.centroid[0], cluster.centroid[1] - other.centroid[1]) > neighbor_radius:
                        continue
                    else:
                        visited_ids.add(id(other))
                        component.append(other)
                        queue.append(other)
        component.sort(key=lambda cluster: (self._distance(self._cluster_point(root_cluster), self._cluster_point(cluster)), -len(cluster.members)))
        return component[:max_clusters]
    def _focus_group_score(self, start_point: tuple[int, int], start_direction: tuple[float, float] | None, root_cluster: GatherCluster, group: list[GatherCluster], profile: CalibrationProfile) -> float:
        member_reward = float(profile.thresholds.get('gather_focus_group_member_reward', 18.0))
        cluster_reward = float(profile.thresholds.get('gather_focus_group_cluster_reward', 10.0))
        distance_penalty = float(profile.thresholds.get('gather_focus_group_distance_penalty', 1.15))
        excursion_penalty = float(profile.thresholds.get('gather_focus_group_excursion_penalty', 0.85))
        isolation_penalty = float(profile.thresholds.get('gather_focus_group_isolation_penalty', 12.0))
        forward_bonus = float(profile.thresholds.get('gather_focus_group_forward_bonus', 6.0))
        turn_penalty = float(profile.thresholds.get('gather_focus_group_turn_penalty', 8.0))
        root_point = self._cluster_point(root_cluster)
        root_distance = self._distance(start_point, root_point)
        farthest_distance = max((self._distance(start_point, self._cluster_point(cluster)) for cluster in group))
        member_count = sum((len(cluster.members) for cluster in group))
        support_count = max(0, len(group) - 1)
        direction_alignment = 0.0
        if start_direction is not None:
            next_direction = self._normalize_vector(root_cluster.centroid[0] - start_point[0], root_cluster.centroid[1] - start_point[1])
            if next_direction is not None:
                direction_alignment = start_direction[0] * next_direction[0] + start_direction[1] * next_direction[1]
        score = member_count * member_reward + support_count * cluster_reward
        score -= root_distance * distance_penalty
        score -= farthest_distance * excursion_penalty
        score += max(0.0, direction_alignment) * forward_bonus
        score -= max(0.0, -direction_alignment) * turn_penalty
        if member_count <= 1:
            score -= isolation_penalty
        return score
    def _select_focus_clusters(self, start_point: tuple[int, int], start_direction: tuple[float, float] | None, clusters: list[GatherCluster], profile: CalibrationProfile, pinned_cluster: GatherCluster | None=None) -> list[GatherCluster]:
        if not clusters:
            return []
        else:
            if pinned_cluster is not None:
                return self._expand_focus_group(pinned_cluster, clusters, profile)
            else:
                best_group = []
                best_score = float('-inf')
                for root_cluster in clusters:
                    group = self._expand_focus_group(root_cluster, clusters, profile)
                    score = self._focus_group_score(start_point, start_direction, root_cluster, group, profile)
                    if score > best_score:
                        best_group = group
                        best_score = score
                return best_group if best_group else [clusters[0]]
    def _order_cluster_members(self, cluster: GatherCluster, entry_point: tuple[int, int], pinned_node: GatherMemoryNode | None=None) -> list[GatherMemoryNode]:
        if len(cluster.members) <= 1:
            return list(cluster.members)
        else:
            travel_direction = self._normalize_vector(cluster.centroid[0] - entry_point[0], cluster.centroid[1] - entry_point[1]) or (0.0, (-1.0))
            lateral_direction = (-travel_direction[1], travel_direction[0])
            remaining = [member for member in cluster.members if member is not pinned_node]
            ordered = sorted(remaining, key=lambda member: ((member.current_point[0] - entry_point[0]) * travel_direction[0] + (member.current_point[1] - entry_point[1]) * travel_direction[1], abs((member.current_point[0] - entry_point[0]) * lateral_direction[0] + (member.current_point[1] - entry_point[1]) * lateral_direction[1])))
            if pinned_node is not None:
                return [pinned_node] + ordered
            else:
                return ordered
    def _plan_cluster_sequence(self, start_point: tuple[int, int], start_direction: tuple[float, float] | None, clusters: list[GatherCluster], profile: CalibrationProfile, pinned_cluster: GatherCluster | None=None) -> list[GatherCluster]:
        if not clusters:
            return []
        else:
            max_steps = max(1, int(profile.thresholds.get('gather_route_max_clusters', 4.0)))
            beam_width = max(3, int(profile.thresholds.get('gather_route_plan_beam_width', 20.0)))
            return_penalty = float(profile.thresholds.get('gather_route_return_penalty', 1.4))
            excursion_penalty = float(profile.thresholds.get('gather_route_excursion_penalty', 0.42))
            length_bonus = float(profile.thresholds.get('gather_route_length_bonus', 6.0))
            start_turn_scale = float(profile.thresholds.get('gather_route_start_turn_scale', 0.35))
            preferred_max_distance = float(profile.thresholds.get('gather_cluster_preferred_max_distance_px', 96.0))
            def state_value(total_score: float, current_point: tuple[int, int], path: list[GatherCluster], max_excursion: float) -> float:
                return_distance = self._distance(start_point, current_point)
                excursion_overflow = max(0.0, max_excursion - preferred_max_distance)
                return total_score + len(path) * length_bonus - return_distance * return_penalty - excursion_overflow * excursion_penalty
            remaining_clusters = list(clusters)
            initial_score = 0.0
            initial_point = start_point
            initial_direction = start_direction
            initial_path = []
            initial_max_excursion = 0.0
            if pinned_cluster is not None and pinned_cluster in remaining_clusters:
                    pinned_value = self._cluster_route_value(current_point=start_point, current_direction=start_direction, cluster=pinned_cluster, remaining=remaining_clusters, profile=profile, direction_weight_scale=start_turn_scale)
                    pinned_point = self._cluster_point(pinned_cluster)
                    initial_score = pinned_value
                    initial_point = pinned_point
                    initial_direction = self._normalize_vector(pinned_point[0] - start_point[0], pinned_point[1] - start_point[1]) or start_direction
                    initial_path = [pinned_cluster]
                    initial_max_excursion = self._distance(start_point, pinned_point)
                    remaining_clusters.remove(pinned_cluster)
            best_path = list(initial_path)
            best_value = state_value(initial_score, initial_point, initial_path, initial_max_excursion)
            states = [(initial_score, initial_point, initial_direction, initial_path, remaining_clusters, initial_max_excursion)]
            for _ in range(len(initial_path), max_steps):
                next_states = []
                for total_score, current_point, current_direction, path, remaining, max_excursion in states:
                    current_value = state_value(total_score, current_point, path, max_excursion)
                    if current_value > best_value:
                        best_value = current_value
                        best_path = list(path)
                    if not remaining:
                        continue
                    else:
                        direction_scale = start_turn_scale if not path else 1.0
                        for cluster in remaining:
                            covered_clusters = self._corridor_covered_clusters(current_point, cluster, remaining, profile)
                            step_value = self._cluster_route_value(current_point=current_point, current_direction=current_direction, cluster=cluster, remaining=remaining, profile=profile, direction_weight_scale=direction_scale)
                            next_point = self._cluster_point(cluster)
                            next_direction = self._normalize_vector(next_point[0] - current_point[0], next_point[1] - current_point[1]) or current_direction
                            next_path = path + [cluster]
                            next_remaining = [other for other in remaining if other not in covered_clusters]
                            next_max_excursion = max(max_excursion, self._distance(start_point, next_point))
                            next_states.append((total_score + step_value, next_point, next_direction, next_path, next_remaining, next_max_excursion))
                if not next_states:
                    break
                else:
                    next_states.sort(key=lambda state: (-state_value(state[0], state[1], state[3], state[5]), -sum((len(cluster.members) for cluster in state[3])), self._distance(start_point, state[1])))
                    states = next_states[:beam_width]
            for total_score, current_point, _current_direction, path, _remaining, max_excursion in states:
                current_value = state_value(total_score, current_point, path, max_excursion)
                if current_value > best_value:
                    best_value = current_value
                    best_path = list(path)
            return best_path
    def _candidate_nodes_for_state(self, current_point: tuple[int, int], remaining_nodes: list[GatherMemoryNode], profile: CalibrationProfile) -> list[GatherMemoryNode]:
        candidate_pool = max(3, int(profile.thresholds.get('gather_candidate_pool_size', 6.0)))
        collect_radius = float(profile.thresholds.get('gather_collect_radius_px', 18.0))
        density_bonus = float(profile.thresholds.get('gather_candidate_density_bonus', 8.0))
        scored_nodes = []
        for node in remaining_nodes:
            distance = self._distance(current_point, node.current_point)
            nearby_count = sum((1 for other in remaining_nodes if other is not node and self._distance(node.current_point, other.current_point) <= collect_radius))
            score = distance - nearby_count * density_bonus
            scored_nodes.append((score, node))
        scored_nodes.sort(key=lambda item: item[0])
        return [node for _, node in scored_nodes[:candidate_pool]]
    def _build_reward_route(self, start_point: tuple[int, int], start_direction: tuple[float, float] | None, candidates: list[GatherMemoryNode], profile: CalibrationProfile) -> list[GatherMemoryNode]:
        if not candidates:
            return []
        else:
            beam_width = max(2, int(profile.thresholds.get('gather_route_beam_width', 10.0)))
            horizon = max(1, int(profile.thresholds.get('gather_route_horizon_waypoints', 4.0)))
            collect_radius = float(profile.thresholds.get('gather_collect_radius_px', 18.0))
            distance_budget = float(profile.thresholds.get('gather_route_distance_budget_px', 0.0))
            if distance_budget <= 0.0:
                distance_budget = self._effective_memory_half_extent(profile) * 1.85
            reward_per_enemy = float(profile.thresholds.get('gather_reward_per_enemy', 28.0))
            pack_bonus = float(profile.thresholds.get('gather_reward_pack_bonus', 8.0))
            distance_penalty = float(profile.thresholds.get('gather_reward_distance_penalty', 1.0))
            turn_penalty = float(profile.thresholds.get('gather_reward_turn_penalty', 9.0))
            isolation_penalty = float(profile.thresholds.get('gather_reward_isolation_penalty', 12.0))
            isolation_distance = float(profile.thresholds.get('gather_reward_isolation_distance_px', 26.0))
            forward_bonus = float(profile.thresholds.get('gather_reward_forward_bonus', 4.0))
            initial_state = (0.0, 0.0, start_point, start_direction, [], set())
            states = [initial_state]
            best_state = initial_state
            for _ in range(horizon):
                next_states = []
                for total_score, total_distance, current_point, current_direction, path, covered_ids in states:
                    remaining_nodes = [node for node in candidates if id(node) not in covered_ids]
                    if not remaining_nodes:
                        if total_score > best_state[0]:
                            best_state = (total_score, total_distance, current_point, current_direction, path, covered_ids)
                        continue
                    else:
                        for node in self._candidate_nodes_for_state(current_point, remaining_nodes, profile):
                            covered_nodes = [other for other in remaining_nodes if self._distance(node.current_point, other.current_point) <= collect_radius]
                            if not covered_nodes:
                                continue
                            else:
                                distance = self._distance(current_point, node.current_point)
                                next_direction = self._normalize_vector(node.current_point[0] - current_point[0], node.current_point[1] - current_point[1]) or current_direction
                                direction_alignment = 0.0
                                if current_direction is not None and next_direction is not None:
                                        direction_alignment = current_direction[0] * next_direction[0] + current_direction[1] * next_direction[1]
                                reward = len(covered_nodes) * reward_per_enemy
                                reward += max(0, len(covered_nodes) - 1) * pack_bonus
                                cost = distance * distance_penalty
                                cost += max(0.0, -direction_alignment) * turn_penalty
                                cost -= max(0.0, direction_alignment) * forward_bonus
                                if len(covered_nodes) == 1 and distance >= isolation_distance:
                                        cost += isolation_penalty
                                next_score = total_score + reward - cost
                                next_distance = total_distance + distance
                                if next_distance > distance_budget:
                                    continue
                                else:
                                    next_path = path + [node]
                                    next_covered = set(covered_ids)
                                    next_covered.update((id(covered) for covered in covered_nodes))
                                    state = (next_score, next_distance, node.current_point, next_direction, next_path, next_covered)
                                    next_states.append(state)
                                    if next_score > best_state[0] or (abs(next_score - best_state[0]) <= 1e-06 and len(next_path) > len(best_state[4])):
                                        best_state = state
                if not next_states:
                    break
                else:
                    next_states.sort(key=lambda state: (-state[0], -len(state[4]), state[1]))
                    states = next_states[:beam_width]
            return best_state[4]
    def _select_terminal_cluster(self, center: tuple[int, int], clusters: list[GatherCluster], pinned_cluster: GatherCluster | None, profile: CalibrationProfile) -> GatherCluster | None:
        if not clusters:
            return None
        else:
            if len(clusters) == 1:
                return clusters[0]
            else:
                terminal_size_bonus = float(profile.thresholds.get('gather_route_terminal_size_bonus', 6.0))
                eligible = [cluster for cluster in clusters if cluster is not pinned_cluster]
                if not eligible:
                    eligible = list(clusters)
                return min(eligible, key=lambda cluster: (self._distance(center, self._cluster_point(cluster)) - len(cluster.members) * terminal_size_bonus, self._distance(center, self._cluster_point(cluster)), -len(cluster.members)))
    def _order_route_clusters(self, center: tuple[int, int], forward_vector: tuple[float, float] | None, clusters: list[GatherCluster], pinned_cluster: GatherCluster | None, terminal_cluster: GatherCluster | None, profile: CalibrationProfile) -> list[GatherCluster]:
        remaining = list(clusters)
        ordered = []
        current_point = center
        current_direction = forward_vector
        if pinned_cluster is not None and pinned_cluster in remaining:
                ordered.append(pinned_cluster)
                remaining.remove(pinned_cluster)
                pinned_point = self._cluster_point(pinned_cluster)
                next_direction = self._normalize_vector(pinned_point[0] - current_point[0], pinned_point[1] - current_point[1])
                current_point = pinned_point
                current_direction = next_direction or current_direction
        while remaining:
            candidates = remaining
            if len(remaining) > 1 and terminal_cluster is not None and (terminal_cluster in remaining):
                        non_terminal = [cluster for cluster in remaining if cluster is not terminal_cluster]
                        if non_terminal:
                            candidates = non_terminal
            next_cluster = max(candidates, key=lambda cluster: self._cluster_route_value(current_point=current_point, current_direction=current_direction, cluster=cluster, remaining=remaining, profile=profile))
            ordered.append(next_cluster)
            remaining.remove(next_cluster)
            next_point = self._cluster_point(next_cluster)
            next_direction = self._normalize_vector(next_point[0] - current_point[0], next_point[1] - current_point[1])
            current_point = next_point
            current_direction = next_direction or current_direction
        return ordered
    def _build_route(self, center: tuple[int, int], profile: CalibrationProfile, forward_vector: tuple[float, float] | None=None) -> bool:
        mode = self._gather_logic_mode(profile)
        min_seen_frames = int(profile.thresholds.get('gather_memory_min_seen_frames', 1))
        min_target_radius = float(profile.thresholds.get('gather_route_min_target_radius_px', max(profile.thresholds.get('gather_collected_memory_radius_px', 22.0) + 8.0, profile.thresholds.get('visit_distance_px', 12.0) + 16.0)))
        candidates = [node for node in self.memory_nodes if not node.reached and node.seen_frames >= min_seen_frames]
        if not candidates:
            self.route_steps = []
            self.route_index = 0
            return False
        else:
            merge_distance = float(profile.thresholds.get('gather_memory_merge_distance_px', 10.0))
            pinned_node = None
            if self.active_target is not None:
                pinned_node = self._find_matching_node_consistent(self.active_target, max(merge_distance, 18.0), center, outward_tolerance_px=float(profile.thresholds.get('gather_target_match_outward_tolerance_px', 14.0)), angle_threshold_deg=float(profile.thresholds.get('gather_target_match_angle_threshold_deg', 34.0)))
            if pinned_node is None and self.route_steps and (self.route_index < len(self.route_steps)):
                        current_route_step = self.route_steps[self.route_index]
                        if current_route_step.node in candidates:
                            pinned_node = current_route_step.node
            filtered_candidates = [node for node in candidates if node is pinned_node or self._distance(center, node.current_point) >= min_target_radius]
            if filtered_candidates:
                candidates = filtered_candidates
            clusters = self._build_clusters(list(candidates), profile)
            ranked_clusters = self._rank_clusters(center, None, clusters, profile)
            max_route_nodes = max(1, int(profile.thresholds.get('gather_route_max_clusters', 4.0)))
            candidate_limit = max(max_route_nodes, int(profile.thresholds.get('gather_route_candidate_clusters', max_route_nodes + 3.0)))
            selected_clusters = ranked_clusters[:candidate_limit]
            pinned_cluster = None
            if pinned_node is not None:
                for cluster in selected_clusters:
                    if pinned_node in cluster.members:
                        pinned_cluster = cluster
                        break
            selected_clusters = self._filter_route_clusters(center, selected_clusters, profile, pinned_cluster)
            if not selected_clusters:
                self.route_steps = []
                self.route_index = 0
                return False
            else:
                ordered_clusters = self._order_clusters_for_logic(center=center, forward_vector=forward_vector, selected_clusters=selected_clusters, pinned_cluster=pinned_cluster, profile=profile, mode=mode)
                route_steps = []
                entry_point = center
                for cluster in ordered_clusters:
                    cluster_pinned_node = pinned_node if pinned_node in cluster.members else None
                    representative = self._cluster_representative(cluster, entry_point, pinned_node=cluster_pinned_node)
                    planned_point = (int(representative.current_point[0]), int(representative.current_point[1]))
                    route_steps.append(GatherRouteStep(node=representative, planned_point=planned_point, current_point=planned_point, cluster_size=max(1, len(cluster.members)), cluster_node_ids={id(member) for member in cluster.members}, centroid=cluster.centroid))
                    entry_point = planned_point
                self.route_steps = route_steps
                self.route_index = 0
                self.last_route_build_at = time.monotonic()
                self.route_step_missing_started_at = 0.0
                planned_points = [step.planned_point for step in self.route_steps]
                terminal_point = planned_points[(-1)] if planned_points else None
                self.logger.info('Built gather route: mode=%s count=%s clusters=%s terminal=%s weights=%s points=%s extent=%.0f', mode, len(self.route_steps), len(clusters), terminal_point, [step.cluster_size for step in self.route_steps], planned_points, self._effective_memory_half_extent(profile))
                return True
    def _needs_route_rebuild(self, profile: CalibrationProfile) -> bool:
        # ***<module>.NavigationController._needs_route_rebuild: Failure: Different control flow
        if self.active_target is not None:
            return False
        else:
            if self.route_steps and self.route_index >= len(self.route_steps):
                return True
            else:
                now = time.monotonic()
                rebuild_s = float(profile.timeouts.get('gather_route_rebuild_seconds', 0.8))
                commit_s = float(profile.timeouts.get('gather_route_commit_seconds', max(1.8, rebuild_s * 2.5)))
                if now - self.last_route_build_at < max(rebuild_s, commit_s):
                    return False
                else:
                    route_missing_frames = int(profile.thresholds.get('gather_route_missing_frames', 8))
                    center = self._center(profile)
                    current_live_point = self._route_step_live_point(self.route_steps[self.route_index], route_missing_frames, profile=profile, center=center, commit=False)
                    if current_live_point is not None:
                        self.route_step_missing_started_at = 0.0
                        return False
                    else:
                        missing_grace_s = float(profile.timeouts.get('gather_route_step_missing_grace_seconds', 1.2))
                        if self.route_step_missing_started_at <= 0.0:
                            self.route_step_missing_started_at = now
                            return False
                        else:
                            if now - self.route_step_missing_started_at < missing_grace_s:
                                return False
                            else:
                                return True
    def has_route(self) -> bool:
        return bool(self.route_steps)
    def has_memory_targets(self) -> bool:
        return any((not node.reached for node in self.memory_nodes))
    def route_progress(self) -> tuple[int, int]:
        return (min(self.route_index, len(self.route_steps)), len(self.route_steps))
    def route_finished(self) -> bool:
        return bool(self.route_steps) and self.route_index >= len(self.route_steps)
    def route_debug_points(self, profile: CalibrationProfile) -> list[tuple[int, int]]:
        if not self.route_steps:
            return []
        else:
            center = self._center(profile)
            route_missing_frames = int(profile.thresholds.get('gather_route_missing_frames', 8))
            points = []
            reference_point = center
            for step in self.route_steps:
                live_point = self._route_step_live_point(step, route_missing_frames, profile=profile, reference_point=reference_point, center=center, commit=False)
                point = live_point if live_point is not None else step.current_point
                points.append(point)
                reference_point = point
            return points
    def route_debug_terminal(self, profile: CalibrationProfile) -> tuple[int, int] | None:
        points = self.route_debug_points(profile)
        if not points:
            return None
        else:
            return points[(-1)]
    def route_debug_weights(self) -> list[int]:
        return [step.cluster_size for step in self.route_steps]
    @staticmethod
    def _round_point(x: float, y: float) -> tuple[int, int]:
        return (int(round(x)), int(round(y)))
    @staticmethod
    def _blend_point(current: tuple[int, int], target: tuple[int, int], alpha: float, max_step: float) -> tuple[int, int]:
        dx = float(target[0] - current[0])
        dy = float(target[1] - current[1])
        distance = math.hypot(dx, dy)
        if distance <= 0.001:
            return current
        else:
            step = min(distance, max_step, max(1.0, distance * alpha))
            scale = step / distance
            return (int(round(current[0] + dx * scale)), int(round(current[1] + dy * scale)))
    def _clamp_live_point_outward(self, current_point: tuple[int, int], live_point: tuple[int, int], center: tuple[int, int] | None, outward_tolerance_px: float) -> tuple[int, int]:
        if center is None:
            return live_point
        else:
            current_radius = self._distance(center, current_point)
            live_radius = self._distance(center, live_point)
            if live_radius <= current_radius + outward_tolerance_px:
                return live_point
            else:
                return current_point
    def _route_step_live_point(self, step: GatherRouteStep, route_missing_frames: int, profile: CalibrationProfile | None=None, reference_point: tuple[int, int] | None=None, center: tuple[int, int] | None=None, commit: bool=True) -> tuple[int, int] | None:
        # ***<module>.NavigationController._route_step_live_point: Failure: Different control flow
        if not step.node.reached and step.node.missing_frames <= route_missing_frames and (id(step.node) in step.cluster_node_ids):
            return step.node.current_point
        else:
            live_points = [node for node in self.memory_nodes if not (id(node) in step.cluster_node_ids and (node.reached or node.missing_frames <= route_missing_frames))]
            if live_points:
                anchor = reference_point or step.current_point or step.planned_point or center
                fallback_node = min(live_points, key=lambda node: self._distance(anchor, node.current_point))
                if commit:
                    step.node = fallback_node
                return fallback_node.current_point
            else:
                if profile is not None:
                    anchor = reference_point or step.current_point or step.planned_point or center
                    if anchor is not None:
                        reacquire_distance = max(float(profile.thresholds.get('gather_route_step_reacquire_distance_px', 56.0)), float(profile.thresholds.get('gather_route_locked_match_distance_px', 42.0)))
                        reacquire_radius_tolerance = float(profile.thresholds.get('gather_route_step_reacquire_radius_tolerance_px', 28.0))
                        reacquire_angle_threshold_deg = float(profile.thresholds.get('gather_route_step_reacquire_angle_threshold_deg', 42.0))
                        anchor_radius = self._distance(center, anchor) if center is not None else 0.0
                        anchor_vec = (anchor[0] - center[0], anchor[1] - center[1]) if center is not None else None
                        best_node = None
                        best_score = None
                        for node in self.memory_nodes:
                            if node.reached or node.missing_frames > route_missing_frames:
                                continue
                            else:
                                point = node.current_point
                                distance = self._distance(anchor, point)
                                if distance > reacquire_distance:
                                    continue
                                else:
                                    radius_delta = 0.0
                                    angle_delta_deg = 0.0
                                    if center is not None:
                                        point_radius = self._distance(center, point)
                                        radius_delta = point_radius - anchor_radius
                                        if radius_delta > reacquire_radius_tolerance:
                                            continue
                                        else:
                                            point_vec = (point[0] - center[0], point[1] - center[1])
                                            if anchor_vec is not None and (anchor_vec[0]!= 0 or anchor_vec[1]!= 0):
                                                    if point_vec[0] == 0 and point_vec[1] == 0:
                                                            continue
                                                    angle_delta_deg = abs(math.degrees(self._signed_angle(anchor_vec, point_vec)))
                                                    if angle_delta_deg > reacquire_angle_threshold_deg:
                                                        continue
                                    score = (distance, angle_delta_deg, abs(radius_delta), node.missing_frames)
                                    if best_score is None or score < best_score:
                                        best_node = node
                                        best_score = score
                        if best_node is not None:
                            if commit and best_node is not step.node:
                                    self.logger.info('Reacquired gather route target: %s -> %s', step.node.current_point, best_node.current_point)
                            if commit:
                                step.node = best_node
                                step.cluster_node_ids.add(id(best_node))
                            return best_node.current_point
    def _resolve_route_target(self, profile: CalibrationProfile) -> tuple[int, int] | None:
        # ***<module>.NavigationController._resolve_route_target: Failure: Compilation Error
        center = self._center(profile)
        min_target_radius = float(profile.thresholds.get('gather_route_min_target_radius_px', max(profile.thresholds.get('gather_collected_memory_radius_px', 22.0) + 8.0, profile.thresholds.get('visit_distance_px', 12.0) + 16.0)))
        route_missing_frames = int(profile.thresholds.get('gather_route_missing_frames', 8))
        track_distance = max(float(profile.thresholds.get('gather_target_track_move_px', 18.0)), float(profile.thresholds.get('gather_target_hold_match_distance_px', 36.0)))
        missing_grace_s = float(profile.timeouts.get('gather_route_step_missing_grace_seconds', 1.2))
        now = time.monotonic()
        if self.route_index < len(self.route_steps):
            step = self.route_steps[self.route_index]
            node = step.node
            live_point = self._route_step_live_point(step, route_missing_frames, profile=profile, reference_point=step.current_point, center=center)
            if node.reached:
                self.route_step_missing_started_at = 0.0
                self.logger.info('Skipping gather route node %s/%s: %s', self.route_index + 1, len(self.route_steps), step.planned_point)
                self.route_index += 1
            else:
                if live_point is None:
                    if self.route_step_missing_started_at <= 0.0:
                        self.route_step_missing_started_at = now
                    if now - self.route_step_missing_started_at < missing_grace_s:
                        fallback_point = self.active_target if self.active_target is not None else step.current_point
                        self._set_active_target(fallback_point, track_distance=track_distance)
                        return fallback_point
                    else:
                        self.logger.info('Skipping gather route node %s/%s after missing grace: %s', self.route_index + 1, len(self.route_steps), step.planned_point)
                        self.route_index += 1
                        self.route_step_missing_started_at = 0.0
                else:
                    self.route_step_missing_started_at = 0.0
                    step.current_point = live_point
                    if center is not None and self._distance(center, step.current_point) < min_target_radius:
                            self.logger.info('Skipping gather route node %s/%s near center: %s radius=%.1f', self.route_index + 1, len(self.route_steps), step.current_point, self._distance(center, step.current_point))
                            step.node.reached = True
                            self.route_index += 1
                            continue
                    self._set_active_target(step.current_point, track_distance=track_distance)
                    return step.current_point
        self._set_active_target(None)
        self.route_step_missing_started_at = 0.0
    def choose_target(self, snapshot: VisionSnapshot, profile: CalibrationProfile, current_target: tuple[int, int] | None=None) -> tuple[int, int] | None:
        center = self._center(profile)
        if center is None:
            return None
        self._update_memory(snapshot, profile, center)
        if current_target is not None and self.active_target is None:
                hold_match_distance = max(float(profile.thresholds.get('gather_target_hold_match_distance_px', 36.0)), float(profile.thresholds.get('gather_target_track_move_px', 18.0)))
                reuse_distance = max(float(profile.thresholds.get('visited_reuse_distance_px', 12.0)), float(profile.thresholds.get('gather_switch_distance_px', 24.0)))
                matched_node = self._find_matching_node_consistent(current_target, hold_match_distance, center, outward_tolerance_px=float(profile.thresholds.get('gather_target_match_outward_tolerance_px', 14.0)), angle_threshold_deg=float(profile.thresholds.get('gather_target_match_angle_threshold_deg', 34.0)))
                if matched_node is not None and (not self._is_recently_visited(current_target, reuse_distance)):
                        self._set_active_target(matched_node.current_point, track_distance=hold_match_distance)
        route_active = bool(self.route_steps) and self.route_index < len(self.route_steps)
        if not route_active:
            tracked_target = self._track_active_target(snapshot, profile)
            if tracked_target is not None:
                return tracked_target
        if self._needs_route_rebuild(profile):
            self._build_route(center, profile, forward_vector=self._forward_vector(snapshot, profile))
        target = self._resolve_route_target(profile)
        if target is None:
            if self.route_finished():
                self.route_steps = []
                self.route_index = 0
        return target
    def _local_enemy_density(self, point: tuple[int, int], enemies: list[tuple[int, int]], profile: CalibrationProfile) -> tuple[float, int]:
        sigma_px = float(profile.thresholds.get('gather_aggro_density_sigma_px', 24.0))
        near_radius = float(profile.thresholds.get('gather_aggro_nearby_radius_px', 30.0))
        sigma_sq = max(1.0, sigma_px * sigma_px)
        density = 0.0
        near_count = 0
        for enemy in enemies:
            distance = self._distance(point, enemy)
            if distance <= near_radius:
                near_count += 1
            density += math.exp(-(distance * distance) / (2.0 * sigma_sq))
        return (density, near_count)
    def mark_visited_if_reached(self, target: tuple[int, int] | None, snapshot: VisionSnapshot, profile: CalibrationProfile) -> bool:
        # ***<module>.NavigationController.mark_visited_if_reached: Failure: Different control flow
        if target is None:
            return False
        else:
            center = self._center(profile)
            if center is None:
                return False
            else:
                hard_capture_distance = max(float(profile.thresholds.get('visit_distance_px', 12.0)), float(profile.thresholds.get('gather_route_capture_distance_px', profile.thresholds.get('visit_distance_px', 12.0))))
                aggro_capture_distance = max(hard_capture_distance, float(profile.thresholds.get('gather_aggro_capture_distance_px', 42.0)))
                aggro_marker_capture_distance = max(hard_capture_distance, float(profile.thresholds.get('gather_aggro_marker_capture_distance_px', aggro_capture_distance)))
                aggro_marker_capture_min_distance = max(0.0, float(profile.thresholds.get('gather_aggro_marker_capture_min_distance_px', 0.0)))
                aggro_marker_capture_max_distance = max(aggro_marker_capture_min_distance, float(profile.thresholds.get('gather_aggro_marker_capture_max_distance_px', min(18.0, aggro_marker_capture_distance))))
                aggro_density_threshold = float(profile.thresholds.get('gather_aggro_density_threshold', 1.6))
                aggro_nearby_points = max(1, int(profile.thresholds.get('gather_aggro_nearby_points', 2.0)))
                aggro_marker_min_count = max(1, int(profile.thresholds.get('gather_aggro_marker_min_count', 1.0)))
                merge_distance = float(profile.thresholds.get('gather_memory_merge_distance_px', 10.0))
                collect_radius = float(profile.thresholds.get('gather_collect_radius_px', max(hard_capture_distance, merge_distance)))
                route_soft_capture_distance = float(profile.thresholds.get('gather_route_soft_capture_distance_px', max(float(profile.thresholds.get('gather_route_capture_distance_px', hard_capture_distance)), 60.0)))
                route_soft_capture_nearby_points = max(1, int(profile.thresholds.get('gather_route_soft_capture_nearby_points', 1.0)))
                route_soft_capture_min_progress = float(profile.thresholds.get('gather_route_soft_capture_min_progress_px', 18.0))
                route_soft_capture_min_lock_seconds = float(profile.timeouts.get('gather_route_soft_capture_min_lock_seconds', 0.45))
                distance = self._distance(center, target)
                target_progress = 0.0
                if self.active_target_initial_distance is not None and self.active_target_best_distance is not None:
                        target_progress = max(0.0, self.active_target_initial_distance - self.active_target_best_distance)
                target_lock_age = max(0.0, time.monotonic() - self.active_target_started_at) if self.active_target_started_at > 0.0 else 0.0
                local_density, near_count = self._local_enemy_density(target, snapshot.minimap_enemies, profile)
                aggro_density_captured = distance <= aggro_capture_distance and (local_density >= aggro_density_threshold or near_count >= aggro_nearby_points)
                route_soft_captured = self.route_index < len(self.route_steps) and distance <= route_soft_capture_distance and (target_progress >= route_soft_capture_min_progress) and (target_lock_age >= route_soft_capture_min_lock_seconds) and (near_count >= route_soft_capture_nearby_points or snapshot.enemy_aggro_count >= aggro_marker_min_count or local_density >= max(1.0, aggro_density_threshold * 0.8))
                aggro_marker_captured = aggro_marker_capture_min_distance <= distance <= aggro_marker_capture_max_distance and snapshot.enemy_aggro_count >= aggro_marker_min_count
                reached = distance <= hard_capture_distance or route_soft_captured or aggro_marker_captured or aggro_density_captured
                if not reached:
                    self.reach_confirm_frames = 0
                    return False
                else:
                    confirm_frames = max(1, int(profile.thresholds.get('gather_visit_confirm_frames', 2.0)))
                    if route_soft_captured:
                        confirm_frames = min(confirm_frames, max(1, int(profile.thresholds.get('gather_route_soft_capture_confirm_frames', 1.0))))
                    if aggro_marker_captured:
                        confirm_frames = max(confirm_frames, int(profile.thresholds.get('gather_aggro_marker_confirm_frames', 2.0)))
                    self.reach_confirm_frames += 1
                    if self.reach_confirm_frames < confirm_frames:
                        return False
                    else:
                        now = time.monotonic()
                        self.visited_targets.append((target, now))
                        matched_cluster_node_ids = set()
                        match_distance = max(aggro_capture_distance, merge_distance, collect_radius)
                        matched = 0
                        if self.route_index < len(self.route_steps):
                            current_step = self.route_steps[self.route_index]
                            current_step.node.reached = True
                            matched_cluster_node_ids.add(id(current_step.node))
                            for node in self.memory_nodes:
                                if id(node) not in current_step.cluster_node_ids or node.reached:
                                    continue
                                else:
                                    if self._distance(node.current_point, target) <= match_distance or self._distance(node.seed_point, target) <= match_distance:
                                        matched_cluster_node_ids.add(id(node))
                            matched = max(1, len(matched_cluster_node_ids))
                        else:
                            if self.active_target is not None:
                                matched = 1
                        future_route_node_ids = set()
                        if self.route_index + 1 < len(self.route_steps):
                            for future_step in self.route_steps[self.route_index + 1:]:
                                future_route_node_ids.update(future_step.cluster_node_ids)
                        fallback_nodes = 0
                        for node in self.memory_nodes:
                            if id(node) in matched_cluster_node_ids:
                                node.reached = True
                                continue
                            else:
                                if id(node) in future_route_node_ids:
                                    continue
                                else:
                                    if self._distance(node.current_point, target) <= match_distance or self._distance(node.seed_point, target) <= match_distance:
                                        node.reached = True
                                        fallback_nodes += 1
                        fallback_bonus_cap = max(0, int(profile.thresholds.get('gather_reached_fallback_bonus_cap', 2.0)))
                        while self.route_index < len(self.route_steps) and self.route_steps[self.route_index].node.reached:
                            self.last_reached_count = max(1, matched + min(fallback_nodes, fallback_bonus_cap))
                            self._set_active_target(None)
                            self.route_step_missing_started_at = 0.0
                            self.reach_confirm_frames = 0
                            self.distance_history.clear()
                            return True
                        else:
                            self.logger.info('Gather route step reached: %s/%s target=%s weight=%s', self.route_index + 1, len(self.route_steps), self.route_steps[self.route_index].node.current_point, self.route_steps[self.route_index].cluster_size)
                            self.route_index += 1
    def update_gather(self, target: tuple[int, int] | None, snapshot: VisionSnapshot, profile: CalibrationProfile) -> tuple[str, bool]:
        center = self._center(profile)
        if center is None or target is None:
            self.stop_motion()
            return ('no-target', False)
        else:
            target_vec = (target[0] - center[0], target[1] - center[1])
            distance = self._distance(center, target)
            if self.active_target == target:
                if self.active_target_initial_distance is None:
                    self.active_target_initial_distance = distance
                if self.active_target_best_distance is None:
                    self.active_target_best_distance = distance
                else:
                    self.active_target_best_distance = min(self.active_target_best_distance, distance)
            gather_turn_direction_sign = int(profile.thresholds.get('gather_turn_direction_sign', (-1)))
            sector_deadzone_deg = float(profile.thresholds.get('gather_sector_deadzone_deg', 12.0))
            heading_turn_gain = float(profile.thresholds.get('gather_heading_turn_gain_px_per_deg', 3.2))
            heading_turn_min_dx = float(profile.thresholds.get('gather_heading_turn_min_dx', 18.0))
            heading_turn_max_dx = float(profile.thresholds.get('gather_heading_turn_max_dx', 320.0))
            forward_vector = self._forward_vector(snapshot, profile)
            heading_error = self._signed_angle(forward_vector, target_vec)
            heading_error_deg = math.degrees(heading_error)
            abs_error_deg = abs(heading_error_deg)
            turn_in_place_threshold_deg = float(profile.thresholds.get('gather_turn_in_place_threshold_deg', 155.0))
            turn_in_place_distance_px = float(profile.thresholds.get('gather_turn_in_place_distance_px', 52.0))
            move_heading_threshold_deg = float(profile.thresholds.get('gather_move_heading_threshold_deg', 62.0))
            close_move_heading_threshold_deg = float(profile.thresholds.get('gather_close_move_heading_threshold_deg', 88.0))
            close_move_distance_px = float(profile.thresholds.get('gather_close_move_distance_px', 34.0))
            sprint_heading_threshold_deg = float(profile.thresholds.get('gather_sprint_heading_threshold_deg', 36.0))
            stuck_measure_alignment_threshold_deg = float(profile.thresholds.get('gather_stuck_measure_alignment_threshold_deg', max(24.0, sprint_heading_threshold_deg)))
            stuck_min_distance_px = float(profile.thresholds.get('gather_stuck_min_distance_px', 32.0))
            stuck_heading_confidence_threshold = float(profile.thresholds.get('gather_stuck_heading_confidence_threshold', profile.thresholds.get('minimap_heading_confidence_threshold', 0.18)))
            turn_in_place = abs_error_deg >= turn_in_place_threshold_deg and distance >= turn_in_place_distance_px
            move_heading_limit = close_move_heading_threshold_deg if distance <= close_move_distance_px else move_heading_threshold_deg
            hold_forward = not turn_in_place and abs_error_deg <= move_heading_limit
            if not hold_forward:
                self.input.release_key('W')
                self.input.release_key('SHIFT')
                self.distance_history.clear()
                self.world_coord_history.clear()
            else:
                self.input.press_key('W')
                stamina_threshold = float(profile.thresholds.get('stamina_shift_threshold', 0.55))
                if snapshot.stamina_ratio is not None and snapshot.stamina_ratio >= stamina_threshold and (abs_error_deg <= sprint_heading_threshold_deg):
                    self.input.press_key('SHIFT')
                else:
                    self.input.release_key('SHIFT')
                should_measure_stuck = abs_error_deg <= stuck_measure_alignment_threshold_deg and distance >= stuck_min_distance_px and (snapshot.minimap_heading_confidence >= stuck_heading_confidence_threshold)
                if should_measure_stuck:
                    self.distance_history.append((time.monotonic(), distance))
                else:
                    self.distance_history.clear()
                if should_measure_stuck and snapshot.world_x is not None and (snapshot.world_z is not None):
                    self.world_coord_history.append((time.monotonic(), int(snapshot.world_x), int(snapshot.world_z)))
                else:
                    self.world_coord_history.clear()
            turn_direction = 1 if heading_error_deg >= 0.0 else (-1)
            if abs_error_deg <= sector_deadzone_deg:
                mouse_dx = 0
            else:
                raw_mouse_dx = max(heading_turn_min_dx, abs_error_deg * heading_turn_gain)
                if turn_in_place:
                    raw_mouse_dx *= 1.18
                mouse_dx = turn_direction * int(round(min(heading_turn_max_dx, raw_mouse_dx)))
            mouse_dx *= gather_turn_direction_sign
            now = time.monotonic()
            if now - self._last_gather_steering_log_at >= 1.5:
                self.logger.info('Gather steering: mode=%s target=%s distance=%.1f heading_error=%.1f heading_conf=%.3f hold_w=%s turn_in_place=%s mouse_dx=%s enemies=%s route=%s/%s', self._gather_logic_mode(profile), target, distance, heading_error_deg, float(snapshot.minimap_heading_confidence), hold_forward, turn_in_place, mouse_dx, len(snapshot.minimap_enemies), self.route_index, len(self.route_steps))
                self._last_gather_steering_log_at = now
            if mouse_dx!= 0:
                self.input.move_mouse_relative(mouse_dx, 0)
            if self.mark_visited_if_reached(target, snapshot, profile):
                return ('target-reached', False)
            else:
                stuck = self.is_stuck(profile, heading_error_deg=abs_error_deg, target_distance=distance, heading_confidence=float(snapshot.minimap_heading_confidence))
                if turn_in_place:
                    return ('turning', stuck)
                else:
                    if not hold_forward:
                        return ('aligning', stuck)
                    else:
                        return ('moving', stuck)
    def is_stuck(self, profile: CalibrationProfile, heading_error_deg: float | None=None, target_distance: float | None=None, heading_confidence: float | None=None) -> bool:
        now = time.monotonic()
        if self.active_target_started_at > 0.0:
            grace_after_lock = float(profile.timeouts.get('stuck_after_target_lock_seconds', 1.2))
            if now - self.active_target_started_at < grace_after_lock:
                return False
        stable_frames_required = max(1, int(profile.thresholds.get('gather_stuck_target_stable_frames', 3.0)))
        if self.active_target_stable_frames < stable_frames_required:
            return False
        else:
            target_shift_grace_s = float(profile.timeouts.get('gather_stuck_target_shift_grace_seconds', 1.0))
            if self.active_target_last_move_at > 0.0:
                if now - self.active_target_last_move_at < target_shift_grace_s:
                    return False
            if heading_error_deg is not None:
                alignment_threshold = float(profile.thresholds.get('gather_stuck_measure_alignment_threshold_deg', 32.0))
                if heading_error_deg > alignment_threshold:
                    return False
            if target_distance is not None:
                min_distance = float(profile.thresholds.get('gather_stuck_min_distance_px', 32.0))
                if target_distance < min_distance:
                    return False
            if heading_confidence is not None:
                confidence_threshold = float(profile.thresholds.get('gather_stuck_heading_confidence_threshold', profile.thresholds.get('minimap_heading_confidence_threshold', 0.18)))
                if heading_confidence < confidence_threshold:
                    return False
            coord_window_s = float(profile.timeouts.get('gather_stuck_coord_window_seconds', 2.0))
            coord_min_movement = float(profile.thresholds.get('gather_stuck_coord_min_movement_units', 5.0))
            recent_coords = [(ts, x, z) for ts, x, z in self.world_coord_history if now - ts <= coord_window_s]
            if len(recent_coords) < 4:
                return False
            else:
                span = recent_coords[(-1)][0] - recent_coords[0][0]
                if span < max(1.6, coord_window_s * 0.8):
                    return False
                else:
                    first_x, first_z = (recent_coords[0][1], recent_coords[0][2])
                    max_displacement = max((math.hypot(float(x - first_x), float(z - first_z)) for _, x, z in recent_coords))
                    return max_displacement < coord_min_movement
    def _abandon_active_target(self) -> None:
        if self.active_target is None:
            return None
        else:
            self.logger.info('Abandoning gather target after repeated anti-stuck: %s', self.active_target)
            self.visited_targets.append((self.active_target, time.monotonic()))
            if self.route_index < len(self.route_steps):
                self.route_steps[self.route_index].node.reached = True
                self.route_index += 1
            self._set_active_target(None)
            self.distance_history.clear()
    def anti_stuck(self, profile: CalibrationProfile | None=None) -> None:
        self.anti_stuck_attempt += 1
        self.active_target_stuck_attempts += 1
        direction = (-1) if self.anti_stuck_attempt % 2 == 0 else 1
        strafe_key = 'A' if direction < 0 else 'D'
        mouse_dx = self.config.anti_stuck_mouse_dx * direction
        self.logger.warning('Anti-stuck triggered: attempt=%s strafe=%s mouse_dx=%s', self.anti_stuck_attempt, strafe_key, mouse_dx)
        self.stop_motion()
        self.input.tap_key('S', hold_s=0.22)
        self.input.tap_key(strafe_key, hold_s=0.18)
        self.input.move_mouse_relative(mouse_dx, 0)
        self.input.tap_key('SPACE', hold_s=0.06)
        self.distance_history.clear()
        self.world_coord_history.clear()
        if profile is not None:
            abandon_attempts = max(1, int(profile.thresholds.get('gather_target_abandon_attempts', 4.0)))
            if self.active_target_stuck_attempts >= abandon_attempts:
                self._abandon_active_target()
    def update_pack(self, snapshot: VisionSnapshot, profile: CalibrationProfile) -> None:
        self.input.press_key('W')
        stamina_threshold = float(profile.thresholds.get('stamina_shift_threshold', 0.55))
        if snapshot.stamina_ratio is not None and snapshot.stamina_ratio >= stamina_threshold:
            self.input.press_key('SHIFT')
        else:
            self.input.release_key('SHIFT')
        pack_turn_scale = float(profile.thresholds.get('pack_turn_scale', 1.15))
        pack_mouse_dx = max(1, int(round(self.config.pack_mouse_dx * pack_turn_scale)))
        self.input.move_mouse_relative(pack_mouse_dx, 0)
    def search_for_targets(self, snapshot: VisionSnapshot, profile: CalibrationProfile) -> None:
        self.input.press_key('W')
        stamina_threshold = float(profile.thresholds.get('stamina_shift_threshold', 0.55))
        if snapshot.stamina_ratio is not None and snapshot.stamina_ratio >= stamina_threshold:
            self.input.press_key('SHIFT')
        else:
            self.input.release_key('SHIFT')
        base_mouse_dx = int(profile.thresholds.get('gather_search_mouse_dx', 22))
        interval = max(1, int(profile.thresholds.get('gather_search_turn_interval_frames', 4)))
        sweep_growth = int(profile.thresholds.get('gather_search_sweep_growth_dx', 6.0))
        sweep_max = int(profile.thresholds.get('gather_search_max_dx', 96.0))
        cycle_frames = max(interval * 2, int(profile.thresholds.get('gather_search_cycle_frames', 20.0)))
        if self.search_step % cycle_frames == 0:
            self.search_direction *= (-1)
        sweep_stage = max(0, self.search_step // interval)
        turn_dx = min(sweep_max, base_mouse_dx + sweep_stage * sweep_growth)
        self.input.move_mouse_relative(turn_dx * self.search_direction, 0)
        self.search_step += 1
    def target_distance(self, target: tuple[int, int] | None, profile: CalibrationProfile) -> float | None:
        if target is None:
            return None
        else:
            center = self._center(profile)
            if center is None:
                return None
            else:
                return self._distance(center, target)
    def stop_motion(self) -> None:
        self.input.release_key('W')
        self.input.release_key('A')
        self.input.release_key('S')
        self.input.release_key('D')
        self.input.release_key('SHIFT')
        self.input.release_key('SPACE')