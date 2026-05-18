# Source Generated with Decompyle++
# File: state_machine.pyc (Python 3.11)

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
    
    def __init__(self, capture, vision, input_controller, profile, config, stop_event, auto_attack_enabled = None, fast_minimap_tracker = None, fast_level_tracker = None, combat_coord_tracker = (True, None, None, None, None), gather_telemetry_tracker = ('capture', 'ScreenCapture', 'vision', 'VisionEngine', 'input_controller', 'InputController', 'profile', 'CalibrationProfile', 'config', 'AppConfig', 'stop_event', 'Event', 'auto_attack_enabled', 'bool', 'fast_minimap_tracker', 'MinimapFastTracker | None', 'fast_level_tracker', 'LevelFastTracker | None', 'combat_coord_tracker', 'CombatCoordTracker | None', 'gather_telemetry_tracker', 'GatherTelemetryTracker | None', 'return', 'None')):
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
        self.gather_wait_started_at = 0
        self.gather_plan_locked = False
        self.gather_plan_frames = 0
        self.inventory_checked = False
        self.last_inventory_result = None
        self.return_arrival_started_at = 0
        self.return_last_log_at = 0
        self.return_cached_world_coords = None
        self.return_cached_world_at = 0
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0
        self.gather_resume_after_arrival_at = 0
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._last_combat_coord_age_ms = None
        self._perf_last_log_at = 0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0
        self._last_death_check_at = 0

    
    def start(self = None):
        self._transition(BotPhase.GATHER, 'start')

    
    def stop(self = None):
        self.status = 'stopping'
        self.combat.stop(self.profile)
        self.navigation.stop_motion()
        self.compass.stop()
        self.input.safe_release_all()
        self.phase = BotPhase.IDLE
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._last_combat_coord_age_ms = None
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0
        self._perf_last_log_at = 0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0
        self._last_death_check_at = 0
        self.logger.info('Bot stopped safely')

    
    def _transition(self = None, phase = None, reason = None):
        self.logger.info('Transition: %s -> %s (%s)', self.phase.name, phase.name, reason)
        self.phase = phase
        self.phase_started_at = time.monotonic()
        self.status = reason
        self.current_target = None
        self.gather_no_target_frames = 0
        self.gather_dense_frames = 0
        self.gather_collected_nodes = 0
        self.gather_wait_started_at = 0
        self.gather_plan_locked = False
        self.gather_plan_frames = 0
        self.return_arrival_started_at = 0
        self.return_last_log_at = 0
        self.return_cached_world_coords = None
        self.return_cached_world_at = 0
        self.gather_cached_world_coords = None
        self.gather_cached_world_at = 0
        self.gather_resume_after_arrival_at = 0
        self._last_full_snapshot = None
        self._last_full_snapshot_at = 0
        self._last_fast_minimap_age_ms = None
        self._last_fast_level_age_ms = None
        self._perf_last_log_at = 0
        self._perf_control_ticks = 0
        self._perf_full_vision_updates = 0
        self._perf_full_vision_ms_sum = 0
        self._last_death_check_at = 0
        if phase == BotPhase.GATHER:
            self.navigation.reset()
            self.combat.reset(self.profile)
            self.compass.reset()
            self.inventory_checked = False
            self.last_inventory_result = None
            if reason in frozenset({'arrived-near-route', 'arrived', 'arrived-near-marker'}):
                settle_s = float(self.profile.timeouts.get('return_arrival_stop_seconds', 0.75))
                if settle_s > 0:
                    self.gather_resume_after_arrival_at = time.monotonic() + settle_s
                    return None
                return None
            return None
        if None == BotPhase.PACK:
            self.combat.stop(self.profile)
            return None
        if None == BotPhase.COMBAT:
            self.combat.reset(self.profile)
            self.navigation.stop_motion()
            return None
        if None == BotPhase.INVENTORY_RETURN:
            self.combat.stop(self.profile)
            self.navigation.stop_motion()
            self.compass.reset()
            self.inventory_checked = False
            self.return_last_log_at = 0
            self.return_cached_world_coords = None
            self.return_cached_world_at = 0
            return None

    
    def _read_stable_return_world_coords(self = None):
        samples = []
    # WARNING: Decompyle incomplete

    
    def _gather_route_anchor(self = None):
        route = self.profile.get_active_go_to_farm_route()
        if not route:
            return None
        (target_x, _target_y, target_z) = None[-1]
        return (int(target_x), int(target_z))

    
    def _hydrate_gather_world_coords(self = None, snapshot = None):
        now = time.monotonic()
    # WARNING: Decompyle incomplete

    
    def _gather_route_anchor_distance(self = None, snapshot = None):
        self._hydrate_gather_world_coords(snapshot)
        anchor = self._gather_route_anchor()
    # WARNING: Decompyle incomplete

    
    def _run_full_inventory_service_cycle(self = None):
