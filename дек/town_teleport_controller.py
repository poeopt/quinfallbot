# Source Generated with Decompyle++
# File: town_teleport_controller.pyc (Python 3.11)

from __future__ import annotations
import logging
import time
from pathlib import Path
from threading import Event
import cv2
import numpy as np
from mmobot.capture.screen_capture import ScreenCapture
from mmobot.input.game_window import GameWindowManager
from mmobot.input.input_controller import InputController
from mmobot.models.config_models import AppConfig
from mmobot.models.profile_models import CalibrationProfile
from mmobot.vision.vision_engine import VisionEngine

class TownTeleportController:
    CAMP_TEXTS = ('Roamtribe', 'Лагерь странников')
    FAST_TRAVEL_TEXTS = ('Fast Travel', 'Fast travel', 'Быстрое путешествие')
    OCR_LANG_SEQUENCE = ('eng', 'rus')
    CAMP_TEXT = CAMP_TEXTS[0]
    FAST_TRAVEL_TEXT = FAST_TRAVEL_TEXTS[0]
    
    def __init__(self, capture = None, vision = None, input_controller = None, config = ('capture', 'ScreenCapture', 'vision', 'VisionEngine', 'input_controller', 'InputController', 'config', 'AppConfig', 'return', 'None')):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.capture = capture
        self.vision = vision
        self.input = input_controller
        self.window = GameWindowManager(config)
        self.log_dir = config.log_dir
        self.map_dir = config.base_dir / 'map'
        self.camp_label_templates = self._load_template_assets((self.map_dir / 'lager_stranikov1.png', self.map_dir / 'lager_stranikov.png'))
        self.camp_label_template = self.camp_label_templates[0] if self.camp_label_templates else None
        self.camp_template = self._load_template_asset(self.map_dir / 'lager.png')
        self.fast_travel_template = self._load_template_asset(self.map_dir / 'button_home.png')

    
    def _sleep_interruptible(self = None, seconds = None, stop_event = None):
        end_time = time.monotonic() + max(0, seconds)
    # WARNING: Decompyle incomplete

    _bbox_center = (lambda rect = None: (x, y, w, h) = rect(x + w // 2, y + h // 2))()
    
    def _load_template_asset(self = None, path = None):
        if not path.exists():
            self.logger.info('Town teleport template not found: %s', path)
            return None
        image = None.imread(str(path), cv2.IMREAD_UNCHANGED)
    # WARNING: Decompyle incomplete

    
    def _load_template_assets(self = None, paths = None):
        assets = []
    # WARNING: Decompyle incomplete

    
    def _save_debug_frame(self = None, frame = None, label = None):
        self.log_dir.mkdir(parents = True, exist_ok = True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        path = self.log_dir / f'''teleport_{label}_{timestamp}.png'''
        cv2.imwrite(str(path), frame)
        self.logger.info('Town teleport debug frame saved: %s', path)
        return None
    # WARNING: Decompyle incomplete

    
    def _find_text_bbox_with_tiles(self, frame, profile, target_text, region, timeout_seconds = None, lang_sequence = None, cols = None, rows = ('profile', 'CalibrationProfile', 'target_text', 'str', 'region', 'tuple[int, int, int, int] | None', 'timeout_seconds', 'float', 'lang_sequence', 'tuple[str | None, ...]', 'cols', 'int', 'rows', 'int', 'return', 'tuple[int, int, int, int] | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _find_any_text_bbox_with_tiles(self, frame, profile, target_texts, region, timeout_seconds = None, lang_sequence = None, cols = None, rows = ('profile', 'CalibrationProfile', 'target_texts', 'tuple[str, ...]', 'region', 'tuple[int, int, int, int] | None', 'timeout_seconds', 'float', 'lang_sequence', 'tuple[str | None, ...]', 'cols', 'int', 'rows', 'int', 'return', 'tuple[int, int, int, int] | None')):
        pass
    # WARNING: Decompyle incomplete

    
    def _get_template_region(self, frame_shape = None, prefix = None, defaults = None, profile = ('frame_shape', 'tuple[int, ...]', 'prefix', 'str', 'defaults', 'tuple[float, float, float, float]', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int, int, int]')):
        (frame_h, frame_w) = frame_shape[:2]
        (x_ratio, y_ratio, w_ratio, h_ratio) = defaults
        x = int(frame_w * float(profile.thresholds.get(f'''{prefix}_x_ratio''', x_ratio)))
        y = int(frame_h * float(profile.thresholds.get(f'''{prefix}_y_ratio''', y_ratio)))
        w = int(frame_w * float(profile.thresholds.get(f'''{prefix}_w_ratio''', w_ratio)))
        h = int(frame_h * float(profile.thresholds.get(f'''{prefix}_h_ratio''', h_ratio)))
        return self._clamp_rect_to_frame(frame_shape, (x, y, w, h))

    
    def _match_template(self, frame = None, template_asset = None, region = None, threshold = ((1, 0.96, 1.04),), scales = ('template_asset', 'dict[str, object] | None', 'region', 'tuple[int, int, int, int]', 'threshold', 'float', 'scales', 'tuple[float, ...]', 'return', 'tuple[int, int, int, int] | None')):
        pass
    # WARNING: Decompyle incomplete

    _bbox_iou = (lambda a = None, b = None: (ax, ay, aw, ah) = a(bx, by, bw, bh) = binter_x1 = max(ax, bx)inter_y1 = max(ay, by)inter_x2 = min(ax + aw, bx + bw)inter_y2 = min(ay + ah, by + bh)if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
0inter_area = None((inter_x2 - inter_x1) * (inter_y2 - inter_y1))union_area = float(aw * ah + bw * bh - inter_area)if union_area <= 0:
0None / union_area)()
    
    def _match_template_candidates(self, frame, template_asset, region = None, threshold = None, scales = None, max_candidates = ((1, 0.96, 1.04), 8, 0.35), dedupe_iou = ('template_asset', 'dict[str, object] | None', 'region', 'tuple[int, int, int, int]', 'threshold', 'float', 'scales', 'tuple[float, ...]', 'max_candidates', 'int', 'dedupe_iou', 'float', 'return', 'list[tuple[float, tuple[int, int, int, int], float]]')):
        pass
    # WARNING: Decompyle incomplete

    
    def _find_camp_template_bbox(self = None, frame = None, profile = None):
        region = self._get_template_region(frame.shape, 'teleport_camp_template_region', defaults = (0, 0.05, 1, 0.9), profile = profile)
        threshold = float(profile.thresholds.get('teleport_camp_template_threshold', 0.94))
        return self._match_template(frame, self.camp_template, region, threshold)

    
    def _find_camp_label_template_bbox(self = None, frame = None, profile = None):
        primary_region = self._get_template_region(frame.shape, 'teleport_camp_label_template_region', defaults = (0, 0.05, 1, 0.9), profile = profile)
        primary_threshold = float(profile.thresholds.get('teleport_camp_label_template_threshold', 0.82))
    # WARNING: Decompyle incomplete

    
    def _find_camp_template_near_label(self = None, frame = None, label_bbox = None, profile = ('label_bbox', 'tuple[int, int, int, int]', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int, int, int] | None')):
        (x, y, w, h) = label_bbox
        threshold = float(profile.thresholds.get('teleport_camp_template_threshold', 0.94))
        (label_cx, label_cy) = self._bbox_center(label_bbox)
        max_distance = float(profile.thresholds.get('teleport_camp_label_candidate_max_distance_px', 460))
        distance_weight = max(1, float(profile.thresholds.get('teleport_camp_label_candidate_distance_weight_px', 460)))
        max_abs_dx = float(profile.thresholds.get('teleport_camp_label_candidate_max_abs_dx_px', 110))
        min_dy = float(profile.thresholds.get('teleport_camp_label_candidate_min_dy_px', -135))
        max_dy = float(profile.thresholds.get('teleport_camp_label_candidate_max_dy_px', -5))
        regions = []
        around_left = int(profile.thresholds.get('teleport_camp_label_near_margin_left_px', 360))
        around_top = int(profile.thresholds.get('teleport_camp_label_near_margin_top_px', 260))
        around_right = int(profile.thresholds.get('teleport_camp_label_near_margin_right_px', 460))
        around_bottom = int(profile.thresholds.get('teleport_camp_label_near_margin_bottom_px', 360))
        regions.append(self._clamp_rect_to_frame(frame.shape, (x - around_left, y - around_top, w + around_left + around_right, h + around_top + around_bottom)))
        global_region = self._get_template_region(frame.shape, 'teleport_camp_pair_global_region', defaults = (0, 0.03, 1, 0.94), profile = profile)
        regions.append(global_region)
        best_candidate = None
    # WARNING: Decompyle incomplete

    
    def _predict_camp_click_from_label(self = None, label_bbox = None, frame_shape = None, profile = ('label_bbox', 'tuple[int, int, int, int]', 'frame_shape', 'tuple[int, ...]', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int]')):
        (x, y, w, _h) = label_bbox
        click_x = x + int(round(w * float(profile.thresholds.get('teleport_camp_label_click_ratio_x', 1.66))))
        click_y = y + int(profile.thresholds.get('teleport_camp_label_click_offset_y_px', 192))
        (frame_h, frame_w) = frame_shape[:2]
        return (max(0, min(frame_w - 1, click_x)), max(0, min(frame_h - 1, click_y)))

    
    def _find_camp_template_near_text(self = None, frame = None, text_bbox = None, profile = ('text_bbox', 'tuple[int, int, int, int]', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int, int, int] | None')):
        (x, y, w, h) = text_bbox
        margin_left = int(profile.thresholds.get('teleport_camp_template_text_margin_left_px', 40))
        margin_right = int(profile.thresholds.get('teleport_camp_template_text_margin_right_px', 220))
        margin_top = int(profile.thresholds.get('teleport_camp_template_text_margin_top_px', 120))
        margin_bottom = int(profile.thresholds.get('teleport_camp_template_text_margin_bottom_px', 70))
        region = self._clamp_rect_to_frame(frame.shape, (x - margin_left, y - margin_top, w + margin_left + margin_right, h + margin_top + margin_bottom))
        return self._match_template(frame, self.camp_template, region, float(profile.thresholds.get('teleport_camp_template_threshold', 0.94)), scales = (1, 0.98, 1.02))

    
    def _find_camp_template_by_icon_text(self, frame = None, profile = None, lang_sequence = None, timeout_seconds = ('profile', 'CalibrationProfile', 'lang_sequence', 'tuple[str | None, ...]', 'timeout_seconds', 'float', 'return', 'tuple[int, int, int, int] | None')):
        region = self._get_template_region(frame.shape, 'teleport_camp_candidate_region', defaults = (0.06, 0.08, 0.88, 0.84), profile = profile)
        threshold = float(profile.thresholds.get('teleport_camp_candidate_threshold', 0.945))
        max_candidates = max(1, int(profile.thresholds.get('teleport_camp_candidate_max_results', 8)))
        candidates = self._match_template_candidates(frame, self.camp_template, region, threshold, scales = (1, 0.98, 0.99, 1.01, 1.02), max_candidates = max_candidates, dedupe_iou = float(profile.thresholds.get('teleport_camp_candidate_dedupe_iou', 0.35)))
        if not candidates:
            return None
        margin_left = None(profile.thresholds.get('teleport_camp_icon_text_margin_left_px', 160))
        margin_right = int(profile.thresholds.get('teleport_camp_icon_text_margin_right_px', 200))
        margin_top = int(profile.thresholds.get('teleport_camp_icon_text_margin_top_px', 140))
        margin_bottom = int(profile.thresholds.get('teleport_camp_icon_text_margin_bottom_px', 150))
        cols = max(1, int(profile.thresholds.get('teleport_camp_icon_text_cols', 2)))
        rows = max(1, int(profile.thresholds.get('teleport_camp_icon_text_rows', 2)))
    # WARNING: Decompyle incomplete

    
    def _find_fast_travel_template_bbox(self = None, frame = None, profile = None):
        region = self._get_template_region(frame.shape, 'teleport_fast_travel_template_region', defaults = (0, 0, 1, 1), profile = profile)
        threshold = float(profile.thresholds.get('teleport_fast_travel_template_threshold', 0.84))
        return self._match_template(frame, self.fast_travel_template, region, threshold, scales = (1, 0.98, 1.02))

    
    def _find_quick_camp_bbox(self = None, frame = None, profile = None):
        label_bbox = self._find_camp_label_template_bbox(frame, profile)
    # WARNING: Decompyle incomplete

    
    def _find_global_camp_template_bbox(self = None, frame = None, profile = None):
        if int(profile.thresholds.get('teleport_allow_global_camp_template_fallback', 0)) <= 0:
            return None
        region = None._get_template_region(frame.shape, 'teleport_global_camp_template_region', defaults = (0.18, 0.16, 0.64, 0.66), profile = profile)
        threshold = float(profile.thresholds.get('teleport_global_camp_template_threshold', 0.985))
        bbox = self._match_template(frame, self.camp_template, region, threshold, scales = (1, 0.99, 1.01))
    # WARNING: Decompyle incomplete

    
    def _zoom_out_map(self = None, profile = None, stop_event = None):
        anchor_ratio_x = min(0.95, max(0.05, float(profile.thresholds.get('teleport_map_zoom_anchor_ratio_x', 0.35))))
        anchor_ratio_y = min(0.95, max(0.05, float(profile.thresholds.get('teleport_map_zoom_anchor_ratio_y', 0.36))))
        anchor_x = int(profile.screen_width * anchor_ratio_x)
        anchor_y = int(profile.screen_height * anchor_ratio_y)
        self.input.move_mouse_absolute(anchor_x, anchor_y)
        zoom_out_notches = max(1, int(profile.thresholds.get('teleport_map_zoom_out_notches', 80)))
        burst_notches = max(1, int(profile.thresholds.get('teleport_map_zoom_burst_notches', 8)))
        probe_start_notches = max(0, min(zoom_out_notches, int(profile.thresholds.get('teleport_map_zoom_probe_start_notches', 48))))
        burst_delay_s = float(profile.timeouts.get('teleport_zoom_burst_delay_seconds', profile.timeouts.get('teleport_zoom_step_delay_seconds', 0.06)))
        zoomed_notches = 0
        last_frame = None
    # WARNING: Decompyle incomplete

    
    def _open_map_and_zoom(self = None, profile = None, stop_event = None):
        self.input.tap_key('M', hold_s = 0.08)
        if not self._sleep_interruptible(profile.timeouts.get('teleport_map_open_delay_seconds', 0.9), stop_event):
            return (False, None, None)
        return None._zoom_out_map(profile, stop_event)

    
    def _reset_map_and_zoom(self = None, profile = None, stop_event = None):
        self.logger.info('Town teleport resetting map state via M toggle')
        self.input.tap_key('M', hold_s = 0.08)
        if not self._sleep_interruptible(profile.timeouts.get('teleport_map_open_delay_seconds', 1.1), stop_event):
            return (False, None, None)
        return None._zoom_out_map(profile, stop_event)

    _clamp_rect_to_frame = (lambda frame_shape = None, rect = None: (frame_h, frame_w) = frame_shape[:2](x, y, w, h) = rectx = max(0, min(frame_w - 1, x))y = max(0, min(frame_h - 1, y))w = max(1, min(frame_w - x, w))h = max(1, min(frame_h - y, h))(x, y, w, h))()
    
    def _camp_click_point(self = None, camp_bbox = None, frame_shape = None, profile = ('camp_bbox', 'tuple[int, int, int, int]', 'frame_shape', 'tuple[int, ...]', 'profile', 'CalibrationProfile', 'return', 'tuple[int, int]')):
        if int(profile.thresholds.get('teleport_camp_click_center_bbox', 1)) > 0:
            (click_x, click_y) = self._bbox_center(camp_bbox)
            (frame_h, frame_w) = frame_shape[:2]
            return (max(0, min(frame_w - 1, click_x)), max(0, min(frame_h - 1, click_y)))
        (x, y, w, _h) = None
        anchor_ratio_x = min(0.95, max(0.05, float(profile.thresholds.get('teleport_camp_click_anchor_ratio_x', 0.67))))
        min_offset_x = int(profile.thresholds.get('teleport_camp_click_min_offset_x_px', 70))
        click_offset_y = int(profile.thresholds.get('teleport_camp_click_offset_y_px', 20))
        click_x = x + max(min_offset_x, int(round(w * anchor_ratio_x)))
        click_y = y - click_offset_y
        (frame_h, frame_w) = frame_shape[:2]
        return (max(0, min(frame_w - 1, click_x)), max(0, min(frame_h - 1, click_y)))

    
    def _get_auto_run_dialog_region(self = None, frame_shape = None, profile = None):
        (frame_h, frame_w) = frame_shape[:2]
        width = int(frame_w * float(profile.thresholds.get('teleport_autorun_region_width_ratio', 0.15)))
        height = int(frame_h * float(profile.thresholds.get('teleport_autorun_region_height_ratio', 0.16)))
        x = int(frame_w * float(profile.thresholds.get('teleport_autorun_region_x_ratio', 0.84)))
        y = int(frame_h * float(profile.thresholds.get('teleport_autorun_region_y_ratio', 0.82)))
        return self._clamp_rect_to_frame(frame_shape, (x, y, width, height))

    
    def _auto_run_dialog_present(self = None, frame = None, profile = None):
