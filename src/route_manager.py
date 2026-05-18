import json
import math
import time

class RouteManager:
    def __init__(self):
        self.current_route = [] # List of (x, y, z)
        self.is_recording = False

    def start_recording(self):
        self.current_route = []
        self.is_recording = True

    def stop_recording(self, filename=None):
        self.is_recording = False
        if filename:
            self.save_route(filename)

    def add_point(self, x, y, z):
        if self.is_recording:
            # Only add if far enough from last point to save space
            if not self.current_route or self._distance(self.current_route[-1], (x, y, z)) > 5:
                self.current_route.append((x, y, z))

    def save_route(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.current_route, f)

    def load_route(self, filename):
        with open(filename, 'r') as f:
            self.current_route = json.load(f)
        return self.current_route

    def _distance(self, p1, p2):
        return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

    def get_next_point(self, current_pos, look_ahead=1):
        # Logic to find where to go next on the route
        if not self.current_route:
            return None

        # Simple version: find closest point and return next one
        min_dist = float('inf')
        closest_idx = 0
        for i, p in enumerate(self.current_route):
            d = self._distance(current_pos, p)
            if d < min_dist:
                min_dist = d
                closest_idx = i

        next_idx = min(closest_idx + look_ahead, len(self.current_route)-1)
        return self.current_route[next_idx]
