# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\input\\manual_action_recorder.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import ctypes
import json
import logging
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import win32con
from PySide6.QtCore import QObject, Signal
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine
user32 = ctypes.windll.user32
@dataclass(slots=True)
class RecordedSession:
    started_at_iso: str
    duration_ms: int
    event_count: int
    telemetry_count: int
    output_path: Path
class ManualActionRecorder(QObject):
    recording_changed = Signal(bool, str)
    session_saved = Signal(str)
    error = Signal(str)
    KEY_MAP = {'W': ord('W'), 'A': ord('A'), 'S': ord('S'), 'D': ord('D'), 'SHIFT': win32con.VK_SHIFT, 'SPACE': win32con.VK_SPACE, 'Q': ord('Q'), 'E': ord('E'), 'R': ord('R'), 'F': ord('F'), '1': ord('1'), '2': ord('2'), '3': ord('3'), '4': ord('4'), '5': ord('5'), '6': ord('6'), 'I': ord('I')}
    BUTTON_MAP = {'left': win32con.VK_LBUTTON, 'right': win32con.VK_RBUTTON}
    class POINT(ctypes.Structure):
        _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self._stop_event = threading.Event()
        self._thread = None
        self._session = None
        self._events = []
        self._telemetry = []
        self._started_at_monotonic = 0.0
        self._started_at_iso = ''
        self._profile = None
        self._key_states = {name: False for name in self.KEY_MAP}
        self._button_states = {name: False for name in self.BUTTON_MAP}
        self._last_cursor = None
    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    def toggle(self) -> None:
        if self.is_recording:
            self.stop()
        else:
            self.start()
    def start(self, profile: CalibrationProfile | None=None) -> None:
        if self.is_recording:
            return None
        else:
            self._events = []
            self._telemetry = []
            self._session = None
            self._profile = profile
            self._started_at_monotonic = time.monotonic()
            self._started_at_iso = datetime.now().isoformat(timespec='seconds')
            self._reset_states()
            self._last_cursor = self._get_cursor_position()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name='ManualActionRecorder', daemon=True)
            self._thread.start()
            self.recording_changed.emit(True, '')
            self.logger.info('Manual action recording started')
    def stop(self) -> None:
        if not self.is_recording:
            return None
        else:
            self._stop_event.set()
            if self._thread is not None and self._thread.is_alive():
                    self._thread.join(timeout=2.5)
            if self._session is not None:
                self.session_saved.emit(str(self._session.output_path))
                self.recording_changed.emit(False, str(self._session.output_path))
                self.logger.info('Manual action recording saved: %s (%s events, %s telemetry)', self._session.output_path, self._session.event_count, self._session.telemetry_count)
            else:
                self.recording_changed.emit(False, '')
            self._thread = None
    def _run(self) -> None:
        capture = None
        vision = None
        try:
            poll_s = max(0.01, self.config.manual_record_sample_ms / 1000.0)
            vision_poll_s = max(0.05, self.config.manual_record_vision_sample_ms / 1000.0)
            next_vision_poll = time.monotonic()
            if self._profile is not None:
                capture = ScreenCapture()
                vision = VisionEngine(self.config.tesseract_cmd)
            while not self._stop_event.is_set():
                self._poll_keys()
                self._poll_buttons()
                self._poll_mouse()
                if capture is not None and vision is not None and (self._profile is not None):
                            now = time.monotonic()
                            if now >= next_vision_poll:
                                self._poll_vision(capture, vision, self._profile)
                                next_vision_poll = now + vision_poll_s
                time.sleep(poll_s)
            self._session = self._save_session()
        except Exception as exc:
            self.logger.exception('Manual action recording failed')
            self.error.emit(str(exc))
        finally:
            if capture is not None:
                try:
                    capture.close()
                except Exception:
                    self.logger.exception('Failed to close manual record capture')
    def _reset_states(self) -> None:
        self._key_states = {name: self._is_pressed(vk) for name, vk in self.KEY_MAP.items()}
        self._button_states = {name: self._is_pressed(vk) for name, vk in self.BUTTON_MAP.items()}
    def _append_event(self, event_type: str, **payload: object) -> None:
        timestamp_ms = int((time.monotonic() - self._started_at_monotonic) * 1000.0)
        event = {'t_ms': timestamp_ms, 'type': event_type}
        event.update(payload)
        self._events.append(event)
    @staticmethod
    def _is_pressed(vk: int) -> bool:
        return bool(user32.GetAsyncKeyState(vk) & 32768)
    def _get_cursor_position(self) -> tuple[int, int]:
        point = self.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return (0, 0)
        else:
            return (point.x, point.y)
    def _poll_keys(self) -> None:
        for name, vk in self.KEY_MAP.items():
            current = self._is_pressed(vk)
            previous = self._key_states[name]
            if current == previous:
                continue
            else:
                self._key_states[name] = current
                self._append_event('key_down' if current else 'key_up', key=name)
    def _poll_buttons(self) -> None:
        for name, vk in self.BUTTON_MAP.items():
            current = self._is_pressed(vk)
            previous = self._button_states[name]
            if current == previous:
                continue
            else:
                self._button_states[name] = current
                self._append_event('mouse_down' if current else 'mouse_up', button=name)
    def _poll_mouse(self) -> None:
        current = self._get_cursor_position()
        if self._last_cursor is None:
            self._last_cursor = current
            return None
        else:
            dx = current[0] - self._last_cursor[0]
            dy = current[1] - self._last_cursor[1]
            self._last_cursor = current
            if dx == 0 and dy == 0:
                    return None
            self._append_event('mouse_move', dx=dx, dy=dy, x=current[0], y=current[1])
    def _append_telemetry(self, payload: dict[str, object]) -> None:
        timestamp_ms = int((time.monotonic() - self._started_at_monotonic) * 1000.0)
        entry = {'t_ms': timestamp_ms}
        entry.update(payload)
        self._telemetry.append(entry)
    def _poll_vision(self, capture: ScreenCapture, vision: VisionEngine, profile: CalibrationProfile) -> None:
        # ***<module>.ManualActionRecorder._poll_vision: Failure: Different bytecode
        frame = capture.grab_bgr()
        snapshot = vision.analyze(frame, profile, include_distance=True, include_world_coords=True, include_inventory=False)
        minimap_center_spec = profile.points.get('minimap_center')
        minimap_center = minimap_center_spec.as_pixels(profile.screen_size) if minimap_center_spec else None
        compass_center_spec = profile.points.get('compass_center')
        compass_center = compass_center_spec.as_pixels(profile.screen_size) if compass_center_spec else None
        enemy_rel = []
        if minimap_center is not None:
            for enemy in snapshot.minimap_enemies:
                enemy_rel.append([enemy[0] - minimap_center[0], enemy[1] - minimap_center[1]])
        heading_tip_rel = None
        if snapshot.minimap_heading_tip is not None and minimap_center is not None:
                heading_tip_rel = [snapshot.minimap_heading_tip[0] - minimap_center[0], snapshot.minimap_heading_tip[1] - minimap_center[1]]
        heading_vector = None
        if snapshot.minimap_heading_vector is not None:
            heading_vector = [round(float(snapshot.minimap_heading_vector[0]), 4), round(float(snapshot.minimap_heading_vector[1]), 4)]
        heading_sector = VisionEngine._vector_to_cardinal(snapshot.minimap_heading_vector)
        compass_offset_x = None
        if snapshot.compass_marker is not None and compass_center is not None:
                compass_offset_x = int(snapshot.compass_marker[0] - compass_center[0])
        self._append_telemetry({'enemy_count': len(snapshot.minimap_enemies), 'nearby_enemy_count': int(snapshot.nearby_enemy_count), 'nearest_enemy_distance_px': None if snapshot.nearest_enemy_distance is None else round(float(snapshot.nearest_enemy_distance), 1), 'minimap_enemies_rel': enemy_rel, 'heading_vector': heading_vector, 'heading_tip_rel': heading_tip_rel, 'heading_sector': heading_sector, 'heading_confidence': snapshot.heading_confidence, 'world_z': snapshot.world_z, 'compass_offset_x': None if snapshot.stamina_ratio is None else round(float(snapshot.stamina_ratio), 3), 'target_locked': bool(snapshot.target_locked), 'hp_present': bool(snapshot.hp_present), 'name_present': bool(snapshot.name_present)})
    def _save_session(self) -> RecordedSession:
        duration_ms = int((time.monotonic() - self._started_at_monotonic) * 1000.0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = self.config.manual_actions_dir / f'manual_run_{timestamp}.json'
        payload = {'metadata': {'started_at': self._started_at_iso, 'duration_ms': duration_ms, 'sample_ms': self.config.manual_record_sample_ms, 'vision_sample_ms': self.config.manual_record_vision_sample_ms, 'screen_size': [user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)], 'profile_name': None if self._profile is None else self._profile.metadata.profile_name, 'profile_resolution': None if self._profile is None else self._profile.metadata.resolution}, 'events': self._events, 'telemetry': self._telemetry}
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        return RecordedSession(started_at_iso=self._started_at_iso, duration_ms=duration_ms, event_count=len(self._events), telemetry_count=len(self._telemetry), output_path=output_path)