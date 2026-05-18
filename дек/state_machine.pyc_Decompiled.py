# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\bot\\state_machine.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import logging
import math
import statistics
import time
from dataclasses import replace
from enum import Enum, auto
from threading import Event
from mmobot.bot.combat_controller import CombatController
from mmobot.bot.combat_coord_tracker import CombatCoordTracker
from mmobot.bot.compass_return_controller import CompassReturnController
from mmobot.bot.cooldown_tracker import CooldownTracker
from mmobot.bot.death_recovery_controller import DeathRecoveryController
from mmobot.bot.gather_telemetry_tracker import GatherTelemetryTracker
from mmobot.bot.go_to_farm_controller import GoToFarmController
from mmobot.bot.inventory_checker import InventoryCheckResult, InventoryChecker
from mmobot.bot.level_fast_tracker import LevelFastTracker
from mmobot.bot.minimap_fast_tracker import MinimapFastTracker
from mmobot.bot.navigation_controller import NavigationController
from mmobot.bot.town_teleport_controller import TownTeleportController
from mmobot.bot.vendor_sell_controller import VendorSellController
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine, VisionSnapshot
class BotPhase(Enum):
    IDLE = auto()
    GATHER = auto()
    PACK = auto()
    COMBAT = auto()
    INVENTORY_RETURN = auto()
    ERROR = auto()
