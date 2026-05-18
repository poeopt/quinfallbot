# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\input\\game_window.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import ctypes
import logging
import time
import win32con
import win32gui
from mmobot.models.config_models import AppConfig
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
class GameWindowManager:
    def __init__(self, config: AppConfig) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.title_hint = config.game_window_title_hint.strip().lower()
        self.retry_count = max(1, int(config.game_focus_retry_count))
        self.retry_delay_s = max(0.02, float(config.game_focus_retry_delay_ms) / 1000.0)
    def find_game_window(self) -> tuple[int, str] | None:
        if not self.title_hint:
            return None
        else:
            matches = []
            def enum_callback(hwnd: int, _lparam: int) -> None:
                if not win32gui.IsWindowVisible(hwnd):
                    return None
                else:
                    title = win32gui.GetWindowText(hwnd)
                    if not title:
                        return None
                    else:
                        title_lower = title.lower()
                        if self.title_hint in title_lower:
                            matches.append((hwnd, title))
            win32gui.EnumWindows(enum_callback, 0)
            if not matches:
                return None
            else:
                matches.sort(key=lambda item: (0 if item[1].lower() == self.title_hint else 1, 0 if item[1].lower().startswith(self.title_hint) else 1, len(item[1])))
                return matches[0]
    def focus_game_window(self, reason: str='') -> bool:
        match = self.find_game_window()
        if match is None:
            self.logger.warning('Game window not found for hint=%r reason=%s', self.title_hint, reason or 'n/a')
            return False
        else:
            hwnd, title = match
            foreground = user32.GetForegroundWindow()
            if foreground == hwnd:
                return True
            else:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                for attempt in range(1, self.retry_count + 1):
                    self._try_focus(hwnd)
                    time.sleep(self.retry_delay_s)
                    if user32.GetForegroundWindow() == hwnd:
                        self.logger.info('Focused game window: %s reason=%s attempt=%s', title, reason or 'n/a', attempt)
                        return True
                self.logger.warning('Failed to focus game window: %s reason=%s', title, reason or 'n/a')
                return False
    def _try_focus(self, hwnd: int) -> None:
        current_thread = kernel32.GetCurrentThreadId()
        foreground = user32.GetForegroundWindow()
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached_threads = []
        try:
            for thread_id in {foreground_thread, target_thread}:
                if thread_id and thread_id!= current_thread:
                        user32.AttachThreadInput(current_thread, thread_id, True)
                        attached_threads.append(thread_id)
            win32gui.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
        except Exception:
            self.logger.exception('Failed to activate game window hwnd=%s', hwnd)
        finally:
            for thread_id in reversed(attached_threads):
                try:
                    user32.AttachThreadInput(current_thread, thread_id, False)
                except Exception:
                    self.logger.exception('Failed to detach thread input thread_id=%s', thread_id)