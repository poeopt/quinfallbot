# Source Generated with Decompyle++
# File: cooldown_tracker.pyc (Python 3.11)

from __future__ import annotations
import time

class CooldownTracker:
    
    def __init__(self = None):
        self._last_used = { }

    
    def ready(self = None, name = None, cooldown_s = None):
        return time.monotonic() - self._last_used.get(name, 0) >= cooldown_s

    
    def trigger(self = None, name = None):
        self._last_used[name] = time.monotonic()

    
    def remaining(self = None, name = None, cooldown_s = None):
        return max(0, cooldown_s - time.monotonic() - self._last_used.get(name, 0))

    
    def reset(self = None):
        self._last_used.clear()


