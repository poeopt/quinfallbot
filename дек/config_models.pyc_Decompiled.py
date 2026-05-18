# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\models\\config_models.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
try:
    import winreg
except Exception:
    winreg = None
@dataclass(slots=True)
class AppConfig:
    base_dir: Path
    profiles_dir: Path
    log_dir: Path
    manual_actions_dir: Path
    worker_tick_ms: int = 8
    worker_full_vision_tick_ms: int = 35
    minimap_fast_tick_ms: int = 8
    minimap_fast_max_age_ms: int = 350
    minimap_fast_capture_backend: str = 'auto'
    minimap_fast_capture_target_fps: int = 160
    combat_level_fast_tick_ms: int = 6
    combat_level_fast_max_age_ms: int = 400
    combat_level_fast_capture_backend: str = 'auto'
    combat_level_fast_capture_target_fps: int = 220
    combat_coord_tick_ms: int = 40
    combat_coord_max_age_ms: int = 2500
    combat_coord_read_attempts: int = 1
    combat_coord_attempt_pause_ms: int = 8
    gather_telemetry_tick_ms: int = 250
    gather_telemetry_max_age_ms: int = 700
    worker_perf_log_interval_seconds: float = 2.0
    turn_gain: float = 0.35
    pack_mouse_dx: int = 24
    turn_180_mouse_dx: int = 650
    anti_stuck_mouse_dx: int = 280
    hotkey_vk: int = 116
    hotkey_id: int = 1
    record_hotkey_vk: int = 117
    record_hotkey_id: int = 2
    teleport_hotkey_vk: int = 118
    teleport_hotkey_id: int = 3
    sell_hotkey_vk: int = 119
    sell_hotkey_id: int = 4
    go_to_farm_hotkey_vk: int = 120
    go_to_farm_hotkey_id: int = 5
    manual_record_sample_ms: int = 20
    manual_record_vision_sample_ms: int = 150
    tesseract_cmd: str | None = None
    game_window_title_hint: str = 'quinfall'
    game_focus_retry_count: int = 4
    game_focus_retry_delay_ms: int = 120
    @staticmethod
    def detect_tesseract_cmd() -> str | None:
        runtime_root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]
        bundled_candidates = [runtime_root / 'third_party' / 'tesseract' / 'tesseract.exe', runtime_root / '_internal' / 'third_party' / 'tesseract' / 'tesseract.exe', Path(__file__).resolve().parents[2] / 'third_party' / 'tesseract' / 'tesseract.exe', Path(__file__).resolve().parents[2] / '_internal' / 'third_party' / 'tesseract' / 'tesseract.exe']
        for candidate in bundled_candidates:
            if candidate.exists():
                return str(candidate)
        path_match = shutil.which('tesseract')
        if path_match:
            return path_match
        else:
            candidate_roots = [Path(os.environ.get('ProgramFiles', 'C:\\Program Files')), Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')), Path(os.environ.get('LOCALAPPDATA', 'C:\\Users\\User\\AppData\\Local'))]
            for root in candidate_roots:
                for candidate in [root / 'Tesseract-OCR' / 'tesseract.exe', root / 'Programs' / 'Tesseract-OCR' / 'tesseract.exe']:
                    if candidate.exists():
                        return str(candidate)
            if winreg is None:
                return None
            else:
                registry_locations = [(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Tesseract-OCR'), (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Tesseract-OCR')]
                for hive, subkey in registry_locations:
                    try:
                        with winreg.OpenKey(hive, subkey) as key:
                            install_dir, _ = winreg.QueryValueEx(key, 'InstallDir')
                    except OSError:
                        continue
                    candidate = Path(str(install_dir)) / 'tesseract.exe'
                    if candidate.exists():
                        return str(candidate)
    @classmethod
    def default(cls, base_dir: Path) -> 'AppConfig':
        profiles_dir = base_dir / 'profiles'
        log_dir = base_dir / 'logs'
        manual_actions_dir = log_dir / 'manual_actions'
        profiles_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        manual_actions_dir.mkdir(parents=True, exist_ok=True)
        return cls(base_dir=base_dir, profiles_dir=profiles_dir, log_dir=log_dir, manual_actions_dir=manual_actions_dir, tesseract_cmd=cls.detect_tesseract_cmd())