class BotStateMachine:
    pass
    def __init__(self, capture: ScreenCapture, vision: VisionEngine, input_controller: InputController, profile: CalibrationProfile, config: AppConfig, stop_event: Event, auto_attack_enabled: bool=True, fast_minimap_tracker: MinimapFastTracker | None=None, fast_level_tracker: LevelFastTracker | None=None, combat_coord_tracker: CombatCoordTracker | None=None, gather_telemetry_tracker: GatherTelemetryTracker | None=None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.capture = capture
        self.vision = vision
        self.input = input_controller
        self.profile = profile
        self.config = config
        self.stop_event = stop_event
        self.auto_attack_enabled = auto_attack_enabled
        self.fast_minimap_tracker = fast_minimap_tracker
        self.fast_level_tracker = fast_level_tracker
        self.combat_coord_tracker = combat_coord_tracker
        self.gather_telemetry_tracker = gather_telemetry_tracker
        self.cooldowns = CooldownTracker()
        self.navigation = NavigationController(self.input, self.config)
        self.combat = CombatController(self.input, self.cooldowns, self.config)
        self.inventory = InventoryChecker(self.input)
        self.compass = CompassReturnController(self.input, self.config)
        self.death_recovery = DeathRecoveryController(self.capture, self.vision, self.input, self.config)
        self.go_to_farm = GoToFarmController(self.capture, self.vision, self.input, self.config)
        self.teleport = TownTeleportController(self.capture, self.vision, self.input, self.config)
        self.vendor_sell = VendorSellController(self.capture, self.vision, self.input, self.config)
        self.phase = BotPhase.IDLE
        self.phase_started_at = time.monotonic()
        self.status = 'idle'
        self.current_target = None
        self.gather_no_target_frames = 0
        self.gather_dense_frames = 0
        self.gather_collected_nodes = 0
        self.gather_wait_started_at = 0.0
        self.gather_plan_locked = False
        self.gather_plan_frames = 0
        self.inventory_checked = False
        self.last_inventory_result = None
        self.return_arrival_started_at = 0.0
        self.return_last_log_at = 0.0
        self.return_cached_world_coords = None
        self.return_cached_world_at = 0.0
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0.0
        self.gather_resume_after_arrival_at = 0.0
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0.0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._last_combat_coord_age_ms = None
        self._perf_last_log_at = 0.0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0.0
        self._last_death_check_at = 0.0
    def start(self) -> None:
        self._transition(BotPhase.GATHER, 'start')
    def stop(self) -> None:
        self.status = 'stopping'
        self.combat.stop(self.profile)
        self.navigation.stop_motion()
        self.compass.stop()
        self.input.safe_release_all()
        self.phase = BotPhase.IDLE
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0.0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._last_combat_coord_age_ms = None
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0.0
        self._perf_last_log_at = 0.0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0.0
        self._last_death_check_at = 0.0
        self.logger.info('Bot stopped safely')
    def _transition(self, phase: BotPhase, reason: str) -> None:
        self.logger.info('Transition: %s -> %s (%s)', self.phase.name, phase.name, reason)
        self.phase = phase
        self.phase_started_at = time.monotonic()
        self.status = reason
        self.current_target = None
        self.gather_no_target_frames = 0
        self.gather_dense_frames = 0
        self.gather_collected_nodes = 0
        self.gather_wait_started_at = 0.0
        self.gather_plan_locked = False
        self.gather_plan_frames = 0
        self.return_arrival_started_at = 0.0
        self.return_last_log_at = 0.0
        self.return_cached_world_coords = None
        self.return_cached_world_at = 0.0
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0.0
        self.gather_resume_after_arrival_at = 0.0
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0.0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._perf_last_log_at = 0.0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0.0
        self._last_death_check_at = 0.0
        if phase == BotPhase.GATHER:
            self.navigation.reset()
            self.combat.reset(self.profile)
            self.compass.reset()
            self.inventory_checked = False
            self.last_inventory_result = None
            if reason in {'arrived-near-marker', 'arrived-near-route', 'arrived'}:
                settle_s = float(self.profile.timeouts.get('return_arrival_stop_seconds', 0.75))
                if settle_s > 0.0:
                    self.gather_resume_after_arrival_at = time.monotonic() + settle_s
        else:
            if phase == BotPhase.PACK:
                self.combat.stop(self.profile)
            else:
                if phase == BotPhase.COMBAT:
                    self.combat.reset(self.profile)
                    self.navigation.stop_motion()
                else:
                    if phase == BotPhase.INVENTORY_RETURN:
                        self.combat.stop(self.profile)
                        self.navigation.stop_motion()
                        self.compass.reset()
                        self.inventory_checked = False
                        self.return_last_log_at = 0.0
                        self.return_cached_world_coords = None
                        self.return_cached_world_at = 0.0
    def _read_stable_return_world_coords(self) -> tuple[int, int | None, int] | None:
        samples = []
        for _ in range(4):
            if self.stop_event.is_set():
                break
            else:
                frame = self.capture.grab_bgr()
                world_x, world_z = self.vision.read_minimap_xz_strong(frame, self.profile)
                world_y = None
                if world_x is None or world_z is None:
                    world_x, world_y, world_z = self.vision.read_minimap_coordinates(frame, self.profile)
                if world_x is not None and world_z is not None:
                        samples.append((int(world_x), None if world_y is None else int(world_y), int(world_z)))
                        if len(samples) >= 2:
                            break
                time.sleep(0.03)
        if not samples:
            return None
        else:
            xs = [sample[0] for sample in samples]
            ys = [sample[1] for sample in samples if sample[1] is not None]
            zs = [sample[2] for sample in samples]
            return (int(round(statistics.median(xs))), None if not ys else int(round(statistics.median(ys))), int(round(statistics.median(zs))))
    def _gather_route_anchor(self) -> tuple[int, int] | None:
        route = self.profile.get_active_go_to_farm_route()
        if not route:
            return None
        else:
            target_x, _target_y, target_z = route[(-1)]
            return (int(target_x), int(target_z))
    def _hydrate_gather_world_coords(self, snapshot: VisionSnapshot) -> None:
        now = time.monotonic()
        if snapshot.world_x is not None and snapshot.world_z is not None:
            self.gather_cached_world_coords = (int(snapshot.world_x), None if snapshot.world_y is None else int(snapshot.world_y), int(snapshot.world_z))
            self.gather_cached_world_at = now
        else:
            if self.gather_cached_world_coords is not None:
                if now - self.gather_cached_world_at <= 2.0:
                    cached_x, cached_y, cached_z = self.gather_cached_world_coords
                    snapshot.world_x = cached_x
                    snapshot.world_y = cached_y
                    snapshot.world_z = cached_z
    def _gather_route_anchor_distance(self, snapshot: VisionSnapshot) -> float | None:
        self._hydrate_gather_world_coords(snapshot)
        anchor = self._gather_route_anchor()
        if anchor is None or snapshot.world_x is None or snapshot.world_z is None:
            return None
        else:
            return math.hypot(float(anchor[0] - int(snapshot.world_x)), float(anchor[1] - int(snapshot.world_z)))
    def _run_full_inventory_service_cycle(self) -> bool:
        # ***<module>.BotStateMachine._run_full_inventory_service_cycle: Failure: Different control flow
        self.navigation.stop_motion()
        self.compass.stop()
        self.input.safe_release_all()
        self.status = 'teleport-town'
        self.logger.info('Inventory full: teleporting to town for vendor sell')
        teleported = self.teleport.teleport_to_town(self.profile, self.stop_event)
        self.navigation.stop_motion()
        self.compass.stop()
        self.input.safe_release_all()
        if teleported and self.stop_event.is_set():
            return False
        else:
            self.status = 'vendor-sell'
            self.logger.info('Inventory full: starting vendor sell after town teleport')
            sold = self.vendor_sell.sell_inventory(self.profile, self.stop_event)
            self.navigation.stop_motion()
            self.compass.stop()
            self.input.safe_release_all()
            if sold and self.stop_event.is_set():
                return False
            else:
                self.status = 'go-to-farm'
                self.logger.info('Inventory full: resuming Go To Farm after vendor sell')
                returned = self.go_to_farm.go_to_farm(self.profile, self.stop_event)
                self.navigation.stop_motion()
                self.compass.stop()
                self.input.safe_release_all()
                return bool(returned) and (not self.stop_event.is_set())
    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])
    @staticmethod
    def _copy_snapshot(snapshot: VisionSnapshot) -> VisionSnapshot:
        copied = replace(snapshot)
        copied.minimap_enemies = list(snapshot.minimap_enemies)
        copied.minimap_enemy_candidates = list(snapshot.minimap_enemy_candidates)
        copied.enemy_aggro_markers = list(snapshot.enemy_aggro_markers)
        copied.enemy_back_target = snapshot.enemy_back_target
        copied.enemy_level_targets = list(snapshot.enemy_level_targets)
        copied.enemy_nn_targets = list(snapshot.enemy_nn_targets)
        copied.enemy_hp_targets = list(snapshot.enemy_hp_targets)
        copied.enemy_body_targets = list(snapshot.enemy_body_targets)
        copied.inventory_slot_colors = dict(snapshot.inventory_slot_colors)
        return copied
    def _merge_fast_minimap(self, snapshot: VisionSnapshot) -> VisionSnapshot:
        if self.fast_minimap_tracker is None:
            self._last_fast_minimap_age_ms = None
            return snapshot
        else:
            max_age_s = max(0.01, float(self.config.minimap_fast_max_age_ms) / 1000.0)
            fast_snapshot = self.fast_minimap_tracker.get_latest(max_age_s=max_age_s)
            if fast_snapshot is None:
                self._last_fast_minimap_age_ms = None
                return snapshot
            else:
                self._last_fast_minimap_age_ms = max(0.0, (snapshot.timestamp - fast_snapshot.timestamp) * 1000.0)
                snapshot.minimap_enemies = list(fast_snapshot.minimap_enemies)
                snapshot.minimap_enemy_candidates = list(fast_snapshot.minimap_enemy_candidates)
                snapshot.minimap_heading_vector = fast_snapshot.minimap_heading_vector
                snapshot.minimap_heading_tip = fast_snapshot.minimap_heading_tip
                snapshot.minimap_heading_confidence = fast_snapshot.minimap_heading_confidence
                snapshot.nearby_enemy_count = fast_snapshot.nearby_enemy_count
                snapshot.nearest_enemy_distance = fast_snapshot.nearest_enemy_distance
                return snapshot
    def _merge_gather_telemetry(self, snapshot: VisionSnapshot) -> VisionSnapshot:
        if self.gather_telemetry_tracker is None:
            return snapshot
        else:
            if self.phase not in {BotPhase.GATHER, BotPhase.INVENTORY_RETURN}:
                return snapshot
            else:
                max_age_s = max(0.05, float(self.config.gather_telemetry_max_age_ms) / 1000.0)
                telemetry = self.gather_telemetry_tracker.get_latest(max_age_s=max_age_s)
                if telemetry is None:
                    return snapshot
                else:
                    snapshot.distance_value = telemetry.distance_value
                    snapshot.world_x = telemetry.world_x
                    snapshot.world_y = telemetry.world_y
                    snapshot.world_z = telemetry.world_z
                    return snapshot
    def _merge_fast_level(self, snapshot: VisionSnapshot) -> VisionSnapshot:
        if self.fast_level_tracker is None:
            self._last_fast_level_age_ms = None
            return snapshot
        else:
            if self.phase!= BotPhase.COMBAT or not self.combat.level_only_targeting_enabled(self.profile):
                self._last_fast_level_age_ms = None
                return snapshot
            else:
                max_age_s = max(0.01, float(self.config.combat_level_fast_max_age_ms) / 1000.0)
                fast_snapshot = self.fast_level_tracker.get_latest(max_age_s=max_age_s)
                if fast_snapshot is None:
                    self._last_fast_level_age_ms = None
                    return snapshot
                else:
                    self._last_fast_level_age_ms = max(0.0, (snapshot.timestamp - fast_snapshot.timestamp) * 1000.0)
                    snapshot.enemy_level_targets = list(fast_snapshot.enemy_level_targets)
                    return snapshot
    def _merge_combat_coords(self, snapshot: VisionSnapshot) -> VisionSnapshot:
        if self.combat_coord_tracker is None:
            self._last_combat_coord_age_ms = None
            return snapshot
        else:
            if self.phase!= BotPhase.COMBAT:
                self._last_combat_coord_age_ms = None
                return snapshot
            else:
                max_age_s = max(0.05, float(self.config.combat_coord_max_age_ms) / 1000.0)
                coord_snapshot = self.combat_coord_tracker.get_latest(max_age_s=max_age_s)
                if coord_snapshot is None:
                    self._last_combat_coord_age_ms = None
                    return snapshot
                else:
                    self._last_combat_coord_age_ms = max(0.0, (snapshot.timestamp - coord_snapshot.timestamp) * 1000.0)
                    snapshot.world_x = coord_snapshot.world_x
                    snapshot.world_y = coord_snapshot.world_y
                    snapshot.world_z = coord_snapshot.world_z
                    return snapshot
    def _build_tick_snapshot(self) -> VisionSnapshot:
        now = time.monotonic()
        combat_level_only = self.phase == BotPhase.COMBAT and self.combat.level_only_targeting_enabled(self.profile)
        include_distance = False
        include_world_coords = False
        include_target_lock = self.phase == BotPhase.COMBAT
        include_enemy_aggro = self.phase in {BotPhase.GATHER, BotPhase.COMBAT}
        include_combat_ui = self.phase == BotPhase.COMBAT
        include_compass_marker = self.phase in {BotPhase.GATHER, BotPhase.INVENTORY_RETURN}
        include_minimap = self.fast_minimap_tracker is None or self.phase == BotPhase.GATHER
        full_tick_s = max(0.01, float(self.config.worker_full_vision_tick_ms) / 1000.0)
        need_full = self._last_full_snapshot is None or self._last_full_snapshot_at <= 0.0 or now - self._last_full_snapshot_at >= full_tick_s
        if need_full:
            full_started_at = time.perf_counter()
            frame = self.capture.grab_bgr()
            snapshot = self.vision.analyze(frame, self.profile, include_distance=include_distance, include_world_coords=include_world_coords, include_inventory=False, include_minimap=include_minimap, include_target_lock=include_target_lock, include_enemy_aggro=include_enemy_aggro, include_combat_ui=include_combat_ui, include_compass_marker=include_compass_marker)
            self._last_full_snapshot = self._copy_snapshot(snapshot)
            self._last_full_snapshot_at = now
            full_processing_ms = (time.perf_counter() - full_started_at) * 1000.0
            self._perf_full_vision_updates += 1
            self._perf_full_vision_ms_sum += full_processing_ms
        else:
            snapshot = self._copy_snapshot(self._last_full_snapshot)
            snapshot.timestamp = now
        snapshot = self._merge_gather_telemetry(snapshot)
        snapshot = self._merge_fast_minimap(snapshot)
        snapshot = self._merge_fast_level(snapshot)
        return self._merge_combat_coords(snapshot)
    def _maybe_log_perf(self, now: float) -> None:
        interval_s = max(0.5, float(self.config.worker_perf_log_interval_seconds))
        self._perf_control_ticks += 1
        if self._perf_last_log_at <= 0.0:
            self._perf_last_log_at = now
            return None
        else:
            elapsed_s = now - self._perf_last_log_at
            if elapsed_s < interval_s:
                return None
            else:
                control_hz = float(self._perf_control_ticks) / max(elapsed_s, 1e-06)
                full_hz = float(self._perf_full_vision_updates) / max(elapsed_s, 1e-06)
                avg_full_ms = self._perf_full_vision_ms_sum / max(1, self._perf_full_vision_updates)
                fast_age_text = 'None' if self._last_fast_minimap_age_ms is None else f'{self._last_fast_minimap_age_ms:.1f}'
                fast_level_age_text = 'None' if self._last_fast_level_age_ms is None else f'{self._last_fast_level_age_ms:.1f}'
                combat_coord_age_text = 'None' if self._last_combat_coord_age_ms is None else f'{self._last_combat_coord_age_ms:.1f}'
                self.logger.info('Vision perf: control_hz=%.1f full_hz=%.1f avg_full_ms=%.2f fast_minimap_age_ms=%s fast_level_age_ms=%s combat_coord_age_ms=%s phase=%s status=%s', control_hz, full_hz, avg_full_ms, fast_age_text, fast_level_age_text, combat_coord_age_text, self.phase.name, self.status)
                self._perf_last_log_at = now
                self._perf_control_ticks = 0
                self._perf_full_vision_updates = 0
                self._perf_full_vision_ms_sum = 0.0
    def _try_handle_death_recovery(self) -> bool:
        # ***<module>.BotStateMachine._try_handle_death_recovery: Failure: Different control flow
        if self.phase in {BotPhase.IDLE, BotPhase.ERROR}:
            return False
        else:
            now = time.monotonic()
            cooldown_s = float(self.profile.timeouts.get('death_check_cooldown_seconds', 0.5))
            if self._last_death_check_at > 0.0 and now - self._last_death_check_at < cooldown_s:
                    return False
            self._last_death_check_at = now
            frame = self.capture.grab_bgr()
            if not self.death_recovery.is_respawn_visible(frame, self.profile):
                return False
            else:
                self.logger.info('Death recovery detected during phase=%s', self.phase.name)
                self.status = 'death-respawn'
                self.combat.stop(self.profile)
                self.navigation.stop_motion()
                self.compass.stop()
                self.input.safe_release_all()
                respawned = self.death_recovery.respawn_in_town(self.profile, self.stop_event, initial_frame=frame)
                if respawned and self.stop_event.is_set():
                    self.status = 'death-respawn-failed'
                    return True
                else:
                    if not self.death_recovery._sleep_interruptible(float(self.profile.timeouts.get('death_post_crown_delay_seconds', 1.2)), self.stop_event):
                        return True
                    else:
                        self.status = 'death-go-to-farm'
                        self.logger.info('Death recovery: crown confirmed, starting go to farm')
                        moved = self.go_to_farm.go_to_farm(self.profile, self.stop_event)
                        self.navigation.stop_motion()
                        self.compass.stop()
                        self.input.safe_release_all()
                        if moved and (not self.stop_event.is_set()):
                            self._transition(BotPhase.GATHER, 'respawn-go-to-farm')
                        else:
                            self.phase = BotPhase.ERROR
                            self.status = 'respawn-go-to-farm-failed'
                            self.logger.warning('Death recovery: go to farm failed after respawn')
                        return True
    def _count_enemies_within_radius(self, enemies: list[tuple[int, int]], radius: float) -> int:
        center_spec = self.profile.points.get('minimap_center')
        center = center_spec.as_pixels(self.profile.screen_size) if center_spec else None
        if center is None:
            return 0
        else:
            return sum((1 for enemy in enemies if self._distance(center, enemy) <= radius))
    def _has_high_density(self, enemies: list[tuple[int, int]]) -> bool:
        cluster_distance = self.profile.thresholds.get('cluster_distance_px', 18)
        neighbors_needed = int(self.profile.thresholds.get('high_density_neighbors', 2))
        for index, point in enumerate(enemies):
            neighbors = 0
            for other_index, other in enumerate(enemies):
                if index == other_index:
                    continue
                else:
                    if self._distance(point, other) <= cluster_distance:
                        neighbors += 1
            if neighbors >= neighbors_needed:
                return True
        return False
    def _tick_gather(self, snapshot: VisionSnapshot) -> None:
        # ***<module>.BotStateMachine._tick_gather: Failure: Different control flow
        if self.gather_resume_after_arrival_at > 0.0:
            remaining = self.gather_resume_after_arrival_at - time.monotonic()
            if remaining > 0.0:
                self.current_target = None
                self.navigation.clear_active_target()
                self.navigation.stop_motion()
                self.input.safe_release_all()
                self.status = f'gather-arrival-hold-{remaining:.1f}s'
                return None
            else:
                self.gather_resume_after_arrival_at = 0.0
        elapsed = time.monotonic() - self.phase_started_at
        gather_limit = self.profile.timeouts.get('gather_phase_limit_seconds', 18.0)
        respawn_wait_s = float(self.profile.timeouts.get('gather_respawn_wait_seconds', 12.0))
        gather_goal_count = int(self.profile.thresholds.get('gather_target_goal_count', 12.0))
        home_max_distance = float(self.profile.thresholds.get('gather_home_max_distance', 34.0))
        home_soft_distance = float(self.profile.thresholds.get('gather_home_soft_distance', max(self.profile.thresholds.get('gather_home_arrival_distance', 10.0) + 8.0, home_max_distance - 8.0)))
        home_finish_distance = float(self.profile.thresholds.get('gather_home_finish_distance', self.profile.thresholds.get('gather_home_arrival_distance', 10.0)))
        home_guard_distance = min(home_max_distance, max(home_finish_distance + 2.0, home_soft_distance))
        route_max_distance = float(self.profile.thresholds.get('gather_route_max_distance', max(home_max_distance * 3.0, 110.0)))
        route_finish_distance = float(self.profile.thresholds.get('gather_route_finish_distance', max(home_finish_distance + 24.0, 70.0)))
        route_soft_distance = float(self.profile.thresholds.get('gather_route_soft_distance', max(route_finish_distance + 12.0, route_max_distance - 18.0)))
        route_guard_distance = min(route_max_distance, max(route_finish_distance + 4.0, route_soft_distance))
        route_anchor = self._gather_route_anchor()
        route_anchor_distance = self._gather_route_anchor_distance(snapshot)
        guard_distance = route_anchor_distance if route_anchor is not None else float(snapshot.distance_value) if snapshot.distance_value is not None else None
        active_guard_distance = route_guard_distance if route_anchor is not None else home_guard_distance
        active_finish_distance = route_finish_distance if route_anchor is not None else home_finish_distance
        gather_density_radius = self.profile.thresholds.get('gather_density_distance_px', 92.0)
        gather_density_count = self._count_enemies_within_radius(snapshot.minimap_enemies, gather_density_radius)
        if guard_distance is not None and guard_distance > active_guard_distance:
            self.current_target = None
            self.navigation.clear_active_target()
            self.navigation.stop_motion()
            if route_anchor is not None and snapshot.world_x is not None and (snapshot.world_z is not None):
                arrived = self.compass.update_route_target(snapshot=snapshot, profile=self.profile, target_x=route_anchor[0], target_z=route_anchor[1])
                self.status = f'gather-route-guard-d{guard_distance:.0f}'
            else:
                arrived = self.compass.update_home(snapshot, self.profile)
                self.status = f'gather-home-start-d{guard_distance:.0f}'
            if arrived:
                self.compass.stop()
                self.phase_started_at = time.monotonic()
                self.gather_collected_nodes = 0
                self.gather_dense_frames = 0
                self.gather_wait_started_at = 0.0
                self.gather_plan_locked = False
                self.gather_plan_frames = 0
            return None
        else:
            finish_reason = None
            if self.gather_collected_nodes >= gather_goal_count:
                finish_reason = 'gather-goal-reached'
            else:
                if elapsed >= gather_limit:
                    finish_reason = 'gather-time-limit'
            if finish_reason is not None:
                self.current_target = None
                self.navigation.clear_active_target()
                if guard_distance is not None and guard_distance > active_finish_distance:
                    if route_anchor is not None and snapshot.world_x is not None and (snapshot.world_z is not None):
                        arrived = self.compass.update_route_target(snapshot=snapshot, profile=self.profile, target_x=route_anchor[0], target_z=route_anchor[1])
                        self.status = f'gather-route-finish-d{guard_distance:.0f}'
                    else:
                        arrived = self.compass.update_home(snapshot, self.profile)
                        self.status = f'gather-home-finish-d{guard_distance:.0f}'
                    if arrived:
                        self.compass.stop()
                        self._transition(BotPhase.PACK, finish_reason)
                    return None
                else:
                    self.navigation.stop_motion()
                    self._transition(BotPhase.PACK, finish_reason)
                    return None
            else:
                self.current_target = self.navigation.choose_target(snapshot, self.profile, self.current_target)
                route_done, route_total = self.navigation.route_progress()
                route_suffix = f'-r{route_done}/{route_total}' if route_total > 0 else ''
                has_memory_targets = self.navigation.has_memory_targets()
                if not self.gather_plan_locked:
                    self.gather_plan_frames += 1
                    plan_window_s = float(self.profile.timeouts.get('gather_plan_window_seconds', 0.9))
                    plan_ready = elapsed >= plan_window_s or (route_total > 0 and self.gather_plan_frames >= 4) or (has_memory_targets and self.gather_plan_frames >= 6)
                    self.navigation.stop_motion()
                    self.status = f'gather-plan-{self.gather_plan_frames}{route_suffix}'
                    if not plan_ready:
                        return None
                    else:
                        self.gather_plan_locked = True
                if self.current_target is not None or snapshot.minimap_enemies or has_memory_targets:
                    self.gather_wait_started_at = 0.0
                if self.current_target is None:
                    if snapshot.minimap_enemies or has_memory_targets:
                        self.gather_no_target_frames = 0
                    else:
                        self.gather_no_target_frames += 1
                    if guard_distance is not None and guard_distance > active_guard_distance:
                        self.navigation.clear_active_target()
                        if route_anchor is not None and snapshot.world_x is not None and (snapshot.world_z is not None):
                            arrived = self.compass.update_route_target(snapshot=snapshot, profile=self.profile, target_x=route_anchor[0], target_z=route_anchor[1])
                            self.status = f'gather-route-d{guard_distance:.0f}'
                        else:
                            arrived = self.compass.update_home(snapshot, self.profile)
                            self.status = f'gather-home-d{guard_distance:.0f}'
                        if arrived:
                            self.compass.stop()
                            self.gather_wait_started_at = 0.0
                        return None
                    else:
                        if not snapshot.minimap_enemies and (not has_memory_targets):
                            self.navigation.stop_motion()
                            if self.gather_wait_started_at <= 0.0:
                                self.gather_wait_started_at = time.monotonic()
                            waited = time.monotonic() - self.gather_wait_started_at
                            remaining = max(0.0, respawn_wait_s - waited)
                            self.status = f'gather-wait-{remaining:.1f}s'
                            if waited >= respawn_wait_s:
                                self._transition(BotPhase.PACK, 'gather-empty')
                            return None
                        else:
                            self.navigation.search_for_targets(snapshot, self.profile)
                            self.status = f'gather-search-{self.gather_no_target_frames}{route_suffix}'
                            return None
                else:
                    self.gather_no_target_frames = 0
                    move_status, stuck = self.navigation.update_gather(self.current_target, snapshot, self.profile)
                    reached_count = self.navigation.consume_reached_count()
                    if reached_count > 0:
                        self.gather_collected_nodes += reached_count
                        self.current_target = None
                    target_distance = self.navigation.target_distance(self.current_target, self.profile)
                    if target_distance is not None:
                        self.status = f'gather-{move_status}{route_suffix}-d{target_distance:.0f}-n{gather_density_count}-c{self.gather_collected_nodes}'
                    else:
                        self.status = f'gather-{move_status}{route_suffix}-n{gather_density_count}-c{self.gather_collected_nodes}'
                    if stuck:
                        self.navigation.anti_stuck(self.profile)
                        self.status = f'gather-antistuck{route_suffix}'
    def _tick_pack(self, snapshot: VisionSnapshot) -> None:
        elapsed = time.monotonic() - self.phase_started_at
        self.navigation.update_pack(snapshot, self.profile)
        self.status = f'pack-{elapsed:.1f}s'
        if elapsed >= self.profile.timeouts.get('pack_seconds', 7.0):
            self.navigation.stop_motion()
            self._transition(BotPhase.COMBAT, 'pack-finished')
    def _tick_combat(self, snapshot: VisionSnapshot) -> None:
        # ***<module>.BotStateMachine._tick_combat: Failure: Different control flow
        now = time.monotonic()
        minimap_enabled = self.combat.minimap_support_enabled(self.profile)
        level_only = self.combat.level_only_targeting_enabled(self.profile)
        screen_contact = self.combat.current_screen_contact(snapshot, self.profile)
        confirmed = self.combat.update(snapshot, self.profile, self.auto_attack_enabled)
        actionable_presence = confirmed or self.combat.has_actionable_presence(snapshot, self.profile)
        visible_screen_enemy = self.combat.has_visible_screen_enemy(snapshot, self.profile)
        enemy_presence = self.combat.has_enemy_presence(snapshot, self.profile)
        search_window_s = float(self.profile.timeouts.get('combat_search_only_window_seconds', 4.0))
        post_attack_search_s = float(self.profile.timeouts.get('combat_post_attack_search_window_seconds', search_window_s))
        post_skill_2_search_s = float(self.profile.timeouts.get('combat_post_skill_2_search_window_seconds', post_attack_search_s))
        recent_actionable_at = self.combat.last_actionable_presence_time
        recent_actionable = recent_actionable_at > 0.0 and now - recent_actionable_at <= search_window_s
        recent_attack_stop = self.combat.last_attack_stop_time > 0.0 and now - self.combat.last_attack_stop_time <= post_attack_search_s
        recent_skill_2 = self.combat.last_skill_2_turn_time > 0.0 and now - self.combat.last_skill_2_turn_time <= post_skill_2_search_s
        initial_search_window = now - self.phase_started_at <= search_window_s
        strong_presence = actionable_presence or visible_screen_enemy or (enemy_presence and (recent_actionable or recent_attack_stop or recent_skill_2 or initial_search_window))
        cleanup_presence = self.combat.has_cleanup_presence(snapshot, self.profile)
        if actionable_presence:
            self.combat.note_enemy_presence(actionable=True)
        if confirmed:
            active_refine = False
            if level_only and (snapshot.enemy_level_targets or snapshot.enemy_hp_targets or snapshot.enemy_nn_targets):
                    active_refine = self.combat.try_acquire_target(snapshot, self.profile, allow_hard_lock=True)
            behind_hint = self.combat.should_turn_behind_target(snapshot, self.profile)
            engaged_needs_reacquire = not screen_contact and (behind_hint or self.combat.should_reacquire_while_engaged(snapshot, self.profile) or self.combat.has_enemy_presence(snapshot, self.profile))
            if engaged_needs_reacquire:
                if behind_hint and self.combat.try_turn_behind_target(snapshot, self.profile):
                    self.status = 'combat-behind-turn'
                    return None
                else:
                    reacquired = self.combat.try_acquire_target(snapshot, self.profile)
                    self.status = 'combat-engaged-reacquire' if reacquired else 'combat-engaged-hold'
            else:
                if active_refine:
                    self.status = 'combat-engaged-aim'
                else:
                    self.status = 'combat-engaged'
            return None
        else:
            if strong_presence:
                behind_hint = self.combat.should_turn_behind_target(snapshot, self.profile)
                direct_hint = bool(snapshot.enemy_level_targets or snapshot.enemy_nn_targets or snapshot.enemy_back_target) if level_only else bool(snapshot.target_locked or snapshot.enemy_level_targets or snapshot.enemy_nn_targets or snapshot.enemy_back_target or snapshot.hp_present or snapshot.name_present or snapshot.enemy_body_targets or snapshot.enemy_hp_targets)
                minimap_hint = minimap_enabled and bool(snapshot.minimap_enemies)
                if behind_hint and self.combat.try_turn_behind_target(snapshot, self.profile):
                    self.status = 'combat-behind-turn'
                    return None
                else:
                    self.combat.try_acquire_target(snapshot, self.profile)
                    if behind_hint:
                        self.status = 'combat-behind-turn'
                    else:
                        if direct_hint:
                            self.status = 'combat-acquire'
                        else:
                            if minimap_hint:
                                self.status = 'combat-minimap-reacquire'
                            else:
                                self.status = 'combat-search'
                    return None
            else:
                if cleanup_presence and self.combat.should_respect_cleanup_presence(self.profile):
                    if visible_screen_enemy:
                        behind_hint = self.combat.should_turn_behind_target(snapshot, self.profile)
                        if behind_hint and self.combat.try_turn_behind_target(snapshot, self.profile):
                            self.status = 'combat-behind-turn'
                            return None
                        else:
                            reacquired = self.combat.try_acquire_target(snapshot, self.profile)
                            self.status = 'combat-cleanup-reacquire' if reacquired else 'combat-cleanup-visible'
                            return None
                    else:
                        followed = minimap_enabled and self.combat.try_follow_last_minimap_direction(self.profile)
                        if followed:
                            self.status = 'combat-cleanup-follow'
                        else:
                            self.status = 'combat-cleanup-hold'
                        return None
                else:
                    if self.combat.should_hold_finish(self.profile):
                        followed = minimap_enabled and self.combat.try_follow_last_minimap_direction(self.profile)
                        if followed:
                            self.status = 'combat-finish-follow'
                            return None
                        else:
                            if minimap_enabled and self.combat.has_recent_minimap_direction(self.profile):
                                self.status = 'combat-finish-track'
                                return None
                            else:
                                scanned = self.combat.try_scan_next(self.profile)
                                self.status = 'combat-finish-hold-scan' if scanned else 'combat-finish-hold'
                    else:
                        self.status = 'combat-search'
                        if self.combat.enemies_absent_stable(snapshot, self.profile):
                            scanned = self.combat.try_scan_next(self.profile)
                            if scanned or self.combat.ready_to_clear(snapshot, self.profile):
                                    self._transition(BotPhase.INVENTORY_RETURN, 'combat-cleared')
    def _tick_inventory_return(self, snapshot: VisionSnapshot) -> None:
        if not self.inventory_checked:
            self.last_inventory_result = self.inventory.check(capture=self.capture, vision=self.vision, profile=self.profile, stop_event=self.stop_event)
            self.inventory_checked = True
            if not self.last_inventory_result.full_signal and self._has_high_density(snapshot.minimap_enemies):
                self._transition(BotPhase.GATHER, 'density-high-restart')
                return None
        inventory_full = self.last_inventory_result is not None and self.last_inventory_result.full_signal
        safe_teleport_point = self.profile.get_inventory_safe_teleport_point() if inventory_full else None
        route = self.profile.get_active_go_to_farm_route()
        return_target = safe_teleport_point or (route[(-1)] if route else None)
        return_target_label = 'safe-teleport' if safe_teleport_point is not None else 'route'
        if return_target is not None:
            route_target = return_target
            target_x, _target_y, target_z = route_target
            self.status = f'returning-{return_target_label} ({int(target_x)},{int(target_z)})'
            now = time.monotonic()
            if snapshot.world_x is None or snapshot.world_z is None:
                stable_world = self._read_stable_return_world_coords()
                if stable_world is not None:
                    snapshot.world_x, snapshot.world_y, snapshot.world_z = stable_world
                    self.return_cached_world_coords = stable_world
                    self.return_cached_world_at = now
                else:
                    if self.return_cached_world_coords is not None and now - self.return_cached_world_at <= 1.2:
                            cached_x, cached_y, cached_z = self.return_cached_world_coords
                            snapshot.world_x = cached_x
                            snapshot.world_y = cached_y
                            snapshot.world_z = cached_z
            if snapshot.world_x is None or snapshot.world_z is None:
                if now - self.return_last_log_at >= 2.0:
                    self.logger.info('Inventory return %s: coords missing target=(%s,%s) heading_conf=%.3f', return_target_label, int(target_x), int(target_z), float(snapshot.minimap_heading_confidence))
                    self.return_last_log_at = now
                self.compass.stop()
                self.navigation.stop_motion()
                self.input.safe_release_all()
                return None
            else:
                self.return_cached_world_coords = (int(snapshot.world_x), None if snapshot.world_y is None else int(snapshot.world_y), int(snapshot.world_z))
                self.return_cached_world_at = now
                dx = int(target_x) - int(snapshot.world_x)
                dz = int(target_z) - int(snapshot.world_z)
                distance = math.hypot(float(dx), float(dz))
                if now - self.return_last_log_at >= 2.0:
                    self.logger.info('Inventory return %s: coords=(%s,%s) target=(%s,%s) dx=%s dz=%s distance=%.1f heading_conf=%.3f', return_target_label, int(snapshot.world_x), int(snapshot.world_z), int(target_x), int(target_z), dx, dz, distance, float(snapshot.minimap_heading_confidence))
                    self.return_last_log_at = now
                elapsed = time.monotonic() - self.phase_started_at
                if elapsed >= self.profile.timeouts.get('return_timeout_seconds', 45.0):
                    self.logger.warning('Return timeout reached')
                    self.compass.stop()
                    self.navigation.stop_motion()
                    self.input.safe_release_all()
                    self._transition(BotPhase.GATHER, 'return-timeout')
                    return None
                else:
                    arrived = self.compass.update_route_target(snapshot=snapshot, profile=self.profile, target_x=int(target_x), target_z=int(target_z))
                    if arrived:
                        self.compass.stop()
                        self.navigation.stop_motion()
                        self.input.safe_release_all()
                        if inventory_full:
                            serviced = self._run_full_inventory_service_cycle()
                            if serviced:
                                self._transition(BotPhase.GATHER, 'sold-and-returned')
                            else:
                                self.phase = BotPhase.ERROR
                                self.status = 'inventory-service-failed'
                                self.logger.warning('Inventory full service cycle failed; stopping bot for safety')
                                self.stop_event.set()
                            return None
                        else:
                            self._transition(BotPhase.GATHER, f'arrived-near-{return_target_label}')
                    return None
        else:
            if inventory_full:
                serviced = self._run_full_inventory_service_cycle()
                if serviced:
                    self._transition(BotPhase.GATHER, 'sold-and-returned')
                else:
                    self.phase = BotPhase.ERROR
                    self.status = 'inventory-service-failed'
                    self.logger.warning('Inventory full service cycle failed without active route; stopping bot for safety')
                    self.stop_event.set()
                return None
            else:
                elapsed = time.monotonic() - self.phase_started_at
                if elapsed >= self.profile.timeouts.get('return_timeout_seconds', 45.0):
                    self.logger.warning('Return timeout reached')
                    self._transition(BotPhase.GATHER, 'return-timeout')
                    return None
                else:
                    arrived = self.compass.update(snapshot, self.profile)
                    self.status = 'returning-marker'
                    if arrived:
                        self.compass.stop()
                        self.navigation.stop_motion()
                        self.input.safe_release_all()
                        self._transition(BotPhase.GATHER, 'arrived-near-marker')
    def tick(self) -> dict:
        now = time.monotonic()
        if self._try_handle_death_recovery():
            snapshot = self._build_tick_snapshot()
            debug_model = self.vision.build_debug_model(profile=self.profile, phase_name=self.phase.name, status=self.status, snapshot=snapshot, current_target=self.current_target, route_points=self.navigation.route_debug_points(self.profile), route_active_index=self.navigation.route_index if self.navigation.has_route() else None, route_terminal=self.navigation.route_debug_terminal(self.profile), route_weights=self.navigation.route_debug_weights())
            self._maybe_log_perf(time.monotonic())
            return debug_model
        else:
            snapshot = self._build_tick_snapshot()
            if self.phase == BotPhase.GATHER:
                self._tick_gather(snapshot)
            else:
                if self.phase == BotPhase.PACK:
                    self._tick_pack(snapshot)
                else:
                    if self.phase == BotPhase.COMBAT:
                        self._tick_combat(snapshot)
                    else:
                        if self.phase == BotPhase.INVENTORY_RETURN:
                            self._tick_inventory_return(snapshot)
            debug_model = self.vision.build_debug_model(profile=self.profile, phase_name=self.phase.name, status=self.status, snapshot=snapshot, current_target=self.current_target, route_points=self.navigation.route_debug_points(self.profile), route_active_index=self.navigation.route_index if self.navigation.has_route() else None, route_terminal=self.navigation.route_debug_terminal(self.profile), route_weights=self.navigation.route_debug_weights())
            self._maybe_log_perf(now)
            return debug_model