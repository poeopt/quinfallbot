# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\bot\\worker.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import logging
import math
import statistics
import threading
import time
from PySide6.QtCore import QObject, Signal
from mmobot.auth import RuntimeAccessController, RuntimeAccessError
from mmobot.bot.go_to_farm_controller import GoToFarmController
from mmobot.bot.combat_coord_tracker import CombatCoordTracker
from mmobot.bot.gather_telemetry_tracker import GatherTelemetryTracker
from mmobot.bot.level_fast_tracker import LevelFastTracker
from mmobot.bot.minimap_fast_tracker import MinimapFastTracker
from mmobot.bot.state_machine import BotStateMachine
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.input.game_window import GameWindowManager
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine
class BotWorker(QObject):
    debug_model_ready = Signal(object)
    status_changed = Signal(str)
    running_changed = Signal(bool)
    error = Signal(str)
    def __init__(self, config: AppConfig, profile: CalibrationProfile, auto_attack_enabled: bool, run_startup_go_to_farm_precheck: bool=False, access_controller: RuntimeAccessController | None=None) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.profile = profile
        self.auto_attack_enabled = auto_attack_enabled
        self.run_startup_go_to_farm_precheck = run_startup_go_to_farm_precheck
        self.access_controller = access_controller
        self._thread = None
        self._stop_event = threading.Event()
        self._state_machine = None
        self._emergency_input = InputController(access_controller=access_controller)
    def _startup_go_to_farm_target(self) -> tuple[int, int] | None:
        route = self.profile.get_active_go_to_farm_route()
        if route:
            last_x, _last_y, last_z = route[(-1)]
            return (int(last_x), int(last_z))
        else:
            target_x = self.profile.thresholds.get('go_to_farm_target_x')
            target_z = self.profile.thresholds.get('go_to_farm_target_z')
            if target_x is None or target_z is None:
                return None
            else:
                return (int(round(float(target_x))), int(round(float(target_z))))
    def _read_startup_world_coords(self, capture: ScreenCapture, vision: VisionEngine) -> tuple[int, int] | None:
        samples = []
        for _ in range(5):
            if self._stop_event.is_set():
                return
            else:
                frame = capture.grab_bgr()
                world_x, _world_y, world_z = vision.read_minimap_coordinates(frame, self.profile)
                if world_x is not None and world_z is not None:
                        samples.append((int(world_x), int(world_z)))
                        if len(samples) >= 3:
                            break
                time.sleep(0.06)
        if not samples:
            return None
        else:
            xs = [sample[0] for sample in samples]
            zs = [sample[1] for sample in samples]
            return (int(round(statistics.median(xs))), int(round(statistics.median(zs))))
    def _maybe_run_startup_go_to_farm_precheck(self, capture: ScreenCapture, vision: VisionEngine, input_controller: InputController, window_manager: GameWindowManager) -> bool:
        if not self.run_startup_go_to_farm_precheck:
            return True
        else:
            target = self._startup_go_to_farm_target()
            if target is None:
                self.logger.info('Startup Go To Farm precheck skipped: no final route target')
                return True
            else:
                threshold = float(self.profile.thresholds.get('auto_attack_go_to_farm_precheck_distance_units', 120.0))
                self.status_changed.emit('startup precheck: reading farm distance')
                window_manager.focus_game_window('startup-go-to-farm-precheck')
                coords = self._read_startup_world_coords(capture, vision)
                should_run = True
                if coords is not None:
                    distance = math.hypot(coords[0] - target[0], coords[1] - target[1])
                    self.logger.info('Startup Go To Farm precheck: coords=(%s,%s) target=(%s,%s) distance=%.1f threshold=%.1f', coords[0], coords[1], target[0], target[1], distance, threshold)
                    if distance <= threshold:
                        should_run = False
                        self.status_changed.emit(f'startup precheck: already near farm ({distance:.0f})')
                else:
                    self.logger.info('Startup Go To Farm precheck: coordinates unavailable, running Go To Farm conservatively')
                if not should_run:
                    return True
                else:
                    self.status_changed.emit('startup precheck: running Go To Farm')
                    controller = GoToFarmController(capture, vision, input_controller, self.config)
                    success = controller.go_to_farm(self.profile, self._stop_event)
                    if success:
                        self.status_changed.emit('startup precheck: arrived at farm')
                        input_controller.safe_release_all()
                        return True
                    else:
                        if self._stop_event.is_set():
                            self.logger.info('Startup Go To Farm precheck interrupted by stop request')
                            return False
                        else:
                            self.logger.error('Startup Go To Farm precheck failed')
                            self.error.emit('Startup Go To Farm precheck failed')
                            return False
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
                return None
        if self.access_controller is not None:
            self.access_controller.ensure_runtime_allowed()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name='BotWorker', daemon=True)
        self._thread.start()
        self.running_changed.emit(True)
    def _force_release_inputs(self) -> None:
        try:
            self._emergency_input.safe_release_all()
        except Exception:
            self.logger.exception('Emergency input release failed')
    def stop(self, hard: bool=False) -> None:
        self._stop_event.set()
        if hard:
            self._force_release_inputs()
        if self._state_machine is not None:
            try:
                self._state_machine.stop()
            except Exception:
                self.logger.exception('Failed to stop state machine safely')
        else:
            if hard:
                self._force_release_inputs()
        if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5 if hard else 3.0)
                if self._thread.is_alive():
                    self.logger.warning('Bot worker thread is still alive after stop request')
        if hard:
            self._force_release_inputs()
        self.running_changed.emit(False)
    def _run(self) -> None:
        # irreducible cflow, using cdg fallback
        # ***<module>.BotWorker._run: Failure: Compilation Error
        capture = None
        fast_minimap_tracker = None
        fast_level_tracker = None
        combat_coord_tracker = None
        gather_telemetry_tracker = None
        if self.access_controller is not None:
            self.access_controller.ensure_runtime_allowed()
        capture = ScreenCapture()
        input_controller = InputController(access_controller=self.access_controller)
        window_manager = GameWindowManager(self.config)
        window_manager.focus_game_window('worker-start')
        vision = VisionEngine(self.config.tesseract_cmd)
        fast_minimap_tracker = MinimapFastTracker(self.config, self.profile)
        fast_minimap_tracker.start()
        fast_level_tracker = LevelFastTracker(self.config, self.profile)
        fast_level_tracker.start()
        combat_coord_tracker = CombatCoordTracker(self.config, self.profile)
        combat_coord_tracker.start()
        gather_telemetry_tracker = GatherTelemetryTracker(self.config, self.profile)
        gather_telemetry_tracker.start()
        if not self._maybe_run_startup_go_to_farm_precheck(capture, vision, input_controller, window_manager):
            return
            if fast_minimap_tracker is not None:
                fast_minimap_tracker.stop()
            if fast_level_tracker is not None:
                fast_level_tracker.stop()
            if combat_coord_tracker is not None:
                combat_coord_tracker.stop()
            if gather_telemetry_tracker is not None:
                gather_telemetry_tracker.stop()
            if capture is not None:
                capture.close()
            self.running_changed.emit(False)
            if self._stop_event.is_set():
                return None
                if capture is not None:
                    capture.close()
                self.running_changed.emit(False)
                window_manager.focus_game_window('worker-start')
                input_controller.safe_release_all()
                self._state_machine = BotStateMachine(capture=capture, vision=vision, input_controller=input_controller, profile=self.profile, config=self.config, stop_event=self._stop_event, auto_attack_enabled=self.auto_attack_enabled, fast_minimap_tracker=fast_minimap_tracker, fast_level_tracker=fast_level_tracker, combat_coord_tracker=combat_coord_tracker, gather_telemetry_tracker=gather_telemetry_tracker)
                self._state_machine.start()
                self.status_changed.emit('running')
                tick_s = self.config.worker_tick_ms / 1000.0
                while not self._stop_event.is_set():
                    if self.access_controller is not None:
                        self.access_controller.ensure_runtime_allowed()
                    debug_model = self._state_machine.tick()
                    self.debug_model_ready.emit(debug_model)
                    self.status_changed.emit(f'{self._state_machine.phase.name} | {self._state_machine.status}')
                    time.sleep(tick_s)
                except RuntimeAccessError as exc:
                        self.logger.warning('Runtime access revoked while bot was running: %s', exc)
                        self.error.emit(str(exc))
                    except Exception as exc:
                            logging.getLogger(self.__class__.__name__).exception('Bot worker crashed')
                            self.error.emit(str(exc))
                            if self._state_machine is not None:
                                try:
                                    self._state_machine.stop()
                                except Exception:
                                    self.logger.exception('Safe stop after crash failed')
                                if fast_minimap_tracker is not None:
                                    fast_minimap_tracker.stop()
                                if fast_level_tracker is not None:
                                    fast_level_tracker.stop()
                                if combat_coord_tracker is not None:
                                    combat_coord_tracker.stop()
                                if gather_telemetry_tracker is not None:
                                    gather_telemetry_tracker.stop()
                                if capture is not None:
                                    capture.close()
                                self.running_changed.emit(False)