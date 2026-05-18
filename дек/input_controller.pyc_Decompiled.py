# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\input\\input_controller.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import ctypes
import logging
import threading
import time
from ctypes import wintypes
import win32con
from mmobot.auth.runtime_access import RuntimeAccessController
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 2
MOUSEEVENTF_MOVE = 1
MOUSEEVENTF_LEFTDOWN = 2
MOUSEEVENTF_LEFTUP = 4
MOUSEEVENTF_RIGHTDOWN = 8
MOUSEEVENTF_RIGHTUP = 16
MOUSEEVENTF_WHEEL = 2048
MOUSEEVENTF_ABSOLUTE = 32768
SM_CXSCREEN = 0
SM_CYSCREEN = 1
ULONG_PTR = wintypes.WPARAM
user32 = ctypes.windll.user32
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]
class INPUT_UNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', INPUT_UNION)]
class InputController:
    KEY_MAP = {'W': ord('W'), 'A': ord('A'), 'S': ord('S'), 'D': ord('D'), 'E': ord('E'), 'I': ord('I'), 'M': ord('M'), 'P': ord('P'), 'Y': ord('Y'), '1': ord('1'), '2': ord('2'), '3': ord('3'), 'SHIFT': win32con.VK_SHIFT, 'SPACE': win32con.VK_SPACE, 'ESC': win32con.VK_ESCAPE}
    def __init__(self, access_controller: RuntimeAccessController | None=None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.access_controller = access_controller
        self._lock = threading.Lock()
        self._pressed_keys = set()
        self._pressed_buttons = set()
    def _ensure_allowed(self) -> None:
        if self.access_controller is not None:
            self.access_controller.ensure_runtime_allowed()
    def _send(self, *inputs: INPUT) -> None:
        n_inputs = len(inputs)
        arr = (INPUT * n_inputs)(*inputs)
        sent = user32.SendInput(n_inputs, ctypes.byref(arr), ctypes.sizeof(INPUT))
        if sent!= n_inputs:
            raise RuntimeError(f'SendInput sent {sent}/{n_inputs}')
    def _send_key(self, vk: int, key_up: bool) -> None:
        flags = KEYEVENTF_KEYUP if key_up else 0
        ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
        event = INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=ki))
        self._send(event)
    def _send_mouse(self, flags: int, dx: int=0, dy: int=0, mouse_data: int=0) -> None:
        mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=mouse_data, dwFlags=flags, time=0, dwExtraInfo=0)
        event = INPUT(type=INPUT_MOUSE, union=INPUT_UNION(mi=mi))
        self._send(event)
    def press_key(self, key_name: str) -> None:
        key_name = key_name.upper()
        self._ensure_allowed()
        with self._lock:
            if key_name in self._pressed_keys:
                return
            else:
                vk = self.KEY_MAP[key_name]
                self._send_key(vk, key_up=False)
                self._pressed_keys.add(key_name)
    def release_key(self, key_name: str) -> None:
        key_name = key_name.upper()
        with self._lock:
            if key_name not in self._pressed_keys:
                return
            else:
                vk = self.KEY_MAP[key_name]
                self._send_key(vk, key_up=True)
                self._pressed_keys.discard(key_name)
    def tap_key(self, key_name: str, hold_s: float=0.05) -> None:
        self._ensure_allowed()
        self.press_key(key_name)
        time.sleep(hold_s)
        self.release_key(key_name)
    def move_mouse_relative(self, dx: int, dy: int=0) -> None:
        self._ensure_allowed()
        with self._lock:
            self._send_mouse(MOUSEEVENTF_MOVE, dx=dx, dy=dy)
    def move_mouse_absolute(self, x: int, y: int) -> None:
        self._ensure_allowed()
        with self._lock:
            width = user32.GetSystemMetrics(SM_CXSCREEN) - 1
            height = user32.GetSystemMetrics(SM_CYSCREEN) - 1
            abs_x = int(x * 65535 / max(1, width))
            abs_y = int(y * 65535 / max(1, height))
            self._send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, dx=abs_x, dy=abs_y)
    def scroll_wheel(self, notches: int) -> None:
        if notches == 0:
            return None
        else:
            self._ensure_allowed()
            wheel_delta = win32con.WHEEL_DELTA
            direction = 1 if notches > 0 else (-1)
            with self._lock:
                for _ in range(abs(notches)):
                    self._send_mouse(MOUSEEVENTF_WHEEL, mouse_data=direction * wheel_delta)
    def mouse_down_left(self) -> None:
        self._ensure_allowed()
        with self._lock:
            if 'left' in self._pressed_buttons:
                return
            else:
                self._send_mouse(MOUSEEVENTF_LEFTDOWN)
                self._pressed_buttons.add('left')
    def mouse_up_left(self) -> None:
        with self._lock:
            if 'left' not in self._pressed_buttons:
                return
            else:
                self._send_mouse(MOUSEEVENTF_LEFTUP)
                self._pressed_buttons.discard('left')
    def mouse_down_right(self) -> None:
        self._ensure_allowed()
        with self._lock:
            if 'right' in self._pressed_buttons:
                return
            else:
                self._send_mouse(MOUSEEVENTF_RIGHTDOWN)
                self._pressed_buttons.add('right')
    def mouse_up_right(self) -> None:
        with self._lock:
            if 'right' not in self._pressed_buttons:
                return
            else:
                self._send_mouse(MOUSEEVENTF_RIGHTUP)
                self._pressed_buttons.discard('right')
    def click_absolute(self, x: int, y: int, settle_s: float=0.04) -> None:
        self._ensure_allowed()
        self.move_mouse_absolute(x, y)
        time.sleep(settle_s)
        self.mouse_down_left()
        time.sleep(0.02)
        self.mouse_up_left()
    def drag_absolute(self, start: tuple[int, int], end: tuple[int, int], duration_s: float=0.25, steps: int=12) -> None:
        self._ensure_allowed()
        self.move_mouse_absolute(*start)
        time.sleep(0.05)
        self.mouse_down_left()
        for index in range(1, steps + 1):
            x = int(start[0] + (end[0] - start[0]) * index / steps)
            y = int(start[1] + (end[1] - start[1]) * index / steps)
            self.move_mouse_absolute(x, y)
            time.sleep(duration_s / steps)
        self.mouse_up_left()
    def safe_release_all(self) -> None:
        for key_name in ['W', 'A', 'S', 'D', 'SHIFT', 'SPACE', 'I', '1', '2', '3']:
            try:
                self.release_key(key_name)
            except Exception:
                self.logger.exception('Failed to release key %s', key_name)
        try:
            self.mouse_up_left()
        except Exception:
            self.logger.exception('Failed to release left mouse')
        try:
            self.mouse_up_right()
        except Exception:
            self.logger.exception('Failed to release right mouse')