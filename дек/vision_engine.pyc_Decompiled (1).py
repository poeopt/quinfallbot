# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'mmobot\\vision\\vision_engine.py'
# Bytecode version: 3.11a7e (3495)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from __future__ import annotations
import json
import logging
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import cv2
import numpy as np
from mmobot.models.profile_models import CalibrationProfile, HsvRange
from mmobot.vision.monster_nn_detector import MonsterNnDetector, MonsterNnTarget
try:
    import pytesseract
except Exception:
    pytesseract = None
try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    RapidOCR = None
@dataclass
class MinimapEnemyCandidate:
    point: tuple[int, int]
    radius: float
    angle_deg: float
    stack_count: int = 1
    template_score: float = 0.0
    source: str = 'color'
@dataclass
class TemplateImage:
    name: str
    bgr: np.ndarray
    mask: np.ndarray | None = None
@dataclass
class VisionSnapshot:
    timestamp: float
    minimap_enemies: list[tuple[int, int]] = field(default_factory=list)
    minimap_enemy_candidates: list['MinimapEnemyCandidate'] = field(default_factory=list)
    minimap_heading_vector: tuple[float, float] | None = None
    minimap_heading_tip: tuple[int, int] | None = None
    minimap_heading_confidence: float = 0.0
    enemy_aggro_markers: list[tuple[int, int]] = field(default_factory=list)
    enemy_aggro_count: int = 0
    enemy_back_target: 'EnemyBackTarget | None' = None
    enemy_level_targets: list['EnemyLevelTarget'] = field(default_factory=list)
    enemy_nn_targets: list['MonsterNnTarget'] = field(default_factory=list)
    enemy_hp_targets: list['EnemyHpTarget'] = field(default_factory=list)
    enemy_body_targets: list['EnemyBodyTarget'] = field(default_factory=list)
    target_locked: bool = False
    target_red_ratio: float = 0.0
    reticle_idle_ratio: float = 0.0
    target_confidence: float = 0.0
    hp_present: bool = False
    hp_edge_ratio: float = 0.0
    hp_sat_ratio: float = 0.0
    hp_layout_detected: bool = False
    hp_vertical_ratio: float | None = None
    hp_lower_ratio: float = 0.0
    name_present: bool = False
    name_edge_ratio: float = 0.0
    name_sat_ratio: float = 0.0
    stamina_ratio: float | None = None
    nearby_enemy_count: int = 0
    nearest_enemy_distance: float | None = None
    compass_marker: tuple[int, int] | None = None
    distance_value: int | None = None
    world_x: int | None = None
    world_y: int | None = None
    world_z: int | None = None
    inventory_slot_colors: dict[str, tuple[int, int, int]] = field(default_factory=dict)
@dataclass
class MinimapFastSnapshot:
    timestamp: float
    minimap_enemies: list[tuple[int, int]] = field(default_factory=list)
    minimap_enemy_candidates: list['MinimapEnemyCandidate'] = field(default_factory=list)
    minimap_heading_vector: tuple[float, float] | None = None
    minimap_heading_tip: tuple[int, int] | None = None
    minimap_heading_confidence: float = 0.0
    nearby_enemy_count: int = 0
    nearest_enemy_distance: float | None = None
    processing_ms: float = 0.0
    tick_hz: float = 0.0
@dataclass
class LevelFastSnapshot:
    timestamp: float
    enemy_level_targets: list['EnemyLevelTarget'] = field(default_factory=list)
    processing_ms: float = 0.0
    tick_hz: float = 0.0
@dataclass
class PresenceReading:
    present: bool
    edge_ratio: float
    sat_ratio: float
    vertical_ratio: float | None = None
    lower_ratio: float = 0.0
@dataclass
class HpBarCandidate:
    rect: tuple[int, int, int, int]
    local_rect: tuple[int, int, int, int]
    area: float
@dataclass
class EnemyBodyTarget:
    hp_bar_rect: tuple[int, int, int, int]
    body_rect: tuple[int, int, int, int]
    body_point: tuple[int, int]
    distance_to_aim: float | None = None
@dataclass
class EnemyLevelTarget:
    icon_rect: tuple[int, int, int, int]
    icon_point: tuple[int, int]
    aim_point: tuple[int, int]
    distance_to_aim: float | None = None
    template_score: float = 0.0
@dataclass
class EnemyBackTarget:
    rect: tuple[int, int, int, int]
    point: tuple[int, int]
    distance_to_aim: float | None = None
    template_score: float = 0.0
    scale: float = 1.0
@dataclass
class EnemyHpTarget:
    hp_bar_rect: tuple[int, int, int, int]
    anchor_point: tuple[int, int]
    distance_to_aim: float | None = None
class VisionEngine:
    def __init__(self, tesseract_cmd: str | None=None) -> None:
        # ***<module>.VisionEngine.__init__: Failure: Different control flow
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ocr_enabled = pytesseract is not None
        self._ocr_missing_logged = False
        self._coord_template_bank = {}
        self._coord_templates_loaded = False
        self._rapid_ocr = None
        self._minimap_enemy_templates_loaded = False
        self._minimap_enemy_templates = []
        self._enemy_aggro_template_loaded = False
        self._enemy_aggro_template_bgr = None
        self._enemy_aggro_template_mask = None
        self._enemy_back_template_loaded = False
        self._enemy_back_template = None
        self._enemy_level_template_loaded = False
        self._enemy_level_template = None
        self._monster_nn_detector = MonsterNnDetector()
        if not self.ocr_enabled or tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    @staticmethod
    def _clamp_rect(rect: tuple[int, int, int, int], frame_shape: tuple[int, int, int]) -> tuple[int, int, int, int]:
        x, y, w, h = rect
        fh, fw = frame_shape[:2]
        x = max(0, min(x, fw - 1))
        y = max(0, min(y, fh - 1))
        w = max(1, min(w, fw - x))
        h = max(1, min(h, fh - y))
        return (x, y, w, h)
    def _crop_zone(self, frame: np.ndarray, profile: CalibrationProfile, zone_name: str) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
        spec = profile.zones.get(zone_name)
        if spec is None:
            return None
        else:
            rect = spec.as_pixels(profile.screen_size)
            if rect is None:
                return None
            else:
                rect = self._clamp_rect(rect, frame.shape)
                x, y, w, h = rect
                return (frame[y:y + h, x:x + w].copy(), rect)
    @staticmethod
    def _hsv_mask(image_bgr: np.ndarray, hsv_range: HsvRange) -> np.ndarray:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array(hsv_range.lower, dtype=np.uint8)
        upper = np.array(hsv_range.upper, dtype=np.uint8)
        return cv2.inRange(hsv, lower, upper)
    @staticmethod
    def _mask_ratio(image_bgr: np.ndarray, hsv_range: HsvRange) -> float:
        mask = VisionEngine._hsv_mask(image_bgr, hsv_range)
        return float(np.count_nonzero(mask)) / float(mask.size)
    @staticmethod
    def _dedupe_points(points: list[tuple[int, int]], min_distance: int) -> list[tuple[int, int]]:
        result = []
        for point in points:
            keep = True
            for existing in result:
                if np.hypot(point[0] - existing[0], point[1] - existing[1]) < min_distance:
                    keep = False
                    break
            if keep:
                result.append(point)
        return result
    def _load_template_image(self, path: Path, *, label: str) -> TemplateImage | None:
        if not path.exists():
            self.logger.debug('%s not found: %s', label, path)
            return None
        else:
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is None or image.size == 0:
                self.logger.warning('Failed to load %s: %s', label, path)
                return None
            else:
                if image.ndim == 2:
                    return TemplateImage(name=path.stem, bgr=cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), mask=None)
                else:
                    if image.shape[2] == 4:
                        alpha = image[:, :, 3]
                        return TemplateImage(name=path.stem, bgr=image[:, :, :3].copy(), mask=np.where(alpha > 0, 255, 0).astype(np.uint8))
                    else:
                        return TemplateImage(name=path.stem, bgr=image[:, :, :3].copy(), mask=None)
    def _load_minimap_enemy_templates(self) -> list[TemplateImage]:
        if self._minimap_enemy_templates_loaded:
            return self._minimap_enemy_templates
        else:
            self._minimap_enemy_templates_loaded = True
            self._minimap_enemy_templates = []
            for filename in ['mob_map.png']:
                path = self._resolve_base_dir() / 'map' / filename
                template = self._load_template_image(path, label='Minimap enemy template')
                if template is not None:
                    self._minimap_enemy_templates.append(template)
            return self._minimap_enemy_templates
    def _load_enemy_aggro_template(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        if self._enemy_aggro_template_loaded:
            return (self._enemy_aggro_template_bgr, self._enemy_aggro_template_mask)
        else:
            self._enemy_aggro_template_loaded = True
            path = self._resolve_base_dir() / 'map' / 'mob_Agression.png'
            if not path.exists():
                self.logger.debug('Enemy aggro template not found: %s', path)
                return (None, None)
            else:
                image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if image is None or image.size == 0:
                    self.logger.warning('Failed to load enemy aggro template: %s', path)
                    return (None, None)
                else:
                    if image.ndim == 2:
                        self._enemy_aggro_template_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                        self._enemy_aggro_template_mask = None
                    else:
                        if image.shape[2] == 4:
                            self._enemy_aggro_template_bgr = image[:, :, :3].copy()
                            alpha = image[:, :, 3]
                            self._enemy_aggro_template_mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
                        else:
                            self._enemy_aggro_template_bgr = image[:, :, :3].copy()
                            self._enemy_aggro_template_mask = None
                    return (self._enemy_aggro_template_bgr, self._enemy_aggro_template_mask)
    def _load_enemy_level_template(self) -> TemplateImage | None:
        if self._enemy_level_template_loaded:
            return self._enemy_level_template
        else:
            self._enemy_level_template_loaded = True
            path = self._resolve_base_dir() / 'map' / 'lvl_mob.png'
            self._enemy_level_template = self._load_template_image(path, label='Enemy level template')
            return self._enemy_level_template
    def _load_enemy_back_template(self) -> TemplateImage | None:
        if self._enemy_back_template_loaded:
            return self._enemy_back_template
        else:
            self._enemy_back_template_loaded = True
            path = self._resolve_base_dir() / 'map' / 'MOb.png'
            self._enemy_back_template = self._load_template_image(path, label='Enemy back template')
            return self._enemy_back_template
    def detect_enemy_back_target(self, frame: np.ndarray, profile: CalibrationProfile) -> EnemyBackTarget | None:
        if float(profile.thresholds.get('combat_enable_back_silhouette_support', 0.0)) <= 0.5:
            return None
        else:
            template = self._load_enemy_back_template()
            if template is None:
                return None
            else:
                aim_spec = profile.zones.get('aim_region')
                aim_rect = aim_spec.as_pixels(profile.screen_size) if aim_spec else None
                if aim_rect is None:
                    return None
                else:
                    ax, ay, aw, ah = aim_rect
                    aim_center = (ax + aw // 2, ay + ah // 2)
                    expand_x = int(profile.thresholds.get('combat_back_silhouette_region_expand_x_px', 420))
                    expand_top = int(profile.thresholds.get('combat_back_silhouette_region_expand_top_px', 220))
                    expand_bottom = int(profile.thresholds.get('combat_back_silhouette_region_expand_bottom_px', 560))
                    zone_rect = (aim_center[0] - expand_x, aim_center[1] - expand_top, expand_x * 2, expand_top + expand_bottom)
                    x0, y0, w0, h0 = self._clamp_rect(zone_rect, frame.shape)
                    crop = frame[y0:y0 + h0, x0:x0 + w0]
                    if crop.size == 0:
                        return None
                    else:
                        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        threshold = float(profile.thresholds.get('combat_back_silhouette_template_threshold', 0.46))
                        min_scale = float(profile.thresholds.get('combat_back_silhouette_scale_min', 0.72))
                        max_scale = float(profile.thresholds.get('combat_back_silhouette_scale_max', 1.16))
                        step = float(profile.thresholds.get('combat_back_silhouette_scale_step', 0.08))
                        max_distance = float(profile.thresholds.get('combat_back_silhouette_max_distance_px', 340.0))
                        best = None
                        scale = min_scale
                        while scale <= max_scale + 1e-06:
                            templ_w = max(8, int(round(template.bgr.shape[1] * scale)))
                            templ_h = max(8, int(round(template.bgr.shape[0] * scale)))
                            if templ_w >= crop_gray.shape[1] or templ_h >= crop_gray.shape[0]:
                                scale += step
                                continue
                            resized_bgr = cv2.resize(template.bgr, (templ_w, templ_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
                            templ_gray = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2GRAY)
                            resized_mask = None
                            if template.mask is not None:
                                resized_mask = cv2.resize(template.mask, (templ_w, templ_h), interpolation=cv2.INTER_NEAREST)
                                resized_mask = np.where(resized_mask > 0, 255, 0).astype(np.uint8)
                            try:
                                if resized_mask is not None:
                                    response = cv2.matchTemplate(crop_gray, templ_gray, cv2.TM_CCORR_NORMED, mask=resized_mask)
                                else:
                                    response = cv2.matchTemplate(crop_gray, templ_gray, cv2.TM_CCORR_NORMED)
                            except cv2.error:
                                scale += step
                                continue
                            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(response)
                            score = float(max_val)
                            if score < threshold:
                                scale += step
                                continue
                            rect = (x0 + max_loc[0], y0 + max_loc[1], templ_w, templ_h)
                            point = (rect[0] + templ_w // 2, rect[1] + int(round(templ_h * 0.4)))
                            distance_to_aim = float(np.hypot(point[0] - aim_center[0], point[1] - aim_center[1]))
                            if distance_to_aim > max_distance:
                                scale += step
                                continue
                            candidate = EnemyBackTarget(rect=rect, point=point, distance_to_aim=distance_to_aim, template_score=score, scale=scale)
                            if best is None or (candidate.template_score, -candidate.distance_to_aim) > (best.template_score, -best.distance_to_aim):
                                best = candidate
                            scale += step
                        return best
    def detect_enemy_aggro_markers(self, frame: np.ndarray, profile: CalibrationProfile) -> list[tuple[int, int]]:
        template_bgr, template_mask = self._load_enemy_aggro_template()
        if template_bgr is None:
            return []
        else:
            fh, fw = frame.shape[:2]
            rx = float(profile.thresholds.get('enemy_aggro_template_region_x_ratio', 0.14))
            ry = float(profile.thresholds.get('enemy_aggro_template_region_y_ratio', 0.06))
            rw = float(profile.thresholds.get('enemy_aggro_template_region_w_ratio', 0.72))
            rh = float(profile.thresholds.get('enemy_aggro_template_region_h_ratio', 0.58))
            rect = self._clamp_rect((int(round(fw * rx)), int(round(fh * ry)), int(round(fw * rw)), int(round(fh * rh))), frame.shape)
            x0, y0, w, h = rect
            crop = frame[y0:y0 + h, x0:x0 + w]
            crop_h, crop_w = crop.shape[:2]
            templ_h, templ_w = template_bgr.shape[:2]
            if crop_h < templ_h or crop_w < templ_w:
                return []
            else:
                threshold = float(profile.thresholds.get('enemy_aggro_template_threshold', 0.82))
                merge_distance = max(1, int(profile.thresholds.get('enemy_aggro_template_merge_distance_px', 48.0)))
                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                lower_1 = np.array([0, 80, 150], dtype=np.uint8)
                upper_1 = np.array([18, 255, 255], dtype=np.uint8)
                lower_2 = np.array([170, 80, 150], dtype=np.uint8)
                upper_2 = np.array([180, 255, 255], dtype=np.uint8)
                warm_mask = cv2.inRange(hsv, lower_1, upper_1)
                warm_mask = cv2.bitwise_or(warm_mask, cv2.inRange(hsv, lower_2, upper_2))
                warm_mask = cv2.morphologyEx(warm_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 9)), iterations=1)
                warm_mask = cv2.dilate(warm_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5)), iterations=1)
                candidate_pad_x = max(2, int(profile.thresholds.get('enemy_aggro_candidate_pad_x_px', 14.0)))
                candidate_pad_y = max(2, int(profile.thresholds.get('enemy_aggro_candidate_pad_y_px', 18.0)))
                min_area = float(profile.thresholds.get('enemy_aggro_candidate_min_area_px', 180.0))
                min_width = max(6, int(profile.thresholds.get('enemy_aggro_candidate_min_width_px', 16.0)))
                min_height = max(12, int(profile.thresholds.get('enemy_aggro_candidate_min_height_px', 28.0)))
                max_width = max(min_width, int(profile.thresholds.get('enemy_aggro_candidate_max_width_px', 120.0)))
                max_height = max(min_height, int(profile.thresholds.get('enemy_aggro_candidate_max_height_px', 180.0)))
                min_aspect = float(profile.thresholds.get('enemy_aggro_candidate_min_aspect_ratio', 1.15))
                max_aspect = float(profile.thresholds.get('enemy_aggro_candidate_max_aspect_ratio', 4.2))
                num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(warm_mask)
                candidate_rects = []
                for index in range(1, num_labels):
                    cx, cy, cw, ch, area = stats[index]
                    if float(area) < min_area:
                        continue
                    else:
                        if cw < min_width or ch < min_height or cw > max_width or (ch > max_height):
                            continue
                        else:
                            aspect = float(ch) / float(max(1, cw))
                            if aspect < min_aspect or aspect > max_aspect:
                                continue
                            else:
                                left = max(0, int(cx) - candidate_pad_x)
                                top = max(0, int(cy) - candidate_pad_y)
                                right = min(crop_w, int(cx + cw) + candidate_pad_x)
                                bottom = min(crop_h, int(cy + ch) + candidate_pad_y)
                                candidate_rects.append((left, top, right - left, bottom - top))
                points = []
                for left, top, cand_w, cand_h in candidate_rects:
                    candidate_crop = crop[top:top + cand_h, left:left + cand_w]
                    if candidate_crop.shape[0] < templ_h or candidate_crop.shape[1] < templ_w:
                        continue
                    else:
                        try:
                            if template_mask is not None:
                                response = cv2.matchTemplate(candidate_crop, template_bgr, cv2.TM_CCORR_NORMED, mask=template_mask)
                            else:
                                response = cv2.matchTemplate(candidate_crop, template_bgr, cv2.TM_CCORR_NORMED)
                        except cv2.error:
                            self.logger.exception('Failed to match enemy aggro template candidate')
                            continue
                        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(response)
                        if float(max_val) < threshold:
                            continue
                        else:
                            point = (x0 + left + max_loc[0] + templ_w // 2, y0 + top + max_loc[1] + templ_h // 2)
                            if any((np.hypot(point[0] - existing[0], point[1] - existing[1]) < merge_distance for existing in points)):
                                continue
                            else:
                                points.append(point)
                return points
    def _detect_enemy_level_targets_from_crop(self, crop: np.ndarray, x0: int, y0: int, profile: CalibrationProfile) -> list[EnemyLevelTarget]:
        template = self._load_enemy_level_template()
        if template is None:
            return []
        else:
            if crop.size == 0:
                return []
            else:
                templ_h, templ_w = template.bgr.shape[:2]
                if crop.shape[0] < templ_h or crop.shape[1] < templ_w:
                    return []
                else:
                    threshold = float(profile.thresholds.get('combat_level_icon_template_threshold', 0.84))
                    partial_threshold = float(profile.thresholds.get('combat_level_icon_partial_template_threshold', max(0.74, threshold - 0.06)))
                    partial_keep_ratio = float(profile.thresholds.get('combat_level_icon_partial_mask_keep_ratio', 0.68))
                    partial_score_penalty = float(profile.thresholds.get('combat_level_icon_partial_score_penalty', 0.035))
                    merge_distance = max(1, int(profile.thresholds.get('combat_level_icon_merge_distance_px', 28)))
                    local_max_window = max(3, int(profile.thresholds.get('combat_level_icon_local_max_window_px', 7)))
                    base_mask = template.mask if template.mask is not None else np.full((templ_h, templ_w), 255, dtype=np.uint8)
                    keep_cols = max(1, min(templ_w, int(round(templ_w * partial_keep_ratio))))
                    keep_rows = max(1, min(templ_h, int(round(templ_h * partial_keep_ratio))))
                    left_mask = base_mask.copy()
                    left_mask[:, keep_cols:] = 0
                    right_mask = base_mask.copy()
                    right_mask[:, :max(0, templ_w - keep_cols)] = 0
                    top_mask = base_mask.copy()
                    top_mask[keep_rows:, :] = 0
                    bottom_mask = base_mask.copy()
                    bottom_mask[:max(0, templ_h - keep_rows), :] = 0
                    match_variants = [(template.mask, threshold, 0.0), (left_mask, partial_threshold, partial_score_penalty), (right_mask, partial_threshold, partial_score_penalty), (top_mask, partial_threshold, partial_score_penalty), (bottom_mask, partial_threshold, partial_score_penalty)]
                    aim_spec = profile.zones.get('aim_region')
                    aim_rect = aim_spec.as_pixels(profile.screen_size) if aim_spec else None
                    aim_center = None
                    if aim_rect is not None:
                        ax, ay, aw, ah = aim_rect
                        aim_center = (ax + aw // 2, ay + ah // 2)
                    offset_x = int(profile.thresholds.get('combat_level_icon_aim_offset_x_px', 50))
                    offset_y = int(profile.thresholds.get('combat_level_icon_aim_offset_y_px', 0))
                    raw_matches = []
                    kernel = np.ones((local_max_window, local_max_window), dtype=np.uint8)
                    for variant_mask, variant_threshold, score_penalty in match_variants:
                        try:
                            if variant_mask is not None:
                                response = cv2.matchTemplate(crop, template.bgr, cv2.TM_CCORR_NORMED, mask=variant_mask)
                            else:
                                response = cv2.matchTemplate(crop, template.bgr, cv2.TM_CCORR_NORMED)
                        except cv2.error:
                            self.logger.exception('Failed to match enemy level template')
                            continue
                        dilated = cv2.dilate(response, kernel)
                        maxima = (response >= variant_threshold) & (response >= dilated - 1e-06)
                        ys, xs = np.where(maxima)
                        for x, y in zip(xs.tolist(), ys.tolist()):
                            score = max(0.0, float(response[y, x]) - score_penalty)
                            rect = (x0 + x, y0 + y, templ_w, templ_h)
                            icon_point = (rect[0] + templ_w // 2, rect[1] + templ_h // 2)
                            aim_point = (icon_point[0] + offset_x, icon_point[1] + offset_y)
                            distance_to_aim = None
                            if aim_center is not None:
                                distance_to_aim = float(np.hypot(aim_point[0] - aim_center[0], aim_point[1] - aim_center[1]))
                            raw_matches.append(EnemyLevelTarget(icon_rect=rect, icon_point=icon_point, aim_point=aim_point, distance_to_aim=distance_to_aim, template_score=score))
                    if not raw_matches:
                        return []
                    else:
                        raw_matches.sort(key=lambda target: (float('inf') if target.distance_to_aim is None else target.distance_to_aim, -target.template_score))
                        merged = []
                        for target in raw_matches:
                            if any((np.hypot(target.icon_point[0] - other.icon_point[0], target.icon_point[1] - other.icon_point[1]) <= merge_distance for other in merged)):
                                continue
                            else:
                                merged.append(target)
                        return merged
    def detect_enemy_level_targets(self, frame: np.ndarray, profile: CalibrationProfile) -> list[EnemyLevelTarget]:
        zone_spec = profile.zones.get('lvl_mob_region') or profile.zones.get('name_level_region') or profile.zones.get('hp_bars_region')
        zone_rect = zone_spec.as_pixels(profile.screen_size) if zone_spec else (0, 0, frame.shape[1], frame.shape[0])
        x0, y0, w0, h0 = self._clamp_rect(zone_rect, frame.shape)
        crop = frame[y0:y0 + h0, x0:x0 + w0]
        return self._detect_enemy_level_targets_from_crop(crop, x0, y0, profile)
    def detect_enemy_nn_targets(self, frame: np.ndarray, profile: CalibrationProfile) -> list[MonsterNnTarget]:
        aim_spec = profile.zones.get('aim_region')
        aim_rect = aim_spec.as_pixels(profile.screen_size) if aim_spec else None
        aim_center = None
        if aim_rect is not None:
            ax, ay, aw, ah = aim_rect
            aim_center = (ax + aw // 2, ay + ah // 2)
        return self._monster_nn_detector.detect(frame, profile, aim_center=aim_center)
    def analyze_level_fast_region(self, crop: np.ndarray, region_rect: tuple[int, int, int, int], profile: CalibrationProfile, *, timestamp: float, tick_hz: float) -> LevelFastSnapshot:
        x0, y0, _w0, _h0 = region_rect
        targets = self._detect_enemy_level_targets_from_crop(crop, x0, y0, profile)
        return LevelFastSnapshot(timestamp=timestamp, enemy_level_targets=targets, processing_ms=0.0, tick_hz=tick_hz)
    def _detect_minimap_enemies_template(self, crop: np.ndarray, rect: tuple[int, int, int, int], profile: CalibrationProfile, *, red_mask: np.ndarray | None=None, red_components: list[dict[str, object]] | None=None) -> list[tuple[tuple[int, int], int, float, str]]:
        templates = self._load_minimap_enemy_templates()
        if not templates:
            return []
        else:
            crop_h, crop_w = crop.shape[:2]
            min_templ_h = min((template.bgr.shape[0] for template in templates))
            min_templ_w = min((template.bgr.shape[1] for template in templates))
            if crop_h < min_templ_h or crop_w < min_templ_w:
                return []
            else:
                method = cv2.TM_CCORR_NORMED
                threshold = float(profile.thresholds.get('minimap_enemy_template_threshold', 0.82))
                overlay_threshold = float(profile.thresholds.get('minimap_enemy_template_heading_overlay_threshold', max(0.7, threshold - 0.06)))
                max_results = max(1, int(profile.thresholds.get('minimap_enemy_template_max_results', 32.0)))
                local_max_window = max(3, int(profile.thresholds.get('minimap_enemy_template_local_max_window_px', 5.0)))
                support_merge_distance = max(1, int(profile.thresholds.get('minimap_enemy_template_support_merge_distance_px', 4.0)))
                cluster_distance = max(1, int(profile.thresholds.get('minimap_enemy_stack_cluster_distance_px', profile.thresholds.get('minimap_enemy_merge_distance_px', 8.0))))
                x0, y0, _, _ = rect
                candidates = []
                if red_mask is None:
                    red_mask = self._build_minimap_enemy_red_mask(crop, profile)
                if red_components is None:
                    _, _, stats, centroids = cv2.connectedComponentsWithStats(red_mask)
                    red_components = []
                    for index in range(1, stats.shape[0]):
                        cx, cy, cw, ch, area = stats[index]
                        if int(area) <= 0:
                            continue
                        else:
                            red_components.append({'rect': (int(cx), int(cy), int(cw), int(ch)), 'area': float(area), 'center': (float(centroids[index][0]), float(centroids[index][1]))})
                candidate_pad = max(2, int(profile.thresholds.get('minimap_enemy_template_candidate_pad_px', max((max(template.bgr.shape[1], template.bgr.shape[0]) for template in templates)))))
                candidate_merge_gap = max(0, int(profile.thresholds.get('minimap_enemy_template_candidate_merge_gap_px', float(candidate_pad // 2))))
                heading_roi_pad = max(2, int(profile.thresholds.get('minimap_enemy_template_heading_roi_pad_px', float(candidate_pad))))
                def clamp_local_roi(left: int, top: int, right: int, bottom: int) -> tuple[int, int, int, int] | None:
                    left = max(0, int(left))
                    top = max(0, int(top))
                    right = min(crop_w, int(right))
                    bottom = min(crop_h, int(bottom))
                    if right - left < min_templ_w or bottom - top < min_templ_h:
                        return None
                    else:
                        return (left, top, right - left, bottom - top)
                rois = []
                for component in red_components:
                    cx, cy, cw, ch = component['rect']
                    roi = clamp_local_roi(cx - candidate_pad, cy - candidate_pad, cx + cw + candidate_pad, cy + ch + candidate_pad)
                    if roi is not None:
                        rois.append((*roi, threshold))
                center_spec = profile.points.get('minimap_center')
                center_px = center_spec.as_pixels(profile.screen_size) if center_spec else None
                if center_px is not None:
                    local_cx = center_px[0] - x0
                    local_cy = center_px[1] - y0
                    if 0 <= local_cx < crop_w and 0 <= local_cy < crop_h:
                                    heading_mask = self._build_minimap_heading_mask(crop, local_cx, local_cy, profile)
                                    dilation_size = max(1, int(profile.thresholds.get('minimap_enemy_heading_overlay_dilation_px', 5.0)))
                                    heading_mask = cv2.dilate(heading_mask, np.ones((dilation_size, dilation_size), dtype=np.uint8), iterations=1)
                                    overlay_min_radius = float(profile.thresholds.get('minimap_enemy_heading_overlay_min_radius_px', 26.0))
                                    overlay_max_radius = float(profile.thresholds.get('minimap_enemy_heading_overlay_max_radius_px', 72.0))
                                    ys, xs = np.where(heading_mask > 0)
                                    if xs.size > 0:
                                        radius = np.hypot(xs.astype(np.float32) - float(local_cx), ys.astype(np.float32) - float(local_cy))
                                        valid = np.logical_and(radius >= overlay_min_radius, radius <= overlay_max_radius)
                                        if np.count_nonzero(valid) > 0:
                                            xs = xs[valid]
                                            ys = ys[valid]
                                            roi = clamp_local_roi(int(xs.min()) - heading_roi_pad, int(ys.min()) - heading_roi_pad, int(xs.max()) + heading_roi_pad + 1, int(ys.max()) + heading_roi_pad + 1)
                                            if roi is not None:
                                                rois.append((*roi, overlay_threshold))
                if not rois:
                    return []
                else:
                    rois.sort(key=lambda item: item[4], reverse=True)
                    merged_rois = []
                    for left, top, roi_w, roi_h, roi_threshold in rois:
                        matched_index = None
                        right = left + roi_w
                        bottom = top + roi_h
                        for index, (mx, my, mw, mh, existing_threshold) in enumerate(merged_rois):
                            mright = mx + mw
                            mbottom = my + mh
                            if left <= mright + candidate_merge_gap and right >= mx - candidate_merge_gap and (top <= mbottom + candidate_merge_gap) and (bottom >= my - candidate_merge_gap):
                                            matched_index = index
                                            merged_rois[index] = (min(mx, left), min(my, top), max(mright, right) - min(mx, left), max(mbottom, bottom) - min(my, top), min(existing_threshold, roi_threshold))
                                            break
                        if matched_index is None:
                            merged_rois.append((left, top, roi_w, roi_h, roi_threshold))
                    kernel = np.ones((local_max_window, local_max_window), dtype=np.uint8)
                    for left, top, roi_w, roi_h, roi_threshold in merged_rois:
                        candidate_crop = crop[top:top + roi_h, left:left + roi_w]
                        for template in templates:
                            templ_h, templ_w = template.bgr.shape[:2]
                            if candidate_crop.shape[0] < templ_h or candidate_crop.shape[1] < templ_w:
                                continue
                            else:
                                template_threshold = roi_threshold
                                try:
                                    if template.mask is not None:
                                        response = cv2.matchTemplate(candidate_crop, template.bgr, method, mask=template.mask)
                                    else:
                                        response = cv2.matchTemplate(candidate_crop, template.bgr, method)
                                except cv2.error:
                                    self.logger.exception('Failed to match minimap enemy template ROI')
                                    continue
                                dilated = cv2.dilate(response, kernel)
                                maxima = (response >= template_threshold) & (response >= dilated - 1e-06)
                                ys, xs = np.where(maxima)
                                for x, y in zip(xs.tolist(), ys.tolist()):
                                    score = float(response[y, x])
                                    point = (x0 + left + x + templ_w // 2, y0 + top + y + templ_h // 2)
                                    candidates.append((score, point, template.name))
                    if not candidates:
                        return []
                    else:
                        candidates.sort(key=lambda item: item[0], reverse=True)
                        clusters = []
                        for score, point, template_name in candidates:
                            if len(clusters) >= max_results:
                                break
                            else:
                                matched_cluster = None
                                for cluster in clusters:
                                    anchor = cluster['anchor']
                                    if np.hypot(point[0] - anchor[0], point[1] - anchor[1]) < cluster_distance:
                                        matched_cluster = cluster
                                        break
                                if matched_cluster is None:
                                    clusters.append({'anchor': point, 'support_points': [point], 'best_score': score, 'source': template_name})
                                else:
                                    if score > float(matched_cluster['best_score']):
                                        matched_cluster['anchor'] = point
                                        matched_cluster['best_score'] = score
                                        matched_cluster['source'] = template_name
                                    support_points = matched_cluster['support_points']
                                    if any((np.hypot(point[0] - existing[0], point[1] - existing[1]) < support_merge_distance for existing in support_points)):
                                        continue
                                    else:
                                        support_points.append(point)
                        return [(cluster['anchor'], len(cluster['support_points']), float(cluster['best_score']), str(cluster['source'])) for cluster in clusters]
    def _detect_minimap_enemies_color(self, crop: np.ndarray, rect: tuple[int, int, int, int], profile: CalibrationProfile, *, include_broad_fallback: bool=False) -> list[tuple[int, int]]:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine._detect_minimap_enemies_color: Failure: Compilation Error
        color = profile.colors.get('minimap_enemy')
        if color is None:
            return []
        else:
            x0, y0, w, h = rect
            mask = self._build_minimap_enemy_red_mask(crop, profile, include_broad_fallback=include_broad_fallback)
            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            safe_margin = max(0, int(profile.thresholds.get('minimap_safe_margin_px', 8.0)))
            if safe_margin > 0 and w > safe_margin * 2 and (h > safe_margin * 2):
                        square_mask = np.zeros_like(mask)
                        cv2.rectangle(square_mask, (safe_margin, safe_margin), (w - safe_margin - 1, h - safe_margin - 1), 255, (-1))
                        mask = cv2.bitwise_and(mask, square_mask)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = profile.thresholds.get('minimap_enemy_min_area', 4)
            max_area = profile.thresholds.get('minimap_enemy_max_area', 28)
            min_circularity = profile.thresholds.get('minimap_enemy_circularity_threshold', 0.45)
            points = []
            for contour in contours:
                pass
        area = cv2.contourArea(contour)
        if not min_area <= area <= max_area:
            pass
        continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        else:
            circularity = float(4.0 * np.pi * area / (perimeter * perimeter))
            if circularity < min_circularity:
                continue
            else:
                moments = cv2.moments(contour)
                if moments['m00'] == 0:
                    continue
                else:
                    cx = int(moments['m10'] / moments['m00']) + x0
                    cy = int(moments['m01'] / moments['m00']) + y0
                    points.append((cx, cy))
        return points
    def _build_minimap_enemy_red_mask(self, crop: np.ndarray, profile: CalibrationProfile, *, include_broad_fallback: bool=False) -> np.ndarray:
        color = profile.colors.get('minimap_enemy')
        if color is None:
            return np.zeros(crop.shape[:2], dtype=np.uint8)
        else:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            lower = np.array(color.lower, dtype=np.uint8)
            upper = np.array(color.upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)
            if int(lower[0]) <= 10:
                wrap_lower = np.array([170, int(lower[1]), int(lower[2])], dtype=np.uint8)
                wrap_upper = np.array([180, int(upper[1]), int(upper[2])], dtype=np.uint8)
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, wrap_lower, wrap_upper))
            if include_broad_fallback and int(profile.thresholds.get('minimap_enemy_enable_broad_red_fallback', 1)) > 0:
                    red_s = int(profile.thresholds.get('minimap_enemy_broad_red_s_min', 90))
                    red_v = int(profile.thresholds.get('minimap_enemy_broad_red_v_min', 80))
                    red_h1_max = int(profile.thresholds.get('minimap_enemy_broad_red_h1_max', 14))
                    red_h2_min = int(profile.thresholds.get('minimap_enemy_broad_red_h2_min', 166))
                    broad_red_1 = cv2.inRange(hsv, np.array([0, red_s, red_v], dtype=np.uint8), np.array([red_h1_max, 255, 255], dtype=np.uint8))
                    broad_red_2 = cv2.inRange(hsv, np.array([red_h2_min, red_s, red_v], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8))
                    orange_h_min = int(profile.thresholds.get('minimap_enemy_broad_orange_h_min', 8))
                    orange_h_max = int(profile.thresholds.get('minimap_enemy_broad_orange_h_max', 26))
                    orange_s = int(profile.thresholds.get('minimap_enemy_broad_orange_s_min', 100))
                    orange_v = int(profile.thresholds.get('minimap_enemy_broad_orange_v_min', 90))
                    broad_orange = cv2.inRange(hsv, np.array([orange_h_min, orange_s, orange_v], dtype=np.uint8), np.array([orange_h_max, 255, 255], dtype=np.uint8))
                    mask = cv2.bitwise_or(mask, cv2.bitwise_or(cv2.bitwise_or(broad_red_1, broad_red_2), broad_orange))
            return mask
    def _prepare_minimap_enemy_mask(self, mask: np.ndarray, rect: tuple[int, int, int, int], profile: CalibrationProfile) -> np.ndarray:
        _x0, _y0, w, h = rect
        kernel = np.ones((3, 3), dtype=np.uint8)
        prepared = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        prepared = cv2.morphologyEx(prepared, cv2.MORPH_CLOSE, kernel, iterations=1)
        safe_margin = max(0, int(profile.thresholds.get('minimap_safe_margin_px', 8.0)))
        if safe_margin > 0 and w > safe_margin * 2 and (h > safe_margin * 2):
                    square_mask = np.zeros_like(prepared)
                    cv2.rectangle(square_mask, (safe_margin, safe_margin), (w - safe_margin - 1, h - safe_margin - 1), 255, (-1))
                    prepared = cv2.bitwise_and(prepared, square_mask)
        return prepared
    def _collect_minimap_enemy_components(self, mask: np.ndarray, *, min_area: float=1.0) -> list[dict[str, object]]:
        _, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
        components = []
        for index in range(1, stats.shape[0]):
            x, y, w, h, area = stats[index]
            if float(area) < min_area:
                continue
            else:
                components.append({'rect': (int(x), int(y), int(w), int(h)), 'area': float(area), 'center': (float(centroids[index][0]), float(centroids[index][1]))})
        return components
    def _estimate_minimap_enemy_stack_count(self, local_point: tuple[int, int], template_peak_count: int, red_components: list[dict[str, object]], crop_shape: tuple[int, int, int], profile: CalibrationProfile) -> int:
        radius = float(profile.thresholds.get('minimap_enemy_stack_group_radius_px', 16.0))
        stack_three_area = float(profile.thresholds.get('minimap_enemy_stack_three_area_px', 78.0))
        stack_two_area = float(profile.thresholds.get('minimap_enemy_stack_two_area_px', 68.0))
        edge_margin = float(profile.thresholds.get('minimap_enemy_stack_edge_margin_px', 18.0))
        px, py = local_point
        nearby_areas = []
        nearby_components = 0
        for component in red_components:
            x, y, w, h = component['rect']
            cx, cy = component['center']
            nearest_x = min(max(px, x), x + w - 1)
            nearest_y = min(max(py, y), y + h - 1)
            bbox_distance = float(np.hypot(px - nearest_x, py - nearest_y))
            center_distance = float(np.hypot(px - cx, py - cy))
            if bbox_distance <= radius or center_distance <= radius:
                nearby_components += 1
                nearby_areas.append(float(component['area']))
        combined_area = float(sum(nearby_areas))
        estimated = max(1, int(template_peak_count))
        if template_peak_count >= 2:
            if combined_area >= stack_three_area:
                estimated = max(estimated, 3)
            else:
                if combined_area >= stack_two_area:
                    estimated = max(estimated, 2)
        crop_h, crop_w = crop_shape[:2]
        near_edge = px <= edge_margin or py <= edge_margin or px >= crop_w - edge_margin or (py >= crop_h - edge_margin)
        if near_edge and template_peak_count >= 2 and (nearby_components >= 2):
                    estimated = max(estimated, 3)
        return min(estimated, 3)
    @staticmethod
    def _minimap_candidate_angle_deg(center: tuple[int, int], point: tuple[int, int]) -> float:
        dx = float(point[0] - center[0])
        dy = float(point[1] - center[1])
        return float((np.degrees(np.arctan2(dx, -dy)) + 360.0) % 360.0)
    def _build_minimap_enemy_candidate(self, center: tuple[int, int] | None, point: tuple[int, int], *, stack_count: int=1, template_score: float=0.0, source: str='color') -> MinimapEnemyCandidate:
        radius = 0.0
        angle_deg = 0.0
        if center is not None:
            radius = float(np.hypot(point[0] - center[0], point[1] - center[1]))
            angle_deg = self._minimap_candidate_angle_deg(center, point)
        return MinimapEnemyCandidate(point=point, radius=radius, angle_deg=angle_deg, stack_count=max(1, int(stack_count)), template_score=float(template_score), source=source)
    def _detect_minimap_enemy_candidates_from_crop(self, crop: np.ndarray, rect: tuple[int, int, int, int], center_px: tuple[int, int] | None, profile: CalibrationProfile) -> list[MinimapEnemyCandidate]:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine._detect_minimap_enemy_candidates_from_crop: Failure: Different control flow
        red_mask = self._prepare_minimap_enemy_mask(self._build_minimap_enemy_red_mask(crop, profile, include_broad_fallback=False), rect, profile)
        red_components = self._collect_minimap_enemy_components(red_mask, min_area=1.0)
        template_clusters = self._detect_minimap_enemies_template(crop, rect, profile, red_mask=red_mask, red_components=red_components)
        color_points = self._detect_minimap_enemies_color(crop, rect, profile, include_broad_fallback=False)
        merge_distance = int(profile.thresholds.get('minimap_enemy_merge_distance_px', 8))
        candidates = []
        template_anchor_points = [anchor for anchor, _, _, _ in template_clusters]
        for anchor, peak_count, best_score, source in template_clusters:
            local_point = (anchor[0] - rect[0], anchor[1] - rect[1])
            stack_count = self._estimate_minimap_enemy_stack_count(local_point=local_point, template_peak_count=peak_count, red_components=red_components, crop_shape=crop.shape, profile=profile)
            candidates.append(self._build_minimap_enemy_candidate(center_px, anchor, stack_count=stack_count, template_score=best_score, source=source))
        color_points = self._dedupe_points(color_points, merge_distance)
        for point in color_points:
            if any((np.hypot(point[0] - anchor[0], point[1] - anchor[1]) < merge_distance for anchor in template_anchor_points)):
                continue
            else:
                candidates.append(self._build_minimap_enemy_candidate(center_px, point, stack_count=1, template_score=0.0, source='color'))
        fallback_enabled = int(profile.thresholds.get('minimap_enemy_component_fallback_enabled', 1)) > 0
        fallback_always = int(profile.thresholds.get('minimap_enemy_component_fallback_always', 0)) > 0
        fallback_trigger_count = max(0, int(profile.thresholds.get('minimap_enemy_broad_fallback_trigger_count', 1.0)))
        if fallback_enabled and (fallback_always or len(candidates) < fallback_trigger_count):
            if int(profile.thresholds.get('minimap_enemy_enable_broad_red_fallback', 1)) > 0:
                broad_mask = self._prepare_minimap_enemy_mask(self._build_minimap_enemy_red_mask(crop, profile, include_broad_fallback=True), rect, profile)
                red_components = self._collect_minimap_enemy_components(broad_mask, min_area=1.0)
            min_area = float(profile.thresholds.get('minimap_enemy_component_fallback_min_area', 3.0))
            max_area = float(profile.thresholds.get('minimap_enemy_component_fallback_max_area', 70.0))
            max_side = float(profile.thresholds.get('minimap_enemy_component_fallback_max_side_px', 18.0))
            max_aspect = float(profile.thresholds.get('minimap_enemy_component_fallback_max_aspect', 3.2))
            component_merge = int(profile.thresholds.get('minimap_enemy_component_fallback_merge_distance_px', merge_distance))
            max_fallback_points = max(1, int(profile.thresholds.get('minimap_enemy_component_fallback_max_points', 36.0)))
            existing_points = [candidate.point for candidate in candidates]
            for component in red_components:
                if len(candidates) >= max_fallback_points:
                    break
                x, y, w, h = component['rect']
                area = float(component['area'])
                if not min_area <= area <= max_area:
                        continue
                        if max(w, h) > max_side:
                            continue
                        else:
                            aspect = max(w / max(1, h), h / max(1, w))
                            if aspect > max_aspect:
                                continue
                            else:
                                cx, cy = component['center']
                                point = (rect[0] + int(round(cx)), rect[1] + int(round(cy)))
                                if any((np.hypot(point[0] - old[0], point[1] - old[1]) < component_merge for old in existing_points)):
                                    continue
                                else:
                                    existing_points.append(point)
                                    candidates.append(self._build_minimap_enemy_candidate(center_px, point, stack_count=1, template_score=0.0, source='red-component'))
                candidates.sort(key=lambda item: (item.radius, item.angle_deg, item.point[1], item.point[0]))
                max_candidates = max(1, int(profile.thresholds.get('minimap_enemy_candidate_max_count', 80.0)))
                if len(candidates) > max_candidates:
                    candidates = candidates[:max_candidates]
                return candidates
    def detect_minimap_enemy_candidates(self, frame: np.ndarray, profile: CalibrationProfile) -> list[MinimapEnemyCandidate]:
        zone = self._crop_zone(frame, profile, 'minimap_region')
        if zone is None:
            return []
        else:
            crop, rect = zone
            center_spec = profile.points.get('minimap_center')
            center_px = center_spec.as_pixels(profile.screen_size) if center_spec else None
            return self._detect_minimap_enemy_candidates_from_crop(crop, rect, center_px, profile)
    @staticmethod
    def _normalize_vector(x: float, y: float) -> tuple[float, float] | None:
        norm = float(np.hypot(x, y))
        if norm <= 1e-06:
            return None
        else:
            return (x / norm, y / norm)
    @staticmethod
    def _vector_to_cardinal(vector: tuple[float, float] | None) -> str | None:
        if vector is None:
            return None
        else:
            x, y = vector
            if abs(x) <= 1e-06 and abs(y) <= 1e-06:
                    return None
            angle = (np.degrees(np.arctan2(x, -y)) + 360.0) % 360.0
            sectors = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
            index = int((angle + 22.5) % 360.0 // 45.0)
            return sectors[index]
    @staticmethod
    def _circular_smooth(values: np.ndarray, radius: int) -> np.ndarray:
        if radius <= 0 or values.size == 0:
            return values.astype(np.float32, copy=True)
        else:
            kernel = np.ones(radius * 2 + 1, dtype=np.float32)
            padded = np.concatenate([values[-radius:], values, values[:radius]]).astype(np.float32, copy=False)
            smoothed = np.convolve(padded, kernel / kernel.sum(), mode='same')
            return smoothed[radius:-radius]
    @staticmethod
    def _angle_delta(angles: np.ndarray, center_angle: float) -> np.ndarray:
        return np.arctan2(np.sin(angles - center_angle), np.cos(angles - center_angle))
    def _build_minimap_heading_mask(self, crop: np.ndarray, cx: int, cy: int, profile: CalibrationProfile) -> np.ndarray:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        value_min = int(profile.thresholds.get('minimap_heading_value_min', 135))
        sat_min = int(profile.thresholds.get('minimap_heading_sat_min', 12))
        sat_max = int(profile.thresholds.get('minimap_heading_sat_max', 170))
        hue_min = int(profile.thresholds.get('minimap_heading_hue_min', 28))
        hue_max = int(profile.thresholds.get('minimap_heading_hue_max', 110))
        radius_min = float(profile.thresholds.get('minimap_heading_radius_min_px', 6))
        radius_max = float(profile.thresholds.get('minimap_heading_radius_max_px', 42))
        base_y_tolerance = int(profile.thresholds.get('minimap_heading_base_y_tolerance_px', 10))
        fill_mask = cv2.inRange(hsv, np.array([hue_min, sat_min, value_min], dtype=np.uint8), np.array([hue_max, sat_max, 255], dtype=np.uint8))
        heading_color = profile.colors.get('minimap_heading')
        if heading_color is not None:
            fill_mask = cv2.bitwise_or(fill_mask, self._hsv_mask(crop, heading_color))
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edge_low = int(profile.thresholds.get('minimap_heading_edge_canny_low', 32))
        edge_high = int(profile.thresholds.get('minimap_heading_edge_canny_high', 96))
        edge_mask = cv2.Canny(gray, edge_low, edge_high)
        support_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        support_mask = cv2.dilate(fill_mask, support_kernel, iterations=1)
        edge_mask = cv2.bitwise_and(edge_mask, support_mask)
        edge_mask = cv2.dilate(edge_mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
        mask = cv2.bitwise_or(fill_mask, edge_mask)
        yy, xx = np.indices(crop.shape[:2], dtype=np.float32)
        radius = np.hypot(xx - float(cx), yy - float(cy))
        geometry_mask = (radius >= radius_min) & (radius <= radius_max)
        mask = np.where(geometry_mask, mask, 0).astype(np.uint8)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        return mask
    def _find_minimap_heading_tip(self, mask: np.ndarray, cx: int, cy: int, profile: CalibrationProfile) -> tuple[tuple[int, int] | None, float]:
        ys, xs = np.where(mask > 0)
        if xs.size == 0:
            return (None, 0.0)
        else:
            radius_min = float(profile.thresholds.get('minimap_heading_radius_min_px', 6))
            radius_max = float(profile.thresholds.get('minimap_heading_radius_max_px', 42))
            min_pixels = int(profile.thresholds.get('minimap_heading_min_pixels', 12))
            base_max_radius = float(profile.thresholds.get('minimap_heading_base_max_radius_px', 16))
            tip_min_radius = float(profile.thresholds.get('minimap_heading_tip_min_radius_px', 16))
            tip_max_radius = float(profile.thresholds.get('minimap_heading_tip_max_radius_px', radius_max))
            tip_min_up = float(profile.thresholds.get('minimap_heading_tip_min_up_px', 10))
            row_min_span = int(profile.thresholds.get('minimap_heading_row_min_span_px', 12))
            row_min_pixels = int(profile.thresholds.get('minimap_heading_row_min_pixels', 2))
            expected_span = float(profile.thresholds.get('minimap_heading_expected_span_px', 24))
            component_min_area = int(profile.thresholds.get('minimap_heading_component_min_area', 18))
            far_band_px = float(profile.thresholds.get('minimap_heading_far_band_px', 7))
            far_band_ratio = float(profile.thresholds.get('minimap_heading_far_band_ratio', 0.18))
            bins = max(36, int(profile.thresholds.get('minimap_heading_angle_bins', 72)))
            smooth_bins = max(1, int(profile.thresholds.get('minimap_heading_smooth_bins', 2)))
            sector_half_angle_deg = float(profile.thresholds.get('minimap_heading_sector_half_angle_deg', 30))
            max_sector_half_angle_deg = float(profile.thresholds.get('minimap_heading_max_sector_half_angle_deg', sector_half_angle_deg * 1.6))
            focus_half_angle_deg = float(profile.thresholds.get('minimap_heading_focus_half_angle_deg', 12))
            sector_edge_ratio = float(profile.thresholds.get('minimap_heading_sector_edge_ratio', 0.42))
            peak_ratio_threshold = float(profile.thresholds.get('minimap_heading_peak_ratio_threshold', 1.35))
            dx = xs.astype(np.float32) - float(cx)
            dy_up = float(cy) - ys.astype(np.float32)
            radius = np.hypot(dx, dy_up)
            valid = np.logical_and(radius >= radius_min, radius <= radius_max)
            if np.count_nonzero(valid) < min_pixels:
                return (None, 0.0)
            else:
                xs = xs[valid]
                ys = ys[valid]
                dx = dx[valid]
                dy_up = dy_up[valid]
                radius = radius[valid]
                angles = np.arctan2(dy_up, dx)
                weights = radius / max(radius_max, 1.0)
                weights = 0.25 + weights
                angle_norm = (angles + np.pi) / (2.0 * np.pi)
                bin_indices = np.floor(angle_norm * bins).astype(np.int32)
                bin_indices = np.clip(bin_indices, 0, bins - 1)
                support = np.bincount(bin_indices, weights=weights, minlength=bins).astype(np.float32)
                smoothed = self._circular_smooth(support, smooth_bins)
                sector_half_bins = max(1, int(round(sector_half_angle_deg / 360.0 * bins)))
                sector_scores = self._circular_smooth(smoothed, sector_half_bins)
                best_bin = int(np.argmax(sector_scores))
                best_peak = float(sector_scores[best_bin])
                baseline = float(np.median(sector_scores))
                peak_ratio = best_peak / max(baseline, 1e-06)
                if best_peak <= 0.0 or peak_ratio < peak_ratio_threshold:
                    return (None, 0.0)
                else:
                    center_angle = (best_bin + 0.5) / bins * (2.0 * np.pi) - np.pi
                    sector_cutoff = max(baseline, float(smoothed[best_bin]) * sector_edge_ratio)
                    max_sector_half_bins = max(1, int(round(max_sector_half_angle_deg / 360.0 * bins)))
                    left_bins = 0
                    while left_bins < max_sector_half_bins:
                        idx = (best_bin - left_bins - 1) % bins
                        if float(smoothed[idx]) < sector_cutoff:
                            break
                        left_bins += 1
                    right_bins = 0
                    while right_bins < max_sector_half_bins:
                        idx = (best_bin + right_bins + 1) % bins
                        if float(smoothed[idx]) < sector_cutoff:
                            break
                        right_bins += 1
                    actual_half_angle = max(np.deg2rad(10.0), (max(left_bins, right_bins) + 1) * (2.0 * np.pi / bins))
                    angle_delta = np.abs(self._angle_delta(angles, center_angle))
                    sector_pixels = angle_delta <= actual_half_angle
                    if np.count_nonzero(sector_pixels) < min_pixels:
                        return (None, 0.0)
                    else:
                        sector_xs = xs[sector_pixels]
                        sector_ys = ys[sector_pixels]
                        sector_radius = radius[sector_pixels]
                        sector_delta = angle_delta[sector_pixels]
                        sector_mask = np.zeros_like(mask, dtype=np.uint8)
                        sector_mask[sector_ys, sector_xs] = 255
                        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(sector_mask, connectivity=8)
                        axis_forward = np.array([np.cos(center_angle), np.sin(center_angle)], dtype=np.float32)
                        best_tip = None
                        best_confidence = 0.0
                        best_score = float('-inf')
                        best_span = 0.0
                        best_component_min_radius = float('inf')
                        for label in range(1, num_labels):
                            area = int(stats[label, cv2.CC_STAT_AREA])
                            if area < component_min_area:
                                continue
                            else:
                                component_pixels = labels == label
                                comp_ys, comp_xs = np.where(component_pixels)
                                if comp_xs.size < min_pixels:
                                    continue
                                else:
                                    comp_dx = comp_xs.astype(np.float32) - float(cx)
                                    comp_dy_up = float(cy) - comp_ys.astype(np.float32)
                                    comp_radius = np.hypot(comp_dx, comp_dy_up)
                                    valid_component = np.logical_and(comp_radius >= radius_min, comp_radius <= radius_max)
                                    if np.count_nonzero(valid_component) < min_pixels:
                                        continue
                                    else:
                                        comp_xs = comp_xs[valid_component]
                                        comp_ys = comp_ys[valid_component]
                                        comp_dx = comp_dx[valid_component]
                                        comp_dy_up = comp_dy_up[valid_component]
                                        comp_radius = comp_radius[valid_component]
                                        component_min_radius = float(np.min(comp_radius))
                                        if component_min_radius > base_max_radius:
                                            continue
                                        else:
                                            comp_weights = np.power(np.maximum(comp_radius, 1.0), 1.35)
                                            weighted_axis = np.array([float(np.sum(comp_dx * comp_weights)), float(np.sum(comp_dy_up * comp_weights))], dtype=np.float32)
                                            if float(np.dot(weighted_axis, axis_forward)) < 0.0:
                                                weighted_axis *= (-1.0)
                                            axis = self._normalize_vector(float(weighted_axis[0]), float(weighted_axis[1]))
                                            if axis is None:
                                                continue
                                            else:
                                                perpendicular = np.array([-axis[1], axis[0]], dtype=np.float32)
                                                projection = comp_dx * axis[0] + comp_dy_up * axis[1]
                                                lateral = comp_dx * perpendicular[0] + comp_dy_up * perpendicular[1]
                                                max_projection = float(np.max(projection))
                                                if max_projection < tip_min_radius:
                                                    continue
                                                else:
                                                    projection_min = float(np.min(projection))
                                                    projection_range = max(0.0, max_projection - projection_min)
                                                    band_size = max(far_band_px, projection_range * far_band_ratio)
                                                    far_band = projection >= max_projection - band_size
                                                    if np.count_nonzero(far_band) < max(row_min_pixels * 2, min_pixels // 3):
                                                        focus_half_angle = min(actual_half_angle * 0.45, np.deg2rad(focus_half_angle_deg))
                                                        component_angles = np.arctan2(comp_dy_up, comp_dx)
                                                        component_delta = np.abs(self._angle_delta(component_angles, center_angle))
                                                        far_band = component_delta <= max(focus_half_angle, np.deg2rad(6.0))
                                                    if np.count_nonzero(far_band) == 0:
                                                        continue
                                                    else:
                                                        far_projection = projection[far_band]
                                                        far_lateral = lateral[far_band]
                                                        lateral_span = float(np.max(far_lateral) - np.min(far_lateral))
                                                        if lateral_span < row_min_span:
                                                            continue
                                                        else:
                                                            band_weights = np.maximum(1.0, far_projection - (max_projection - band_size) + 1.0)
                                                            mid_projection = float(np.average(far_projection, weights=band_weights))
                                                            mid_lateral = float(np.min(far_lateral) + np.max(far_lateral)) * 0.5
                                                            tip_dx = axis[0] * mid_projection + perpendicular[0] * mid_lateral
                                                            tip_dy_up = axis[1] * mid_projection + perpendicular[1] * mid_lateral
                                                            if np.hypot(tip_dx, tip_dy_up) < tip_min_radius:
                                                                continue
                                                            else:
                                                                if tip_dy_up == 0.0 and abs(tip_dx) < 1.0:
                                                                        continue
                                                                tip_x = int(round(float(cx) + tip_dx))
                                                                tip_y = int(round(float(cy) - tip_dy_up))
                                                                if tip_x < 0 or tip_x >= mask.shape[1] or tip_y < 0 or (tip_y >= mask.shape[0]):
                                                                    continue
                                                                else:
                                                                    anchor_conf = 1.0 - min(1.0, component_min_radius / max(base_max_radius, 1.0))
                                                                    peak_conf = min(1.0, max(0.0, (peak_ratio - 1.0) / max(peak_ratio_threshold - 1.0, 1e-06)))
                                                                    span_conf = min(1.0, lateral_span / max(expected_span, 1.0))
                                                                    extension_conf = min(1.0, max_projection / max(tip_max_radius, 1.0))
                                                                    band_conf = min(1.0, float(np.count_nonzero(far_band)) / max(float(min_pixels), 1.0))
                                                                    confidence = 0.24 * peak_conf + 0.24 * anchor_conf + 0.22 * span_conf + 0.18 * extension_conf + 0.12 * band_conf
                                                                    component_score = max_projection * 3.0 + lateral_span * 2.2 + area * 0.2 + anchor_conf * 30.0
                                                                    if component_score > best_score:
                                                                        best_score = component_score
                                                                        best_tip = (tip_x, tip_y)
                                                                        best_confidence = float(confidence)
                                                                        best_span = lateral_span
                                                                        best_component_min_radius = component_min_radius
                        if best_tip is None:
                            focus_half_angle = min(actual_half_angle * 0.45, np.deg2rad(focus_half_angle_deg))
                            focused = sector_delta <= max(focus_half_angle, np.deg2rad(6.0))
                            if np.count_nonzero(focused) < max(4, min_pixels // 2):
                                focused = np.ones(sector_delta.shape, dtype=bool)
                            focus_xs = sector_xs[focused]
                            focus_ys = sector_ys[focused]
                            focus_radius = sector_radius[focused]
                            if focus_xs.size == 0:
                                return (None, 0.0)
                            else:
                                focus_weights = np.power(focus_radius, 1.3)
                                best_tip = (int(round(float(np.average(focus_xs, weights=focus_weights)))), int(round(float(np.average(focus_ys, weights=focus_weights)))))
                                best_span = row_min_span
                                best_component_min_radius = float(np.min(focus_radius))
                                sector_fraction = float(np.count_nonzero(sector_pixels)) / float(max(1, radius.size))
                                expected_fraction = sector_half_angle_deg * 2.0 / 360.0
                                fraction_conf = 1.0 - min(1.0, abs(sector_fraction - expected_fraction) / max(expected_fraction, 1e-06))
                                peak_conf = min(1.0, max(0.0, (peak_ratio - 1.0) / max(peak_ratio_threshold - 1.0, 1e-06)))
                                span_conf = min(1.0, best_span / max(expected_span, 1.0))
                                base_conf = 1.0 - min(1.0, best_component_min_radius / max(base_max_radius, 1.0))
                                best_confidence = float(0.4 * peak_conf + 0.25 * fraction_conf + 0.25 * span_conf + 0.1 * base_conf)
                        return (best_tip, best_confidence)
    def detect_minimap_enemies(self, frame: np.ndarray, profile: CalibrationProfile) -> list[tuple[int, int]]:
        candidates = self.detect_minimap_enemy_candidates(frame, profile)
        expanded_points = []
        max_expanded = max(1, int(profile.thresholds.get('minimap_enemy_expanded_max_count', 120.0)))
        for candidate in candidates:
            for _ in range(max(1, candidate.stack_count)):
                if len(expanded_points) >= max_expanded:
                    break
                else:
                    expanded_points.append(candidate.point)
            if len(expanded_points) >= max_expanded:
                break
        return sorted(expanded_points, key=lambda p: (p[1], p[0]))
    def detect_minimap_heading(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[tuple[float, float] | None, tuple[int, int] | None, float]:
        zone = self._crop_zone(frame, profile, 'minimap_region')
        center_spec = profile.points.get('minimap_center')
        center_px = center_spec.as_pixels(profile.screen_size) if center_spec else None
        if zone is None or center_px is None:
            return (None, None, 0.0)
        else:
            crop, rect = zone
            return self._detect_minimap_heading_from_crop(crop, rect, center_px, profile)
    def _detect_minimap_heading_from_crop(self, crop: np.ndarray, rect: tuple[int, int, int, int], center_px: tuple[int, int] | None, profile: CalibrationProfile) -> tuple[tuple[float, float] | None, tuple[int, int] | None, float]:
        if center_px is None:
            return (None, None, 0.0)
        else:
            x0, y0, _, _ = rect
            cx = center_px[0] - x0
            cy = center_px[1] - y0
            if cx < 0 or cy < 0 or cx >= crop.shape[1] or (cy >= crop.shape[0]):
                return (None, None, 0.0)
            else:
                mask = self._build_minimap_heading_mask(crop, cx, cy, profile)
                heading_tip_local, confidence = self._find_minimap_heading_tip(mask, cx, cy, profile)
                if heading_tip_local is None:
                    return (None, None, confidence)
                else:
                    heading_tip = (x0 + heading_tip_local[0], y0 + heading_tip_local[1])
                    direction = self._normalize_vector(float(heading_tip_local[0] - cx), float(heading_tip_local[1] - cy))
                    if direction is None:
                        return (None, heading_tip, confidence)
                    else:
                        confidence_threshold = float(profile.thresholds.get('minimap_heading_confidence_threshold', 0.18))
                        if confidence < confidence_threshold:
                            return (None, heading_tip, confidence)
                        else:
                            return (direction, heading_tip, confidence)
    def analyze_minimap_fast_region(self, minimap_crop: np.ndarray, rect: tuple[int, int, int, int], profile: CalibrationProfile, *, timestamp: float | None=None, processing_ms: float=0.0, tick_hz: float=0.0) -> MinimapFastSnapshot:
        center_spec = profile.points.get('minimap_center')
        center_px = center_spec.as_pixels(profile.screen_size) if center_spec else None
        candidates = self._detect_minimap_enemy_candidates_from_crop(minimap_crop, rect, center_px, profile)
        enemies = []
        max_expanded = max(1, int(profile.thresholds.get('minimap_enemy_expanded_max_count', 120.0)))
        for candidate in candidates:
            for _ in range(max(1, candidate.stack_count)):
                if len(enemies) >= max_expanded:
                    break
                else:
                    enemies.append(candidate.point)
            if len(enemies) >= max_expanded:
                break
        heading_vector, heading_tip, heading_confidence = self._detect_minimap_heading_from_crop(minimap_crop, rect, center_px, profile)
        nearby_enemy_count, nearest_enemy_distance = self.compute_minimap_metrics(enemies, profile)
        return MinimapFastSnapshot(timestamp=time.monotonic() if timestamp is None else float(timestamp), minimap_enemies=enemies, minimap_enemy_candidates=candidates, minimap_heading_vector=heading_vector, minimap_heading_tip=heading_tip, minimap_heading_confidence=float(heading_confidence), nearby_enemy_count=int(nearby_enemy_count), nearest_enemy_distance=nearest_enemy_distance, processing_ms=float(processing_ms), tick_hz=float(tick_hz))
    def detect_target_locked(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[bool, float, float, float]:
        zone = self._crop_zone(frame, profile, 'aim_region')
        target_color = profile.colors.get('reticle_target')
        if zone is None or target_color is None:
            return (False, 0.0, 0.0, 0.0)
        else:
            crop, _ = zone
            red_ratio = self._mask_ratio(crop, target_color)
            idle_color = profile.colors.get('reticle_idle')
            idle_ratio = self._mask_ratio(crop, idle_color) if idle_color is not None else 0.0
            threshold = profile.thresholds.get('reticle_red_ratio_threshold', 0.03)
            margin = profile.thresholds.get('reticle_target_margin', 0.008)
            confidence = red_ratio - idle_ratio if idle_color is not None else red_ratio
            locked = red_ratio >= threshold and confidence >= margin
            return (locked, red_ratio, idle_ratio, confidence)
    def detect_presence(self, frame: np.ndarray, profile: CalibrationProfile, zone_name: str) -> PresenceReading:
        zone = self._crop_zone(frame, profile, zone_name)
        if zone is None:
            return PresenceReading(present=False, edge_ratio=0.0, sat_ratio=0.0)
        else:
            crop, _ = zone
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 160)
            edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            sat_ratio = float(np.count_nonzero(hsv[:, :, 1] > 60)) / float(hsv.shape[0] * hsv.shape[1])
            threshold = profile.thresholds.get(f'{zone_name}_edge_ratio_threshold', profile.thresholds.get('presence_edge_ratio_threshold', 0.015))
            sat_multiplier = profile.thresholds.get(f'{zone_name}_sat_multiplier', 2.0)
            presence_mask = np.logical_or(edges > 0, hsv[:, :, 1] > 60)
            active_pixels = int(np.count_nonzero(presence_mask))
            vertical_ratio = None
            lower_ratio = 0.0
            if active_pixels > 0:
                row_energy = np.count_nonzero(presence_mask, axis=1).astype(np.float32)
                row_indices = np.arange(presence_mask.shape[0], dtype=np.float32)
                total_energy = float(row_energy.sum())
                if total_energy > 0:
                    denom = max(1, presence_mask.shape[0] - 1)
                    vertical_ratio = float(np.dot(row_energy, row_indices) / total_energy / denom)
                    lower_start = presence_mask.shape[0] // 2
                    lower_ratio = float(row_energy[lower_start:].sum()) / total_energy
            present = edge_ratio >= threshold or sat_ratio >= threshold * sat_multiplier
            return PresenceReading(present=present, edge_ratio=edge_ratio, sat_ratio=sat_ratio, vertical_ratio=vertical_ratio, lower_ratio=lower_ratio)
    def _combat_hp_bar_mask(self, image_bgr: np.ndarray, profile: CalibrationProfile) -> np.ndarray:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        calibrated_color = profile.colors.get('combat_hp_bar_color')
        if calibrated_color is not None:
            lower_h = int(calibrated_color.lower[0])
            upper_h = int(calibrated_color.upper[0])
            lower_s = int(calibrated_color.lower[1])
            lower_v = int(calibrated_color.lower[2])
            upper_s = int(calibrated_color.upper[1])
            upper_v = int(calibrated_color.upper[2])
            masks = []
            masks.append(cv2.inRange(hsv, np.array([lower_h, lower_s, lower_v], dtype=np.uint8), np.array([upper_h, upper_s, upper_v], dtype=np.uint8)))
            if upper_h <= 20:
                mirrored_low = max(0, 180 - upper_h)
                masks.append(cv2.inRange(hsv, np.array([mirrored_low, lower_s, lower_v], dtype=np.uint8), np.array([180, upper_s, upper_v], dtype=np.uint8)))
            else:
                if lower_h >= 160:
                    mirrored_high = min(20, 180 - lower_h)
                    masks.append(cv2.inRange(hsv, np.array([0, lower_s, lower_v], dtype=np.uint8), np.array([mirrored_high, upper_s, upper_v], dtype=np.uint8)))
            mask = masks[0]
            for extra_mask in masks[1:]:
                mask = cv2.bitwise_or(mask, extra_mask)
            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            return mask
        else:
            sat_min = int(profile.thresholds.get('combat_hp_bar_sat_min', 110))
            val_min = int(profile.thresholds.get('combat_hp_bar_val_min', 90))
            low_h_max = int(profile.thresholds.get('combat_hp_bar_low_h_max', 10))
            high_h_min = int(profile.thresholds.get('combat_hp_bar_high_h_min', 170))
            red_mask_low = cv2.inRange(hsv, np.array([0, sat_min, val_min], dtype=np.uint8), np.array([low_h_max, 255, 255], dtype=np.uint8))
            red_mask_high = cv2.inRange(hsv, np.array([high_h_min, sat_min, val_min], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8))
            mask = cv2.bitwise_or(red_mask_low, red_mask_high)
            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            return mask
    def _detect_hp_bar_candidates(self, frame: np.ndarray, profile: CalibrationProfile) -> list[HpBarCandidate]:
        zone = self._crop_zone(frame, profile, 'hp_bars_region')
        if zone is None:
            return []
        else:
            crop, zone_rect = zone
            zone_x, zone_y, _, _ = zone_rect
            mask = self._combat_hp_bar_mask(crop, profile)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = profile.thresholds.get('combat_hp_bar_min_area', 160)
            min_width = profile.thresholds.get('combat_hp_bar_min_width_px', 40)
            min_height = profile.thresholds.get('combat_hp_bar_min_height_px', 8)
            max_width = profile.thresholds.get('combat_hp_bar_max_width_px', 180)
            max_height = profile.thresholds.get('combat_hp_bar_max_height_px', 26)
            min_aspect_ratio = profile.thresholds.get('combat_hp_bar_min_aspect_ratio', 3.4)
            max_aspect_ratio = profile.thresholds.get('combat_hp_bar_max_aspect_ratio', 16.0)
            min_fill_ratio = profile.thresholds.get('combat_hp_bar_min_fill_ratio', 0.18)
            candidates = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                else:
                    x, y, w, h = cv2.boundingRect(contour)
                    if w < min_width or w > max_width or h < min_height or (h > max_height):
                        continue
                    else:
                        aspect_ratio = float(w) / float(max(1, h))
                        fill_ratio = float(area) / float(max(1, w * h))
                        if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio or fill_ratio < min_fill_ratio:
                            continue
                        else:
                            candidates.append(HpBarCandidate(rect=(zone_x + x, zone_y + y, w, h), local_rect=(x, y, w, h), area=float(area)))
            candidates.sort(key=lambda candidate: (candidate.rect[1], candidate.rect[0]))
            return candidates
    def detect_hp_bar_layout(self, hp_bar_candidates: list[HpBarCandidate], profile: CalibrationProfile) -> tuple[float | None, float]:
        zone_spec = profile.zones.get('hp_bars_region')
        zone_rect = zone_spec.as_pixels(profile.screen_size) if zone_spec else None
        if zone_rect is None or not hp_bar_candidates:
            return (None, 0.0)
        else:
            _, zone_y, _, zone_h = zone_rect
            zone_mid_y = zone_y + zone_h * 0.5
            weighted_vertical = 0.0
            total_weight = 0.0
            lower_weight = 0.0
            for candidate in hp_bar_candidates:
                _, global_y, _, h = candidate.rect
                center_y = global_y + h / 2.0
                weighted_vertical += center_y * candidate.area
                total_weight += candidate.area
                if center_y >= zone_mid_y:
                    lower_weight += candidate.area
            if total_weight <= 0.0:
                return (None, 0.0)
            else:
                vertical_ratio = (weighted_vertical / total_weight - zone_y) / float(max(1, zone_h - 1))
                lower_ratio = lower_weight / total_weight
                return (float(vertical_ratio), float(lower_ratio))
    def detect_enemy_hp_targets(self, profile: CalibrationProfile, hp_bar_candidates: list[HpBarCandidate]) -> list[EnemyHpTarget]:
        aim_spec = profile.zones.get('aim_region')
        aim_rect = aim_spec.as_pixels(profile.screen_size) if aim_spec else None
        aim_center = None
        if aim_rect is not None:
            ax, ay, aw, ah = aim_rect
            aim_center = (ax + aw // 2, ay + ah // 2)
        anchor_offset_y = int(profile.thresholds.get('combat_hp_anchor_offset_y_px', profile.thresholds.get('combat_hp_anchor_max_offset_px', 40)))
        hp_targets = []
        for candidate in hp_bar_candidates:
            x, y, w, h = candidate.rect
            anchor_point = (x + w // 2, y + h + anchor_offset_y)
            distance_to_aim = None
            if aim_center is not None:
                distance_to_aim = float(np.hypot(anchor_point[0] - aim_center[0], anchor_point[1] - aim_center[1]))
            hp_targets.append(EnemyHpTarget(hp_bar_rect=candidate.rect, anchor_point=anchor_point, distance_to_aim=distance_to_aim))
        hp_targets.sort(key=lambda target: (float('inf') if target.distance_to_aim is None else target.distance_to_aim, target.anchor_point[1], target.anchor_point[0]))
        return hp_targets
    def _refine_enemy_body_rect(self, frame: np.ndarray, profile: CalibrationProfile, hp_bar_rect: tuple[int, int, int, int], estimated_point: tuple[int, int], expected_width: int) -> tuple[int, int, int, int] | None:
        bar_x, bar_y, bar_w, bar_h = hp_bar_rect
        half_width = int(profile.thresholds.get('combat_body_search_half_width_px', 90))
        search_gap = int(profile.thresholds.get('combat_body_search_start_gap_px', 18))
        search_height = int(profile.thresholds.get('combat_body_search_height_px', 220))
        rect = self._clamp_rect((estimated_point[0] - half_width, bar_y + bar_h + search_gap, half_width * 2, search_height), frame.shape)
        search_x, search_y, search_w, search_h = rect
        search = frame[search_y:search_y + search_h, search_x:search_x + search_w]
        if search.size == 0:
            return None
        else:
            hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
            dark_v_max = int(profile.thresholds.get('combat_body_dark_value_max', 82))
            dark_s_max = int(profile.thresholds.get('combat_body_dark_sat_max', 165))
            dark_mask = np.logical_and(hsv[:, :, 2] <= dark_v_max, hsv[:, :, 1] <= dark_s_max).astype(np.uint8) * 255
            edge = cv2.Canny(gray, 45, 135)
            mask = cv2.bitwise_or(dark_mask, edge)
            kernel = np.ones((5, 5), dtype=np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = float(profile.thresholds.get('combat_body_min_area', 900))
            min_height = int(profile.thresholds.get('combat_body_min_height_px', 70))
            min_width = int(profile.thresholds.get('combat_body_min_width_px', 32))
            max_width = int(profile.thresholds.get('combat_body_max_width_px', 220))
            best_rect = None
            best_score = None
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                else:
                    x, y, w, h = cv2.boundingRect(contour)
                    if h < min_height or w < min_width or w > max_width:
                        continue
                    else:
                        global_rect = (search_x + x, search_y + y, w, h)
                        center_x = global_rect[0] + w / 2.0
                        torso_y = global_rect[1] + h * profile.thresholds.get('combat_body_anchor_height_ratio', 0.36)
                        x_penalty = abs(center_x - estimated_point[0])
                        y_penalty = abs(torso_y - estimated_point[1])
                        width_penalty = abs(w - expected_width) * 0.45
                        score = x_penalty + y_penalty * 0.65 + width_penalty - area * 0.01
                        if best_score is None or score < best_score:
                            best_score = score
                            best_rect = global_rect
            return best_rect
    def detect_enemy_body_targets(self, frame: np.ndarray, profile: CalibrationProfile, hp_bar_candidates: list[HpBarCandidate]) -> list[EnemyBodyTarget]:
        aim_spec = profile.zones.get('aim_region')
        aim_rect = aim_spec.as_pixels(profile.screen_size) if aim_spec else None
        aim_center = None
        if aim_rect is not None:
            ax, ay, aw, ah = aim_rect
            aim_center = (ax + aw // 2, ay + ah // 2)
        body_targets = []
        base_offset = int(profile.thresholds.get('combat_body_offset_base_px', 88))
        far_scale = int(profile.thresholds.get('combat_body_offset_far_scale_px', 62))
        fallback_height = int(profile.thresholds.get('combat_body_rect_height_px', 150))
        width_ratio = float(profile.thresholds.get('combat_body_rect_width_ratio', 0.58))
        min_width = int(profile.thresholds.get('combat_body_min_width_px', 32))
        anchor_ratio = float(profile.thresholds.get('combat_body_anchor_height_ratio', 0.36))
        x_bias = int(profile.thresholds.get('combat_body_offset_x_px', 0))
        allow_fallback = bool(profile.thresholds.get('combat_body_allow_fallback', 0.0))
        for candidate in hp_bar_candidates:
            x, y, w, h = candidate.rect
            y_ratio = (y + h * 0.5) / float(max(1, profile.screen_height - 1))
            body_offset = int(round(base_offset + far_scale * (1.0 - y_ratio)))
            body_width = max(min_width, int(round(w * width_ratio)))
            estimated_point = (x + w // 2 + x_bias, y + h + body_offset)
            refined_rect = self._refine_enemy_body_rect(frame=frame, profile=profile, hp_bar_rect=candidate.rect, estimated_point=estimated_point, expected_width=body_width)
            if refined_rect is None and (not allow_fallback):
                    continue
            if refined_rect is None:
                body_rect = self._clamp_rect((estimated_point[0] - body_width // 2, estimated_point[1] - int(fallback_height * anchor_ratio), body_width, fallback_height), frame.shape)
            else:
                body_rect = refined_rect
            bx, by, bw, bh = body_rect
            body_point = (bx + bw // 2, by + bh // 2)
            distance_to_aim = None
            if aim_center is not None:
                distance_to_aim = float(np.hypot(body_point[0] - aim_center[0], body_point[1] - aim_center[1]))
            body_targets.append(EnemyBodyTarget(hp_bar_rect=candidate.rect, body_rect=body_rect, body_point=body_point, distance_to_aim=distance_to_aim))
        body_targets.sort(key=lambda target: (float('inf') if target.distance_to_aim is None else target.distance_to_aim, target.body_point[1], target.body_point[0]))
        return body_targets
    def estimate_stamina_ratio(self, frame: np.ndarray, profile: CalibrationProfile) -> float | None:
        zone = self._crop_zone(frame, profile, 'stamina_region')
        full_color = profile.colors.get('stamina_full')
        if zone is None or full_color is None:
            return None
        else:
            crop, _ = zone
            full_mask = self._hsv_mask(crop, full_color)
            full_per_column = np.mean(full_mask > 0, axis=0)
            filled_columns = np.where(full_per_column > 0.15)[0]
            if len(filled_columns) == 0:
                return 0.0
            else:
                return float(filled_columns[(-1)] + 1) / float(crop.shape[1])
    def detect_compass_marker(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[int, int] | None:
        zone = self._crop_zone(frame, profile, 'compass_marker_region')
        color = profile.colors.get('compass_marker')
        if zone is None or color is None:
            return None
        else:
            crop, rect = zone
            x0, y0, _, _ = rect
            mask = self._hsv_mask(crop, color)
            mask = cv2.GaussianBlur(mask, (5, 5), 0)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best = None
            best_area = 0.0
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > best_area:
                    best_area = area
                    best = contour
            if best is None:
                return None
            else:
                moments = cv2.moments(best)
                if moments['m00'] == 0:
                    return None
                else:
                    cx = int(moments['m10'] / moments['m00']) + x0
                    cy = int(moments['m01'] / moments['m00']) + y0
                    return (cx, cy)
    def compute_minimap_metrics(self, enemies: list[tuple[int, int]], profile: CalibrationProfile) -> tuple[int, float | None]:
        center_spec = profile.points.get('minimap_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        if center is None or not enemies:
            return (0, None)
        else:
            combat_distance = profile.thresholds.get('combat_minimap_confirm_distance_px', 72)
            distances = [float(np.hypot(enemy[0] - center[0], enemy[1] - center[1])) for enemy in enemies]
            nearby_enemy_count = sum((dist <= combat_distance for dist in distances))
            nearest_enemy_distance = min(distances) if distances else None
            return (nearby_enemy_count, nearest_enemy_distance)
    def read_minimap_coordinates(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[int | None, int | None, int | None]:
        explicit_values = self._read_minimap_coordinates_explicit(frame, profile)
        if explicit_values[0] is not None and explicit_values[2] is not None:
            return explicit_values
        else:
            strong_x, strong_z = self.read_minimap_xz_strong(frame, profile)
            if strong_x is not None and strong_z is not None:
                y_value = explicit_values[1]
                if y_value is None:
                    y_zone = self._crop_zone(frame, profile, 'minimap_coord_y_region')
                    if y_zone is not None:
                        try:
                            y_value = self._read_coord_line_expanded(frame, y_zone[1], allow_negative=True, min_digits=2, profile=profile, axis_name='y')
                        except Exception:
                            self.logger.exception('Strong Y read failed')
                            y_value = None
                return (strong_x, y_value, strong_z)
            else:
                minimap_zone = self._crop_zone(frame, profile, 'minimap_region')
                if minimap_zone is None:
                    return (None, None, None)
                else:
                    crop, _ = minimap_zone
                    h, w = crop.shape[:2]
                    x_ratio = float(profile.thresholds.get('minimap_coords_region_x_ratio', 0.6))
                    y_ratio = float(profile.thresholds.get('minimap_coords_region_y_ratio', 0.62))
                    w_ratio = float(profile.thresholds.get('minimap_coords_region_w_ratio', 0.4))
                    h_ratio = float(profile.thresholds.get('minimap_coords_region_h_ratio', 0.38))
                    rx = max(0, min(w - 1, int(round(w * x_ratio))))
                    ry = max(0, min(h - 1, int(round(h * y_ratio))))
                    rw = max(1, min(w - rx, int(round(w * w_ratio))))
                    rh = max(1, min(h - ry, int(round(h * h_ratio))))
                    region = crop[ry:ry + rh, rx:rx + rw].copy()
                    template_values = self._read_minimap_coordinates_template(region)
                    if template_values[0] is not None and template_values[2] is not None:
                        return template_values
                    else:
                        if not self.ocr_enabled:
                            return template_values
                        else:
                            scale = float(profile.thresholds.get('minimap_coords_ocr_scale', 4.0))
                            min_conf_lines = int(profile.thresholds.get('minimap_coords_min_lines', 3.0))
                            variants = []
                            try:
                                gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                                gray = cv2.GaussianBlur(gray, (3, 3), 0)
                            except Exception:
                                self.logger.exception('Failed to prepare minimap coordinate OCR region')
                                return template_values
                            variants.append(gray)
                            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                            variants.append(thresh)
                            variants.append(cv2.bitwise_not(thresh))
                            best_values = (None, None, None)
                            best_score = (-1.0)
                            for image in variants:
                                for psm in [6, 11]:
                                    try:
                                        text = pytesseract.image_to_string(image, config=f'--oem 3 --psm {psm} -c tessedit_char_whitelist=-0123456789')
                                    except Exception as exc:
                                        tesseract_not_found = getattr(pytesseract, 'TesseractNotFoundError', None)
                                        if tesseract_not_found is not None and isinstance(exc, tesseract_not_found):
                                            self.ocr_enabled = False
                                            if not self._ocr_missing_logged:
                                                self.logger.warning('Tesseract not found; disabling OCR text search until restart')
                                                self._ocr_missing_logged = True
                                            return (None, None, None)
                                        else:
                                            raise
                                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                                    values = []
                                    negative_bonus = 0.0
                                    for line in lines:
                                        compact = line.replace(' ', '')
                                        match = re.search('-?\\d+', compact)
                                        if not match:
                                            continue
                                        else:
                                            token = match.group(0)
                                            if token.startswith('-'):
                                                negative_bonus = 0.25
                                            try:
                                                values.append(int(token))
                                            except ValueError:
                                                pass
                                    score = float(len(values)) + negative_bonus
                                    if score > best_score:
                                        best_score = score
                                        if len(values) >= min_conf_lines:
                                            self._update_coord_templates_from_text(region, [str(values[0]), str(values[1]), str(values[2])])
                                            best_values = (values[0], values[1], values[2])
                                        else:
                                            if len(values) == 2:
                                                best_values = (values[0], values[1], None)
                                    if len(values) >= min_conf_lines and negative_bonus > 0.0:
                                        self._update_coord_templates_from_text(region, [str(values[0]), str(values[1]), str(values[2])])
                                        return (values[0], values[1], values[2])
                                    else:
                                        if len(values) >= min_conf_lines and best_score >= min_conf_lines + 0.2:
                                            self._update_coord_templates_from_text(region, [str(values[0]), str(values[1]), str(values[2])])
                                            return (values[0], values[1], values[2])
                            return best_values if best_values!= (None, None, None) else template_values
    def _read_minimap_coordinates_explicit(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[int | None, int | None, int | None]:
        x_zone = self._crop_zone(frame, profile, 'minimap_coord_x_region')
        z_zone = self._crop_zone(frame, profile, 'minimap_coord_z_region')
        if x_zone is None or z_zone is None:
            return (None, None, None)
        else:
            x_region = self._expanded_coord_region(frame, x_zone[1], profile, 'x')
            z_region = self._expanded_coord_region(frame, z_zone[1], profile, 'z')
            if x_region is not None and z_region is not None:
                rapid_x, rapid_x_score, rapid_z, rapid_z_score = self.read_coordinate_pair_rapidocr(x_region, z_region)
            else:
                rapid_x, rapid_x_score, rapid_z, rapid_z_score = (None, 0.0, None, 0.0)
            if rapid_x is not None and rapid_z is not None and (rapid_x_score >= 0.94) and (rapid_z_score >= 0.94):
                x_value = rapid_x
                z_value = rapid_z
            else:
                x_value = self._read_coord_line_expanded(frame, x_zone[1], allow_negative=False, min_digits=4, profile=profile, axis_name='x')
                z_value = self._read_coord_line_expanded(frame, z_zone[1], allow_negative=True, min_digits=4, profile=profile, axis_name='z')
            if x_value is None or z_value is None:
                return (None, None, None)
            else:
                y_value = None
                y_zone = self._crop_zone(frame, profile, 'minimap_coord_y_region')
                if y_zone is not None:
                    y_value = self._read_coord_line_expanded(frame, y_zone[1], allow_negative=True, min_digits=2, profile=profile, axis_name='y')
                return (x_value, y_value, z_value)
    @staticmethod
    def _coord_normalize_glyph(glyph: np.ndarray, size: tuple[int, int]=(18, 26)) -> np.ndarray:
        mask = (glyph > 0).astype(np.uint8) * 255
        ys, xs = np.where(mask > 0)
        if ys.size == 0 or xs.size == 0:
            return np.zeros((size[1], size[0]), dtype=np.uint8)
        else:
            x0, x1 = (int(xs.min()), int(xs.max()) + 1)
            y0, y1 = (int(ys.min()), int(ys.max()) + 1)
            cropped = mask[y0:y1, x0:x1]
            padded = cv2.copyMakeBorder(cropped, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
            return cv2.resize(padded, size, interpolation=cv2.INTER_NEAREST)
    @staticmethod
    def _coord_prepare_gray_source(region: np.ndarray) -> np.ndarray | None:
        if region is None:
            return None
        try:
            prepared = np.ascontiguousarray(region)
        except Exception:
            return None
        if prepared.size == 0:
            return None
        if prepared.dtype!= np.uint8:
            if not np.issubdtype(prepared.dtype, np.number):
                return None
            else:
                prepared = np.clip(prepared, 0, 255).astype(np.uint8)
        if prepared.ndim == 2:
            return prepared
        else:
            if prepared.ndim == 3:
                if prepared.shape[2] == 1:
                    return prepared[:, :, 0]
                else:
                    if prepared.shape[2] >= 4:
                        return cv2.cvtColor(prepared[:, :, :4], cv2.COLOR_BGRA2GRAY)
                    else:
                        if prepared.shape[2] >= 3:
                            return cv2.cvtColor(prepared[:, :, :3], cv2.COLOR_BGR2GRAY)
            return None
    @staticmethod
    def _coord_score_glyph(glyph: np.ndarray, template: np.ndarray) -> float:
        glyph_mask = glyph > 0
        template_mask = template > 0
        union = np.count_nonzero(glyph_mask | template_mask)
        if union <= 0:
            return 0.0
        else:
            intersection = np.count_nonzero(glyph_mask & template_mask)
            return float(intersection) / float(union)
    @staticmethod
    def _coord_glyph_features(raw_glyph: np.ndarray, normalized: np.ndarray) -> dict[str, float]:
        # ***<module>.VisionEngine._coord_glyph_features: Failure: Compilation Error
        mask = (normalized > 0).astype(np.float32)
        h, w = mask.shape[:2]
        top_rows = max(1, int(round(h * 0.18)))
        bottom_rows = max(1, int(round(h * 0.18)))
        side_cols = max(1, int(round(w * 0.28)))
        center_half = max(1, int(round(w * 0.12)))
        center_start = max(0, w // 2 - center_half)
        center_end = min(w, w // 2 + center_half + 1)
        upper_end = max(1, int(round(h * 0.42)))
        lower_start = max(0, int(round(h * 0.58)))
        left_end = max(1, int(round(w * 0.42)))
        right_start = min(w - 1, int(round(w * 0.58)))
        active_cols = np.count_nonzero(np.any(mask > 0, axis=0)) / max(1, w)
        return {'aspect': float(raw_glyph.shape[1]) / float(max(1, raw_glyph.shape[0])), 'top_fill': float(np.mean(mask[:top_rows, :])), 'bottom_fill': float(np.mean(mask[:, w - side_cols:])), 'left_fill': float(np.mean(mask[:upper_end, :left_end])), 'right_fill': float(np.mean(mask[lower_start:, :left_end])), 'center_fill': float(np.mean(mask[lower_start:, right_start:])), 'upper_left_fill': float(np.mean(mask[lower_start:, right_start:])), 'upper_right_fill': float(np.mean(mask[lower_start:, right_start:])), 'lower_left_fill': float(np.mean(mask[lower_start:, right_start:])), 'lower_right_fill': float(np.mean(mask[lower_start:, right_start:])), 'active_cols':
            pass
    @staticmethod
    def _coord_char_heuristic_bonus(char: str, features: dict[str, float]) -> float:
        if char == '1':
            return max(0.0, 0.5 - features['top_fill']) * 0.22 + max(0.0, features['center_fill'] - 0.22) * 0.2 + max(0.0, 0.48 - features['aspect']) * 0.16 + max(0.0, 0.52 - features['active_cols']) * 0.14
        else:
            if char == '7':
                return max(0.0, features['top_fill'] - 0.34) * 0.24 + max(0.0, features['aspect'] - 0.34) * 0.18 + max(0.0, features['right_fill'] - features['left_fill']) * 0.1
            else:
                if char == '0':
                    return max(0.0, features['bottom_fill'] - 0.16) * 0.18 + max(0.0, 0.16 - features['center_fill']) * 0.14 + max(0.0, 0.08 - abs(features['left_fill'] - features['right_fill'])) * 0.2
                else:
                    if char == '9':
                        return max(0.0, features['upper_right_fill'] - 0.16) * 0.16 + max(0.0, features['right_fill'] - features['left_fill']) * 0.14 + max(0.0, 0.14 - features['lower_left_fill']) * 0.22
                    else:
                        if char == '2':
                            return max(0.0, features['bottom_fill'] - 0.16) * 0.18 + max(0.0, features['lower_left_fill'] - 0.08) * 0.16 + max(0.0, 0.1 - features['upper_left_fill']) * 0.08
                        else:
                            if char == '3':
                                return max(0.0, features['right_fill'] - features['left_fill']) * 0.18 + max(0.0, 0.1 - features['lower_left_fill']) * 0.16 + max(0.0, features['upper_right_fill'] - 0.16) * 0.08
                            else:
                                if char == '8':
                                    return max(0.0, features['top_fill'] - 0.2) * 0.12 + max(0.0, features['bottom_fill'] - 0.18) * 0.12 + max(0.0, features['left_fill'] - 0.12) * 0.12 + max(0.0, features['right_fill'] - 0.12) * 0.12 + max(0.0, features['center_fill'] - 0.16) * 0.14
                                else:
                                    return 0.0
    def _coord_choose_best_char(self, raw_glyph: np.ndarray, normalized: np.ndarray, allow_negative: bool) -> tuple[str | None, float]:
        features = self._coord_glyph_features(raw_glyph, normalized)
        scored_chars = []
        for char, templates in self._coord_template_bank.items():
            if char == '-' and (not allow_negative):
                    continue
            score = max((self._coord_score_glyph(normalized, template) for template in templates), default=0.0)
            score += self._coord_char_heuristic_bonus(char, features)
            scored_chars.append((score, char))
        if not scored_chars:
            return (None, 0.0)
        scored_chars.sort(key=lambda item: item[0], reverse=True)
        best_score, best_char = scored_chars[0]
        if len(scored_chars) >= 2:
            second_score, second_char = scored_chars[1]
            if {best_char, second_char} == {'1', '7'} and abs(best_score - second_score) <= 0.08:
                one_score = next((score for score, char in scored_chars if char == '1'))
                seven_score = next((score for score, char in scored_chars if char == '7'))
                if seven_score > one_score:
                    return ('7', seven_score)
                else:
                    return ('1', one_score)
            else:
                if {best_char, second_char} == {'0', '9'} and abs(best_score - second_score) <= 0.08:
                    zero_score = next((score for score, char in scored_chars if char == '0'))
                    nine_score = next((score for score, char in scored_chars if char == '9'))
                    if nine_score > zero_score:
                        return ('9', nine_score)
                    else:
                        return ('0', zero_score)
                else:
                    if {best_char, second_char} == {'2', '3'} and abs(best_score - second_score) <= 0.08:
                        two_score = next((score for score, char in scored_chars if char == '2'))
                        three_score = next((score for score, char in scored_chars if char == '3'))
                        if three_score > two_score:
                            return ('3', three_score)
                        else:
                            return ('2', two_score)
                    else:
                        if {best_char, second_char} == {'1', '8'} and abs(best_score - second_score) <= 0.1:
                            if features['top_fill'] >= 0.18 and features['bottom_fill'] >= 0.16 and (features['left_fill'] >= 0.1) and (features['right_fill'] >= 0.1):
                                eight_score = next((score for score, char in scored_chars if char == '8'))
                                return ('8', eight_score)
                            else:
                                one_score = next((score for score, char in scored_chars if char == '1'))
                                return ('1', one_score)
                        else:
                            if {best_char, second_char} == {'7', '8'} and abs(best_score - second_score) <= 0.1:
                                if features['left_fill'] >= 0.11 and features['bottom_fill'] >= 0.15:
                                    eight_score = next((score for score, char in scored_chars if char == '8'))
                                    return ('8', eight_score)
                                else:
                                    seven_score = next((score for score, char in scored_chars if char == '7'))
                                    return ('7', seven_score)
        return (best_char, float(best_score))
    def _coord_prepare_text_region(self, region: np.ndarray) -> np.ndarray:
        if region is None or region.size == 0 or region.ndim!= 3 or (region.shape[0] <= 1) or (region.shape[1] <= 1) or (region.shape[2] < 3):
            return np.zeros((1, 1), dtype=np.uint8)
        else:
            text_start = max(0, int(round(region.shape[1] * 0.55)))
            top_start = max(0, int(round(region.shape[0] * 0.44)))
            text_region = region[top_start:, text_start:].copy()
            if text_region.size == 0:
                return np.zeros((1, 1), dtype=np.uint8)
            else:
                try:
                    gray = self._coord_prepare_gray_source(text_region)
                    if gray is None or gray.size == 0:
                        return np.zeros((1, 1), dtype=np.uint8)
                    else:
                        _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
                        return binary
                except Exception:
                    self.logger.exception('Failed to prepare coordinate text region')
                    return np.zeros((1, 1), dtype=np.uint8)
    def _coord_prepare_single_line_region(self, region: np.ndarray) -> np.ndarray:
        if region.size == 0 or region.shape[0] <= 1 or region.shape[1] <= 1:
            return np.zeros((1, 1), dtype=np.uint8)
        else:
            try:
                gray = self._coord_prepare_gray_source(region)
                if gray is None or gray.size == 0:
                    return np.zeros((1, 1), dtype=np.uint8)
                else:
                    gray = cv2.GaussianBlur(gray, (3, 3), 0)
                    _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
            except Exception:
                self.logger.exception('Failed to prepare single coordinate line region')
                return np.zeros((1, 1), dtype=np.uint8)
            rows = np.count_nonzero(binary > 0, axis=1)
            cols = np.count_nonzero(binary > 0, axis=0)
            if np.any(rows > 0):
                ys = np.where(rows > 0)[0]
                y0 = max(0, int(ys.min()) - 2)
                y1 = min(binary.shape[0], int(ys.max()) + 3)
                binary = binary[y0:y1, :]
            if np.any(cols > 0):
                xs = np.where(cols > 0)[0]
                x0 = max(0, int(xs.min()) - 2)
                x1 = min(binary.shape[1], int(xs.max()) + 3)
                binary = binary[:, x0:x1]
            return binary
    def _coord_prepare_single_line_variants(self, region: np.ndarray) -> list[np.ndarray]:
        if region.size == 0 or region.shape[0] <= 1 or region.shape[1] <= 1:
            return [np.zeros((1, 1), dtype=np.uint8)]
        else:
            try:
                gray = self._coord_prepare_gray_source(region)
                if gray is None or gray.size == 0:
                    return [np.zeros((1, 1), dtype=np.uint8)]
                else:
                    blur = cv2.GaussianBlur(gray, (3, 3), 0)
                    variants = []
                    _, binary_fixed = cv2.threshold(blur, 120, 255, cv2.THRESH_BINARY)
                    variants.append(binary_fixed)
                    _, binary_otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    variants.append(binary_otsu)
                    variants.append(cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 5))
            except Exception:
                self.logger.exception('Failed to prepare coordinate line variants')
                return [self._coord_prepare_single_line_region(region)]
            prepared = []
            seen_signatures = set()
            for binary in variants:
                rows = np.count_nonzero(binary > 0, axis=1)
                cols = np.count_nonzero(binary > 0, axis=0)
                cropped = binary
                if np.any(rows > 0):
                    ys = np.where(rows > 0)[0]
                    y0 = max(0, int(ys.min()) - 2)
                    y1 = min(binary.shape[0], int(ys.max()) + 3)
                    cropped = cropped[y0:y1, :]
                if np.any(cols > 0):
                    xs = np.where(cols > 0)[0]
                    x0 = max(0, int(xs.min()) - 2)
                    x1 = min(cropped.shape[1], int(xs.max()) + 3)
                    cropped = cropped[:, x0:x1]
                signature = (cropped.shape[0], cropped.shape[1], int(np.count_nonzero(cropped)))
                if signature in seen_signatures:
                    continue
                else:
                    seen_signatures.add(signature)
                    prepared.append(cropped)
            return prepared or [self._coord_prepare_single_line_region(region)]
    @staticmethod
    def _coord_extract_glyphs_from_binary(binary: np.ndarray) -> list[np.ndarray]:
        cols = np.count_nonzero(binary > 0, axis=0)
        segments = []
        active = False
        start = 0
        for idx, value in enumerate(cols):
            if value >= 2 and (not active):
                start = idx
                active = True
            else:
                if value < 2 and active:
                        end = idx - 1
                        if end - start + 1 >= 2:
                            segments.append((start, end))
                        active = False
        if active:
            end = len(cols) - 1
            if end - start + 1 >= 2:
                segments.append((start, end))
        glyphs = []
        for x0, x1 in segments:
            if x1 - x0 + 1 <= 2 and x0 >= int(round(binary.shape[1] * 0.88)):
                    continue
            glyph = binary[:, max(0, x0 - 1):min(binary.shape[1], x1 + 2)]
            glyphs.append(glyph)
        return glyphs
    @staticmethod
    def _coord_merge_glyph_pair(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        height = max(left.shape[0], right.shape[0])
        width = left.shape[1] + right.shape[1] + 1
        merged = np.zeros((height, width), dtype=np.uint8)
        left_y = max(0, (height - left.shape[0]) // 2)
        right_y = max(0, (height - right.shape[0]) // 2)
        merged[left_y:left_y + left.shape[0], 0:left.shape[1]] = left
        start_x = left.shape[1] + 1
        merged[right_y:right_y + right.shape[0], start_x:start_x + right.shape[1]] = right
        return merged
    def _coord_reduce_glyph_count(self, glyphs: list[np.ndarray], target_count: int) -> list[np.ndarray]:
        reduced = [glyph.copy() for glyph in glyphs]
        while len(reduced) > target_count:
            best_idx = 0
            best_cost = float('inf')
            for idx in range(len(reduced) - 1):
                left = reduced[idx]
                right = reduced[idx + 1]
                cost = float(left.shape[1] + right.shape[1])
                if cost < best_cost:
                    best_cost = cost
                    best_idx = idx
            merged = self._coord_merge_glyph_pair(reduced[best_idx], reduced[best_idx + 1])
            reduced = reduced[:best_idx] + [merged] + reduced[best_idx + 2:]
        return reduced
    def _coord_extract_line_glyphs(self, region: np.ndarray) -> list[list[np.ndarray]]:
        binary = self._coord_prepare_text_region(region)
        rows = np.count_nonzero(binary > 0, axis=1)
        bands = []
        active = False
        start = 0
        for idx, value in enumerate(rows):
            if value >= 4 and (not active):
                start = idx
                active = True
            else:
                if value < 4 and active:
                        end = idx - 1
                        if end - start + 1 >= 7:
                            bands.append((start, end))
                        active = False
        if active:
            end = len(rows) - 1
            if end - start + 1 >= 7:
                bands.append((start, end))
        if len(bands) > 3:
            bands = bands[(-3):]
        line_glyphs = []
        for y0, y1 in bands:
            line = binary[max(0, y0 - 1):min(binary.shape[0], y1 + 2), :]
            glyphs = self._coord_extract_glyphs_from_binary(line)
            if glyphs:
                line_glyphs.append(glyphs)
        return line_glyphs
    def _read_coord_line_template(self, region: np.ndarray, allow_negative: bool, min_digits: int) -> int | None:
        value, _score = self._read_coord_line_template_scored(region, allow_negative=allow_negative, min_digits=min_digits)
        return value
    def _read_coord_line_template_scored(self, region: np.ndarray, allow_negative: bool, min_digits: int) -> tuple[int | None, float]:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine._read_coord_line_template_scored: Failure: Compilation Error
        self._load_coord_templates()
        if not self._coord_template_bank:
            return (None, 0.0)
            target_max_count = min_digits + (1 if allow_negative else 0)
            min_score_threshold = 0.48
            token_votes = {}
            for binary in self._coord_prepare_single_line_variants(region):
                glyphs = self._coord_extract_glyphs_from_binary(binary)
                if not glyphs:
                    continue
                else:
                    if len(glyphs) > target_max_count:
                        glyphs = self._coord_reduce_glyph_count(glyphs, target_max_count)
                    chars = []
                    glyph_scores = []
                    variant_failed = False
                    for glyph in glyphs:
                        normalized = self._coord_normalize_glyph(glyph)
                        best_char, char_score = self._coord_choose_best_char(glyph, normalized, allow_negative=allow_negative)
                        if best_char is None or char_score < min_score_threshold:
                            variant_failed = True
                            break
                        else:
                            chars.append(best_char)
                            glyph_scores.append(char_score)
                    if variant_failed:
                        continue
                    else:
                        token = ''.join(chars)
                        if token.count('-') > 1 or ('-' in token and (not token.startswith('-'))):
                            continue
                        else:
                            if len(token.lstrip('-')) < min_digits:
                                continue
                            else:
                                score = float(sum(glyph_scores)) / float(max(1, len(glyph_scores)))
                                token_votes.setdefault(token, []).append(score)
            best_token = None
            best_vote_count = (-1)
            best_avg_score = 0.0
            for token, scores in token_votes.items():
                vote_count = len(scores)
                avg_score = float(sum(scores)) / float(max(1, vote_count))
                if vote_count > best_vote_count or (vote_count == best_vote_count and avg_score > best_avg_score):
                    best_token = token
                    best_vote_count = vote_count
                    best_avg_score = avg_score
            if best_token is None:
                return (None, 0.0)
                return (int(best_token), best_avg_score)
                    except ValueError:
                            return (None, 0.0)
            except Exception:
                self.logger.exception('Coordinate template scoring failed')
                    return (None, 0.0)
    def _read_coord_line_ocr_candidates(self, region: np.ndarray, allow_negative: bool, min_digits: int) -> list[tuple[int, float]]:
        if not self.ocr_enabled:
            return []
        else:
            try:
                gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                scale = 5.0
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                gray = cv2.GaussianBlur(gray, (3, 3), 0)
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 5)
            except Exception:
                self.logger.exception('Failed to prepare OCR coordinate candidates')
                return []
            variants = [thresh, cv2.bitwise_not(thresh), adaptive, cv2.bitwise_not(adaptive)]
            whitelist = '-0123456789' if allow_negative else '0123456789'
            candidates = []
            for image in variants:
                for psm in [7, 8, 13]:
                    try:
                        text = pytesseract.image_to_string(image, config=f'--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}')
                    except Exception as exc:
                        tesseract_not_found = getattr(pytesseract, 'TesseractNotFoundError', None)
                        if tesseract_not_found is not None and isinstance(exc, tesseract_not_found):
                            self.ocr_enabled = False
                            if not self._ocr_missing_logged:
                                self.logger.warning('Tesseract not found; disabling OCR text search until restart')
                                self._ocr_missing_logged = True
                            return []
                        else:
                            raise
                        return None
                    compact = re.sub('\\s+', '', text)
                    match = re.search('-?\\d+', compact)
                    if not match:
                        continue
                    else:
                        token = match.group(0)
                        if not allow_negative and token.startswith('-'):
                                token = token.lstrip('-')
                        if len(token.lstrip('-')) < min_digits:
                            continue
                        else:
                            try:
                                value = int(token)
                            except ValueError:
                                continue
                            score = float(len(token.lstrip('-'))) + (0.05 if token.startswith('-') else 0.0)
                            candidates.append((value, score))
            return candidates
    def read_coordinate_line(self, region: np.ndarray, allow_negative: bool, min_digits: int) -> int | None:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine.read_coordinate_line: Failure: Compilation Error
        token_votes = {}
        value, score = self._read_coord_line_template_scored(region, allow_negative=allow_negative, min_digits=min_digits)
        if value is not None:
            token_votes.setdefault(str(value), []).append(score + 0.35)
        for ocr_value, ocr_score in self._read_coord_line_ocr_candidates(region, allow_negative=allow_negative, min_digits=min_digits):
            token_votes.setdefault(str(ocr_value), []).append(ocr_score)
        if not token_votes:
            return self._read_coord_line_ocr_fallback(region, allow_negative=allow_negative, min_digits=min_digits)
            best_token = None
            best_vote_count = (-1)
            best_avg_score = 0.0
            for token, scores in token_votes.items():
                vote_count = len(scores)
                avg_score = float(sum(scores)) / float(max(1, vote_count))
                if vote_count > best_vote_count or (vote_count == best_vote_count and avg_score > best_avg_score):
                    best_token = token
                    best_vote_count = vote_count
                    best_avg_score = avg_score
            if best_token is None:
                return
                return int(best_token)
                    except ValueError:
                            return None
                except Exception:
                    self.logger.exception('Coordinate line read failed')
                        return None
    def read_minimap_xz_strong(self, frame: np.ndarray, profile: CalibrationProfile) -> tuple[int | None, int | None]:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine.read_minimap_xz_strong: Failure: Compilation Error
        x_zone = self._crop_zone(frame, profile, 'minimap_coord_x_region')
        z_zone = self._crop_zone(frame, profile, 'minimap_coord_z_region')
        if x_zone is None or z_zone is None:
            return (None, None)
        else:
            x_crop = self._expanded_coord_region(frame, x_zone[1], profile, 'x')
            z_crop = self._expanded_coord_region(frame, z_zone[1], profile, 'z')
            if x_crop is None or z_crop is None:
                return (None, None)
        x_value, x_score, z_value, z_score = self.read_coordinate_pair_rapidocr(x_crop, z_crop)
        if x_value is not None and z_value is not None and (x_score >= 0.995) and (z_score >= 0.995):
            return (x_value, z_value)
                except Exception:
                    self.logger.exception('Strong X/Z rapid read failed')
                        x_value, x_score = self._read_coord_line_template_scored(x_crop, allow_negative=False, min_digits=4)
                        z_value, z_score = self._read_coord_line_template_scored(z_crop, allow_negative=True, min_digits=4)
                        if x_value is not None and z_value is not None and (x_score >= 0.8) and (z_score >= 0.82):
                            return (x_value, z_value)
                                except Exception:
                                    self.logger.exception('Strong X/Z template read failed')
                                        x_value = self.read_coordinate_line(x_crop, allow_negative=False, min_digits=4)
                                        z_value = self.read_coordinate_line(z_crop, allow_negative=True, min_digits=4)
                                        if x_value is not None and z_value is not None:
                                            return (x_value, z_value)
                                                except Exception:
                                                    self.logger.exception('Strong X/Z fallback read failed')
                                                        return (None, None)
    def _ensure_rapid_ocr(self):
        if RapidOCR is None:
            return None
        else:
            if self._rapid_ocr is None:
                try:
                    self._rapid_ocr = RapidOCR()
                except Exception:
                    self.logger.exception('Failed to initialize RapidOCR')
                    self._rapid_ocr = False
            return None if self._rapid_ocr is False else self._rapid_ocr
    @staticmethod
    def _prepare_coord_region_for_rapidocr(region: np.ndarray) -> np.ndarray | None:
        if region is None or region.size == 0:
            return None
        else:
            if region.ndim == 2:
                gray = region.copy()
            else:
                if region.ndim == 3 and region.shape[2] >= 3:
                    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                else:
                    return None
            gray = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return thresh
    @staticmethod
    def _parse_coordinate_token(text: str, allow_negative: bool, min_digits: int) -> int | None:
        compact = re.sub('\\s+', '', text)
        compact = compact.replace('—', '-').replace('–', '-')
        match = re.search('-?\\d+', compact)
        if not match:
            return None
        else:
            token = match.group(0)
            if not allow_negative and token.startswith('-'):
                    token = token.lstrip('-')
            if len(token.lstrip('-')) < min_digits:
                return None
            else:
                try:
                    return int(token)
                except ValueError:
                    return None
    def read_coordinate_pair_rapidocr(self, x_region: np.ndarray, z_region: np.ndarray) -> tuple[int | None, float, int | None, float]:
        # irreducible cflow, using cdg fallback
        # ***<module>.VisionEngine.read_coordinate_pair_rapidocr: Failure: Compilation Error
        engine = self._ensure_rapid_ocr()
        if engine is None:
            return (None, 0.0, None, 0.0)
        x_image = self._prepare_coord_region_for_rapidocr(x_region)
        z_image = self._prepare_coord_region_for_rapidocr(z_region)
        if x_image is None or z_image is None:
                return (None, 0.0, None, 0.0)
                width = max(x_image.shape[1], z_image.shape[1])
                def _pad(img: np.ndarray) -> np.ndarray:
                    # ***<module>.VisionEngine.read_coordinate_pair_rapidocr._pad: Failure detected at line number 1967 and instruction offset 16: Different bytecode
                    return cv2.copyMakeBorder(img, 10, 10, 20, max(20, width - img.shape[1] + 20), cv2.BORDER_CONSTANT, value=0)
                x_pad = _pad(x_image)
                z_pad = _pad(z_image)
                gap = np.zeros((20, x_pad.shape[1]), dtype=np.uint8)
                stacked = np.vstack([x_pad, gap, z_pad])
                result, _elapsed = engine(stacked)
                if not result:
                    return (None, 0.0, None, 0.0)
                    ordered = sorted(result, key=lambda item: min((point[1] for point in item[0])) if item and item[0] else 0.0)
                    x_value = None
                    x_score = 0.0
                    z_value = None
                    z_score = 0.0
                    for item in ordered:
                        if len(item) < 3:
                            continue
                        else:
                            text = str(item[1])
                            score = float(item[2])
                            top_y = min((point[1] for point in item[0])) if item[0] else 0.0
                            if top_y < x_pad.shape[0] + 5:
                                value = self._parse_coordinate_token(text, allow_negative=False, min_digits=4)
                                if value is not None and score > x_score:
                                        x_value = value
                                        x_score = score
                            else:
                                value = self._parse_coordinate_token(text, allow_negative=True, min_digits=4)
                                if value is not None and score > z_score:
                                        z_value = value
                                        z_score = score
                    return (x_value, x_score, z_value, z_score)
                    except Exception:
                        self.logger.exception('RapidOCR coordinate pair read failed')
                            return (None, 0.0, None, 0.0)
    def _read_coord_line_expanded(self, frame: np.ndarray, rect: tuple[int, int, int, int], allow_negative: bool, min_digits: int, profile: CalibrationProfile, axis_name: str) -> int | None:
        expand_left = int(profile.thresholds.get('minimap_coord_expand_left_px', 6.0))
        expand_right = int(profile.thresholds.get('minimap_coord_expand_right_px', 4.0))
        expand_y = int(profile.thresholds.get('minimap_coord_expand_y_px', 2.0))
        extra_left = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_left_px', expand_left))
        extra_right = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_right_px', expand_right))
        extra_y = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_y_px', expand_y))
        if axis_name == 'x':
            extra_left = max(extra_left, 30)
            extra_right = max(extra_right, 8)
        else:
            if axis_name == 'z':
                extra_left = max(extra_left, 18)
                extra_right = max(extra_right, 6)
        x, y, w, h = rect
        variants = [(0, 0, 0), (extra_left, 0, extra_y), (extra_left, extra_right, extra_y), (extra_left * 2, extra_right, extra_y), (extra_left * 3, extra_right * 2, extra_y), (max(extra_left * 4, 24), extra_right * 2, extra_y), (max(extra_left * 5, 32), max(extra_right * 3, 10), extra_y + 1)]
        best_value = None
        best_score = (-1.0)
        best_region = None
        for left_pad, right_pad, y_pad in variants:
            expanded_rect = self._clamp_rect((x - left_pad, y - y_pad, w + left_pad + right_pad, h + y_pad * 2), frame.shape)
            ex, ey, ew, eh = expanded_rect
            if ew <= 1 or eh <= 1:
                continue
            else:
                expanded_region = frame[ey:ey + eh, ex:ex + ew].copy()
                if expanded_region.size == 0:
                    continue
                else:
                    value, score = self._read_coord_line_template_scored(expanded_region, allow_negative=allow_negative, min_digits=min_digits)
                    if value is not None and score > best_score:
                        best_value = value
                        best_score = score
                        best_region = expanded_region
                    else:
                        if best_region is None:
                            best_region = expanded_region
        if best_value is not None:
            return best_value
        else:
            if best_region is None:
                return None
            else:
                return self._read_coord_line_ocr_fallback(best_region, allow_negative=allow_negative, min_digits=min_digits)
    def _expanded_coord_region(self, frame: np.ndarray, rect: tuple[int, int, int, int], profile: CalibrationProfile, axis_name: str) -> np.ndarray | None:
        expand_left = int(profile.thresholds.get('minimap_coord_expand_left_px', 6.0))
        expand_right = int(profile.thresholds.get('minimap_coord_expand_right_px', 4.0))
        expand_y = int(profile.thresholds.get('minimap_coord_expand_y_px', 2.0))
        extra_left = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_left_px', expand_left))
        extra_right = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_right_px', expand_right))
        extra_y = int(profile.thresholds.get(f'minimap_{axis_name}_coord_expand_y_px', expand_y))
        if axis_name == 'x':
            extra_left = max(extra_left, 30)
            extra_right = max(extra_right, 8)
        else:
            if axis_name == 'z':
                extra_left = max(extra_left, 18)
                extra_right = max(extra_right, 6)
        x, y, w, h = rect
        expanded_rect = self._clamp_rect((x - extra_left, y - extra_y, w + extra_left + extra_right, h + extra_y * 2), frame.shape)
        ex, ey, ew, eh = expanded_rect
        if ew <= 1 or eh <= 1:
            return None
        else:
            region = frame[ey:ey + eh, ex:ex + ew].copy()
            if region.size == 0:
                return None
            else:
                return region
    def _read_coord_line_ocr_fallback(self, region: np.ndarray, allow_negative: bool, min_digits: int) -> int | None:
        if not self.ocr_enabled:
            return None
        else:
            try:
                gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                scale = 5.0
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                gray = cv2.GaussianBlur(gray, (3, 3), 0)
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            except Exception:
                self.logger.exception('Failed to prepare OCR coordinate fallback')
                return None
            variants = [thresh, cv2.bitwise_not(thresh)]
            whitelist = '-0123456789' if allow_negative else '0123456789'
            best_value = None
            best_len = (-1)
            for image in variants:
                try:
                    text = pytesseract.image_to_string(image, config=f'--oem 3 --psm 7 -c tessedit_char_whitelist={whitelist}')
                except Exception as exc:
                    tesseract_not_found = getattr(pytesseract, 'TesseractNotFoundError', None)
                    if tesseract_not_found is not None and isinstance(exc, tesseract_not_found):
                        self.ocr_enabled = False
                        if not self._ocr_missing_logged:
                            self.logger.warning('Tesseract not found; disabling OCR text search until restart')
                            self._ocr_missing_logged = True
                        return
                    else:
                        raise
                compact = re.sub('\\s+', '', text)
                match = re.search('-?\\d+', compact)
                if not match:
                    continue
                else:
                    token = match.group(0)
                    if not allow_negative and token.startswith('-'):
                            token = token.lstrip('-')
                    if len(token.lstrip('-')) < min_digits:
                        continue
                    else:
                        try:
                            value = int(token)
                        except ValueError:
                            continue
                        token_len = len(token.lstrip('-'))
                        if token_len > best_len:
                            best_len = token_len
                            best_value = value
            return best_value
    def _register_coord_template(self, char: str, glyph: np.ndarray) -> None:
        if not char:
            return None
        else:
            normalized = self._coord_normalize_glyph(glyph)
            bucket = self._coord_template_bank.setdefault(char, [])
            for existing in bucket:
                if self._coord_score_glyph(normalized, existing) >= 0.97:
                    return
            bucket.append(normalized)
    def save_coord_template_cache(self) -> None:
        self._load_coord_templates()
        cache_path = self._resolve_base_dir() / 'logs' / 'coord_template_cache.json'
        payload = {}
        for char, templates in self._coord_template_bank.items():
            payload[char] = [template.astype(np.uint8).tolist() for template in templates]
        try:
            cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        except Exception:
            self.logger.exception('Failed to save coordinate template cache')
    def _load_coord_template_cache(self) -> None:
        cache_path = self._resolve_base_dir() / 'logs' / 'coord_template_cache.json'
        if not cache_path.exists():
            return None
        else:
            try:
                payload = json.loads(cache_path.read_text(encoding='utf-8'))
            except Exception:
                self.logger.exception('Failed to read coordinate template cache')
                return None
            if not isinstance(payload, dict):
                return None
            else:
                for char, templates in payload.items():
                    if not isinstance(char, str) or not isinstance(templates, list):
                        continue
                    else:
                        for template_rows in templates:
                            try:
                                template = np.array(template_rows, dtype=np.uint8)
                            except Exception:
                                continue
                            if template.ndim!= 2 or template.size == 0:
                                continue
                            else:
                                self._register_coord_template(char, template)
    def learn_coordinate_line_template(self, region: np.ndarray, expected_text: str) -> None:
        self._load_coord_templates()
        normalized_text = expected_text.strip()
        if not normalized_text:
            return None
        else:
            try:
                for binary in self._coord_prepare_single_line_variants(region):
                    glyphs = self._coord_extract_glyphs_from_binary(binary)
                    if len(glyphs) > len(normalized_text):
                        glyphs = self._coord_reduce_glyph_count(glyphs, len(normalized_text))
                    if len(glyphs)!= len(normalized_text):
                        continue
                    else:
                        for glyph, char in zip(glyphs, normalized_text):
                            self._register_coord_template(char, glyph)
            except Exception:
                self.logger.exception('Failed to learn coordinate line template for %s', normalized_text)
    def _load_coord_templates(self) -> None:
        if self._coord_templates_loaded:
            return None
        else:
            self._coord_templates_loaded = True
            base_dir = self._resolve_base_dir()
            references = [(base_dir / 'logs' / 'coord_debug_live.png', ['8628', '454', '-8497']), (base_dir / 'logs' / 'coord_verify_live.png', ['8520', '474', '-8439']), (base_dir / 'logs' / 'crop_from_coord_minimap_live.png', ['8329', '627', '-6649']), (base_dir / 'logs' / 'coord_live_now.png', ['8196', '506', '-7889']), (base_dir / 'logs' / 'coord_block_live.png', ['8533', '464', '-8070']), (base_dir / 'logs' / 'coord_live_debug_full.png', ['8514', '469', '-8041'])]
            for path, expected_lines in references:
                if not path.exists():
                    continue
                else:
                    image = cv2.imread(str(path))
                    if image is None:
                        continue
                    else:
                        self._update_coord_templates_from_text(image, expected_lines)
            line_references = [(base_dir / 'logs' / 'minimap_coord_x_region.png', '8533'), (base_dir / 'logs' / 'minimap_coord_y_region.png', '464'), (base_dir / 'logs' / 'minimap_coord_z_region.png', '-8070'), (base_dir / 'logs' / 'minimap_coord_x_region_live_debug.png', '8514'), (base_dir / 'logs' / 'minimap_coord_y_region_live_debug.png', '469'), (base_dir / 'logs' / 'minimap_coord_z_region_live_debug.png', '-8041')]
            for path, expected_text in line_references:
                if not path.exists():
                    continue
                else:
                    image = cv2.imread(str(path))
                    if image is None:
                        continue
                    else:
                        binary = self._coord_prepare_single_line_region(image)
                        glyphs = self._coord_extract_glyphs_from_binary(binary)
                        if len(glyphs) > len(expected_text):
                            glyphs = self._coord_reduce_glyph_count(glyphs, len(expected_text))
                        if len(glyphs)!= len(expected_text):
                            continue
                        else:
                            for glyph, char in zip(glyphs, expected_text):
                                self._register_coord_template(char, glyph)
            self._load_coord_template_cache()
    def _update_coord_templates_from_text(self, region: np.ndarray, expected_lines: list[str]) -> None:
        glyph_lines = self._coord_extract_line_glyphs(region)
        if not glyph_lines:
            return None
        else:
            for glyphs, text in zip(glyph_lines, expected_lines):
                if len(glyphs)!= len(text):
                    continue
                else:
                    for glyph, char in zip(glyphs, text):
                        self._register_coord_template(char, glyph)
    @staticmethod
    def _resolve_base_dir() -> 'Path':
        return Path(__file__).resolve().parents[2]
    def _read_minimap_coordinates_template(self, region: np.ndarray) -> tuple[int | None, int | None, int | None]:
        self._load_coord_templates()
        if not self._coord_template_bank:
            return (None, None, None)
        else:
            glyph_lines = self._coord_extract_line_glyphs(region)
            if len(glyph_lines)!= 3:
                return (None, None, None)
            else:
                lines = []
                min_score_threshold = 0.48
                for glyphs in glyph_lines:
                    chars = []
                    for glyph in glyphs:
                        normalized = self._coord_normalize_glyph(glyph)
                        best_char, best_score = self._coord_choose_best_char(glyph, normalized, allow_negative=True)
                        if best_char is None or best_score < min_score_threshold:
                            return (None, None, None)
                        else:
                            chars.append(best_char)
                    lines.append(''.join(chars))
                try:
                    x_value = int(lines[0])
                    y_value = int(lines[1])
                    z_value = int(lines[2])
                except ValueError:
                    return (None, None, None)
                if len(lines[0].lstrip('-')) < 4 or len(lines[2].lstrip('-')) < 4:
                    return (None, None, None)
                else:
                    return (x_value, y_value, z_value)
    def read_distance(self, frame: np.ndarray, profile: CalibrationProfile) -> int | None:
        if not self.ocr_enabled:
            return None
        else:
            marker = self.detect_compass_marker(frame, profile)
            center_spec = profile.points.get('compass_center')
            center = center_spec.as_pixels(profile.screen_size) if center_spec else None
            zone_spec = profile.zones.get('distance_region')
            if zone_spec is None:
                return None
            else:
                base_rect = zone_spec.as_pixels(profile.screen_size)
                if base_rect is None:
                    return None
                else:
                    base_rect = self._clamp_rect(base_rect, frame.shape)
                    candidate_rects = []
                    if marker is not None and center is not None:
                            offset_x = marker[0] - center[0]
                            offset_y = marker[1] - center[1]
                            centered_tolerance = int(profile.thresholds.get('distance_marker_center_tolerance_px', 64.0))
                            dynamic_max_shift_x = int(profile.thresholds.get('distance_region_dynamic_max_shift_x_px', max(160, centered_tolerance * 3)))
                            dynamic_max_shift_y = int(profile.thresholds.get('distance_region_dynamic_max_shift_y_px', 42.0))
                            dynamic_gain_x = float(profile.thresholds.get('distance_region_dynamic_follow_gain_x', 1.0))
                            dynamic_gain_y = float(profile.thresholds.get('distance_region_dynamic_follow_gain_y', 1.0))
                            shifted_rect = (base_rect[0] + int(round(max(-dynamic_max_shift_x, min(dynamic_max_shift_x, offset_x * dynamic_gain_x)))), base_rect[1] + int(round(max(-dynamic_max_shift_y, min(dynamic_max_shift_y, offset_y * dynamic_gain_y)))), base_rect[2], base_rect[3])
                            candidate_rects.append(self._clamp_rect(shifted_rect, frame.shape))
                    candidate_rects.append(base_rect)
                    expand_x = int(profile.thresholds.get('distance_region_expand_x_px', 18.0))
                    expand_y = int(profile.thresholds.get('distance_region_expand_y_px', 8.0))
                    unique_rects = []
                    for rect in candidate_rects:
                        expanded_rect = self._clamp_rect((rect[0] - expand_x, rect[1] - expand_y, rect[2] + expand_x * 2, rect[3] + expand_y * 2), frame.shape)
                        if expanded_rect not in unique_rects:
                            unique_rects.append(expanded_rect)
                    for rect in unique_rects:
                        x, y, w, h = rect
                        crop = frame[y:y + h, x:x + w].copy()
                        value = self._read_distance_from_crop(crop, profile)
                        if value is not None:
                            return value
    def _read_distance_from_crop(self, crop: np.ndarray, profile: CalibrationProfile) -> int | None:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        marker_color = profile.colors.get('compass_marker')
        if marker_color is not None:
            lower = np.array([max(0, marker_color.lower[0] - 8), max(0, marker_color.lower[1] - 80), max(0, marker_color.lower[2] - 80)], dtype=np.uint8)
            upper = np.array([min(179, marker_color.upper[0] + 8), 255, 255], dtype=np.uint8)
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            color_mask = cv2.inRange(hsv, lower, upper)
            color_mask = cv2.resize(color_mask, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
            color_mask = cv2.dilate(color_mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
            contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            boxes = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 20:
                    continue
                else:
                    x, y, w, h = cv2.boundingRect(contour)
                    boxes.append((x, y, w, h, area))
            boxes.sort(key=lambda item: item[0])
            if len(boxes) >= 2:
                last_box = boxes[(-1)]
                main_boxes = boxes[:(-1)]
                main_area = sum((box[4] for box in main_boxes))
                if main_boxes and last_box[4] <= main_area:
                        x1 = min((box[0] for box in main_boxes))
                        y1 = min((box[1] for box in main_boxes))
                        x2 = max((box[0] + box[2] for box in main_boxes))
                        y2 = max((box[1] + box[3] for box in main_boxes))
                        color_mask = color_mask[y1:y2, x1:x2]
        else:
            color_mask = None
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ocr_image = thresh
        if color_mask is not None and np.count_nonzero(color_mask) >= 12:
                ocr_image = color_mask
        ocr_image = cv2.copyMakeBorder(ocr_image, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=0)
        try:
            text = pytesseract.image_to_string(ocr_image, config='--psm 7 -c tessedit_char_whitelist=0123456789.,kKmMкКмМ')
        except Exception as exc:
            tesseract_not_found = getattr(pytesseract, 'TesseractNotFoundError', None)
            if tesseract_not_found is not None and isinstance(exc, tesseract_not_found):
                self.ocr_enabled = False
                if not self._ocr_missing_logged:
                    self.logger.warning('Tesseract not found; disabling distance OCR until restart')
                    self._ocr_missing_logged = True
                return None
            else:
                raise
        normalized = text.strip().lower().replace(' ', '')
        normalized = normalized.replace('к', 'k').replace('м', 'm').replace(',', '.')
        match = re.search('(\\d+(?:\\.\\d+)?)', normalized)
        if not match:
            return None
        else:
            try:
                value = float(match.group(1))
            except ValueError:
                return None
            if 'km' in normalized:
                return int(round(value * 1000.0))
            else:
                if 'm' in normalized:
                    return int(round(value))
                else:
                    if '.' in match.group(1) and value < 20.0:
                        return int(round(value * 1000.0))
                    else:
                        return int(round(value))
    @staticmethod
    def _normalize_ocr_text(text: str) -> str:
        return re.sub('[^0-9a-zA-Zа-яА-ЯёЁ]+', '', text).lower()
    def _run_text_ocr_data(self, image: np.ndarray, config: str, timeout_seconds: float | None=None, lang_sequence: tuple[str | None, ...] | None=None) -> dict | None:
        if not self.ocr_enabled:
            return None
        else:
            last_exc = None
            languages = lang_sequence or ('rus+eng', 'rus', 'eng', None)
            for lang in languages:
                kwargs = {'output_type': pytesseract.Output.DICT, 'config': config}
                if lang:
                    kwargs['lang'] = lang
                if timeout_seconds is not None and timeout_seconds > 0.0:
                        kwargs['timeout'] = timeout_seconds
                try:
                    return pytesseract.image_to_data(image, **kwargs)
                except Exception as exc:
                    tesseract_not_found = getattr(pytesseract, 'TesseractNotFoundError', None)
                    if tesseract_not_found is not None and isinstance(exc, tesseract_not_found):
                        self.ocr_enabled = False
                        if not self._ocr_missing_logged:
                            self.logger.warning('Tesseract not found; disabling OCR text search until restart')
                            self._ocr_missing_logged = True
                        return
                    else:
                        last_exc = exc
            if last_exc is not None:
                self.logger.debug('Text OCR failed for config=%s: %s', config, last_exc)
            return None
    def _build_text_search_variants(self, crop: np.ndarray, profile: CalibrationProfile, fast: bool=False) -> list[tuple[np.ndarray, float]]:
        scale = max(1.0, float(profile.thresholds.get('teleport_ocr_scale', 2.2)))
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if fast:
            return [(gray, scale), (thresh, scale)]
        else:
            inverted = cv2.bitwise_not(thresh)
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
            return [(gray, scale), (thresh, scale), (inverted, scale), (adaptive, scale)]
    def _collect_ocr_lines(self, ocr_data: dict, scale: float, offset_x: int, offset_y: int, min_confidence: float) -> list[tuple[str, tuple[int, int, int, int], float]]:
        grouped = {}
        total = len(ocr_data.get('text', []))
        for index in range(total):
            raw_text = str(ocr_data['text'][index] or '').strip()
            if not raw_text:
                continue
            else:
                try:
                    confidence = float(str(ocr_data['conf'][index]).replace(',', '.'))
                except Exception:
                    confidence = (-1.0)
                if confidence < min_confidence:
                    continue
                else:
                    key = (int(ocr_data['block_num'][index]), int(ocr_data['par_num'][index]), int(ocr_data['line_num'][index]))
                    left = int(round(int(ocr_data['left'][index]) / scale)) + offset_x
                    top = int(round(int(ocr_data['top'][index]) / scale)) + offset_y
                    width = int(round(int(ocr_data['width'][index]) / scale))
                    height = int(round(int(ocr_data['height'][index]) / scale))
                    right = left + width
                    bottom = top + height
                    entry = grouped.setdefault(key, {'texts': [], 'left': left, 'top': top, 'right': right, 'bottom': bottom, 'confidences': []})
                    entry['texts'].append(raw_text)
                    entry['left'] = min(int(entry['left']), left)
                    entry['top'] = min(int(entry['top']), top)
                    entry['right'] = max(int(entry['right']), right)
                    entry['bottom'] = max(int(entry['bottom']), bottom)
                    entry['confidences'].append(confidence)
        lines = []
        for entry in grouped.values():
            line_text = ' '.join((str(part) for part in entry['texts']))
            left = int(entry['left'])
            top = int(entry['top'])
            right = int(entry['right'])
            bottom = int(entry['bottom'])
            confidences = [float(value) for value in entry['confidences']]
            confidence = sum(confidences) / max(1, len(confidences))
            lines.append((line_text, (left, top, right - left, bottom - top), confidence))
        return lines
    def find_text_bbox(self, frame: np.ndarray, profile: CalibrationProfile, target_text: str, region: tuple[int, int, int, int] | None=None, fast: bool=False, timeout_seconds: float | None=None, lang_sequence: tuple[str | None, ...] | None=None) -> tuple[int, int, int, int] | None:
        if not self.ocr_enabled:
            return None
        else:
            target_norm = self._normalize_ocr_text(target_text)
            if not target_norm:
                return None
            else:
                if region is None:
                    x0, y0 = (0, 0)
                    crop = frame
                else:
                    x0, y0, w, h = self._clamp_rect(region, frame.shape)
                    crop = frame[y0:y0 + h, x0:x0 + w].copy()
                min_confidence = float(profile.thresholds.get('teleport_text_min_confidence', 28.0))
                min_match_ratio = float(profile.thresholds.get('teleport_text_match_ratio', 0.72))
                token_match_ratio = float(profile.thresholds.get('teleport_text_token_match_ratio', 0.76))
                psm = max(3, int(profile.thresholds.get('teleport_ocr_psm', 6)))
                config = f'--oem 3 --psm {psm}'
                target_tokens = [normalized for normalized in (self._normalize_ocr_text(part) for part in re.split('\\s+', target_text)) if normalized]
                best_match = None
                best_token_match = None
                for ocr_image, scale in self._build_text_search_variants(crop, profile, fast=fast):
                    ocr_data = self._run_text_ocr_data(ocr_image, config=config, timeout_seconds=timeout_seconds, lang_sequence=lang_sequence)
                    if not ocr_data:
                        continue
                    else:
                        total = len(ocr_data.get('text', []))
                        for index in range(total):
                            raw_text = str(ocr_data['text'][index] or '').strip()
                            if not raw_text:
                                continue
                            else:
                                word_norm = self._normalize_ocr_text(raw_text)
                                if not word_norm or not target_tokens:
                                    continue
                                else:
                                    try:
                                        confidence = float(str(ocr_data['conf'][index]).replace(',', '.'))
                                    except Exception:
                                        confidence = (-1.0)
                                    if confidence < min_confidence * 0.5:
                                        continue
                                    else:
                                        best_token_index = (-1)
                                        best_token_ratio = 0.0
                                        for token_index, token in enumerate(target_tokens):
                                            ratio = SequenceMatcher(None, word_norm, token).ratio()
                                            if ratio > best_token_ratio:
                                                best_token_ratio = ratio
                                                best_token_index = token_index
                                        if best_token_ratio < token_match_ratio:
                                            continue
                                        else:
                                            left = int(round(int(ocr_data['left'][index]) / scale)) + x0
                                            top = int(round(int(ocr_data['top'][index]) / scale)) + y0
                                            width = int(round(int(ocr_data['width'][index]) / scale))
                                            height = int(round(int(ocr_data['height'][index]) / scale))
                                            expand_left = width if best_token_index > 0 else max(12, width // 2)
                                            expand_right = max(12, width // 2)
                                            expand_y = max(8, height // 2)
                                            token_bbox = (max(0, left - expand_left), max(0, top - expand_y), width + expand_left + expand_right, height + expand_y * 2)
                                            if best_token_match is None or best_token_ratio > best_token_match[1] or (abs(best_token_ratio - best_token_match[1]) <= 0.02 and confidence > best_token_match[2]):
                                                best_token_match = (token_bbox, best_token_ratio, confidence)
                        lines = self._collect_ocr_lines(ocr_data, scale, x0, y0, min_confidence)
                        for line_text, bbox, confidence in lines:
                            line_norm = self._normalize_ocr_text(line_text)
                            if not line_norm:
                                continue
                            else:
                                match_ratio = 1.0 if target_norm in line_norm else SequenceMatcher(None, line_norm, target_norm).ratio()
                                if match_ratio < min_match_ratio:
                                    continue
                                else:
                                    if best_match is None or match_ratio > best_match[1] or (abs(match_ratio - best_match[1]) <= 0.02 and confidence > best_match[2]):
                                        best_match = (bbox, match_ratio, confidence)
                if best_match is not None:
                    return best_match[0]
                else:
                    return None if best_token_match is None else best_token_match[0]
    def read_inventory_slots(self, frame: np.ndarray, profile: CalibrationProfile) -> dict[str, tuple[int, int, int]]:
        result = {}
        inner_margin = int(profile.thresholds.get('inventory_slot_inner_margin_px', 10.0))
        for slot_name in ['inventory_slot_1', 'inventory_slot_2', 'inventory_slot_3']:
            zone = self._crop_zone(frame, profile, slot_name)
            if zone is None:
                continue
            else:
                crop, _ = zone
                if crop.size == 0:
                    continue
                else:
                    h, w = crop.shape[:2]
                    margin_x = min(inner_margin, max(0, w // 2 - 1))
                    margin_y = min(inner_margin, max(0, h // 2 - 1))
                    inner = crop[margin_y:h - margin_y, margin_x:w - margin_x]
                    if inner.size == 0:
                        inner = crop
                    median_bgr = tuple((int(v) for v in np.median(inner.reshape((-1), 3), axis=0)))
                    result[slot_name] = median_bgr
        return result
    def analyze(self, frame: np.ndarray, profile: CalibrationProfile, include_distance: bool=False, include_world_coords: bool=False, include_inventory: bool=False, include_minimap: bool=True, include_target_lock: bool=True, include_enemy_aggro: bool=True, include_combat_ui: bool=True, include_compass_marker: bool=True) -> VisionSnapshot:
        # ***<module>.VisionEngine.analyze: Failure: Different control flow
        if include_target_lock:
            target_locked, red_ratio, idle_ratio, target_confidence = self.detect_target_locked(frame, profile)
        else:
            target_locked, red_ratio, idle_ratio, target_confidence = (False, 0.0, 0.0, 0.0)
        if include_minimap:
            minimap_enemy_candidates = self.detect_minimap_enemy_candidates(frame, profile)
            minimap_enemies = []
            for candidate in minimap_enemy_candidates:
                minimap_enemies.extend([candidate.point] * max(1, candidate.stack_count))
            minimap_heading_vector, minimap_heading_tip, minimap_heading_confidence = self.detect_minimap_heading(frame, profile)
        else:
            minimap_enemy_candidates = []
            minimap_enemies = []
            minimap_heading_vector = None
            minimap_heading_tip = None
            minimap_heading_confidence = 0.0
        enemy_aggro_markers = self.detect_enemy_aggro_markers(frame, profile) if include_enemy_aggro else []
        nearby_enemy_count, nearest_enemy_distance = self.compute_minimap_metrics(minimap_enemies, profile)
        if include_combat_ui:
            enemy_level_targets = self.detect_enemy_level_targets(frame, profile)
            enemy_nn_targets = self.detect_enemy_nn_targets(frame, profile)
            enemy_back_target = self.detect_enemy_back_target(frame, profile)
            level_only_targeting = float(profile.thresholds.get('combat_level_only_targeting', 1.0)) > 0.5
            hp_presence = self.detect_presence(frame, profile, 'hp_bars_region')
            hp_bar_candidates = self._detect_hp_bar_candidates(frame, profile)
            hp_vertical_ratio, hp_lower_ratio = self.detect_hp_bar_layout(hp_bar_candidates, profile)
            enemy_hp_targets = self.detect_enemy_hp_targets(profile, hp_bar_candidates)
            hp_layout_detected = hp_vertical_ratio is not None
            hp_candidates_present = bool(hp_bar_candidates)
            hp_edge_assist_threshold = float(profile.thresholds.get('combat_hp_presence_edge_assist_threshold', profile.thresholds.get('presence_edge_ratio_threshold', 0.015) * 1.2))
            hp_present = hp_candidates_present or (target_locked and hp_presence.present and (hp_presence.edge_ratio >= hp_edge_assist_threshold))
            if level_only_targeting:
                name_presence = PresenceReading(present=False, edge_ratio=0.0, sat_ratio=0.0)
                enemy_body_targets = []
                name_present = False
            else:
                name_presence = self.detect_presence(frame, profile, 'name_level_region')
                enemy_body_targets = self.detect_enemy_body_targets(frame, profile, hp_bar_candidates)
                name_present = bool(name_presence.present and (hp_present or target_locked or bool(enemy_level_targets) or bool(enemy_nn_targets) or bool(enemy_body_targets) or bool(enemy_hp_targets)))
        else:
            hp_presence = PresenceReading(present=False, edge_ratio=0.0, sat_ratio=0.0)
            name_presence = PresenceReading(present=False, edge_ratio=0.0, sat_ratio=0.0)
            enemy_back_target = None
            enemy_level_targets = []
            enemy_nn_targets = []
            enemy_hp_targets = []
            enemy_body_targets = []
            hp_layout_detected = False
            hp_vertical_ratio = None
            hp_lower_ratio = 0.0
            hp_present = False
            name_present = False
        snapshot = VisionSnapshot(timestamp=time.monotonic(), minimap_enemies=minimap_enemies, minimap_enemy_candidates=minimap_enemy_candidates, minimap_heading_vector=minimap_heading_vector, minimap_heading_tip=minimap_heading_tip, minimap_heading_confidence=minimap_heading_confidence, enemy_aggro_markers=enemy_aggro_markers, enemy_aggro_count=len(enemy_aggro_markers), enemy_nn_targets=enemy_nn_targets, enemy_hp_targets=enemy_hp_targets, enemy_body_targets=enemy_body_targets, target_locked=target_locked, target_red_ratio=red_ratio, reticle_idle_ratio=idle_ratio, target_confidence=hp_vertical_ratio if hp_layout_detected else hp_presence.vertical_ratio, stamina_ratio=name_presence.edge_ratio, nearest_enemy_distance=nearest_enemy_distance, compass_marker=self.detect_compass_marker(frame, profile) if include_compass_marker else None)
        if include_distance:
            try:
                snapshot.distance_value = self.read_distance(frame, profile)
            except Exception:
                self.logger.exception('Distance OCR failed')
        if include_world_coords:
            try:
                snapshot.world_x, snapshot.world_y, snapshot.world_z = self.read_minimap_coordinates(frame, profile)
            except Exception:
                self.logger.exception('Coordinate OCR failed')
        if include_inventory:
            snapshot.inventory_slot_colors = self.read_inventory_slots(frame, profile)
        return snapshot
    def build_debug_model(self, profile: CalibrationProfile, phase_name: str, status: str, snapshot: VisionSnapshot, current_target: tuple[int, int] | None=None, route_points: list[tuple[int, int]] | None=None, route_active_index: int | None=None, route_terminal: tuple[int, int] | None=None, route_weights: list[int] | None=None) -> dict:
        # ***<module>.VisionEngine.build_debug_model: Failure: Compilation Error
        level_only_targeting = float(profile.thresholds.get('combat_level_only_targeting', 1.0)) > 0.5
        rects = []
        lines = []
        for name in ['minimap_region', 'aim_region', 'name_level_region', 'lvl_mob_region', 'compass_marker_region', 'distance_region', 'stamina_region', 'inventory_slot_1', 'inventory_slot_2', 'inventory_slot_3']:
            spec = profile.zones.get(name)
            if spec is None:
                continue
            else:
                rect = spec.as_pixels(profile.screen_size)
                if rect is None:
                    continue
                else:
                    rects.append({'name': name, 'rect': rect, 'color': (0, 255, 0)})
        minimap_spec = profile.zones.get('minimap_region')
        minimap_rect = minimap_spec.as_pixels(profile.screen_size) if minimap_spec else None
        if minimap_rect is not None:
            mx, my, mw, mh = minimap_rect
            coords_rect = (mx + int(round(mw * float(profile.thresholds.get('minimap_coords_region_x_ratio', 0.6)))), my + int(round(mh * float(profile.thresholds.get('minimap_coords_region_y_ratio', 0.62)))), int(round(mw * float(profile.thresholds.get('minimap_coords_region_w_ratio', 0.4)))), int(round(mh * float(profile.thresholds.get('minimap_coords_region_h_ratio', 0.38)))))
            rects.append({'name': 'minimap_coords_region', 'rect': coords_rect, 'color': (0, 200, 255)})
        for zone_name, color in [('minimap_coord_x_region', (0, 220, 255)), ('minimap_coord_y_region', (80, 220, 255)), ('minimap_coord_z_region', (160, 220, 255))]:
            spec = profile.zones.get(zone_name)
            if spec is None:
                continue
            else:
                rect = spec.as_pixels(profile.screen_size)
                if rect is not None:
                    rects.append({'name': zone_name, 'rect': rect, 'color': color})
        points = [{'name': 'enemy', 'point': p, 'color': (40, 185, 255)} for p in snapshot.minimap_enemies]
        for name in ['minimap_center', 'compass_center', 'inventory_scrollbar']:
            spec = profile.points.get(name)
            if spec is None:
                continue
            else:
                pt = spec.as_pixels(profile.screen_size)
                if pt is None:
                    continue
                else:
                    points.append({'name': name, 'point': pt, 'color': (0, 255, 255)})
        if snapshot.compass_marker is not None:
            points.append({'name': 'marker', 'point': snapshot.compass_marker, 'color': (0, 140, 255)})
        center_spec = profile.points.get('minimap_center')
        center = center_spec.as_pixels(profile.screen_size) if center_spec else None
        if center is not None:
            if snapshot.minimap_heading_tip is not None:
                lines.append({'name': 'heading_ray', 'start': center, 'end': snapshot.minimap_heading_tip, 'color': (0, 255, 180)})
                points.append({'name': 'heading_tip', 'point': snapshot.minimap_heading_tip, 'color': (0, 255, 180)})
            else:
                if snapshot.minimap_heading_vector is not None:
                    heading_point = (center[0] + int(round(snapshot.minimap_heading_vector[0] * 26.0)), center[1] + int(round(snapshot.minimap_heading_vector[1] * 26.0)))
                    lines.append({'name': 'heading_ray', 'start': center, 'end': heading_point, 'color': (0, 255, 180)})
                    points.append({'name': 'heading', 'point': heading_point, 'color': (0, 255, 180)})
            if route_points:
                previous_point = center
                for index, point in enumerate(route_points):
                    line_name = 'route_path' if index < len(route_points) - 1 else 'route_end_path'
                    line_color = (70, 170, 255) if index < len(route_points) - 1 else (255, 110, 70)
                    lines.append({'name': line_name, 'start': previous_point, 'end': point, 'color': line_color})
                    point_name = 'route_step'
                    point_color = (70, 170, 255)
                    if route_active_index is not None and index == route_active_index:
                            point_name = 'route_active'
                            point_color = (255, 170, 0)
                    if route_terminal is not None and point == route_terminal:
                            point_name = 'route_end'
                            point_color = (255, 110, 70)
                    points.append({'name': point_name, 'point': point, 'color': point_color})
                    previous_point = point
        if current_target is not None:
            points.append({'name': 'target', 'point': current_target, 'color': (255, 255, 0)})
        if snapshot.enemy_back_target is not None:
            rects.append({'name': 'enemy_back_rect', 'rect': snapshot.enemy_back_target.rect, 'color': (220, 120, 255)})
            points.append({'name': 'enemy_back_point', 'point': snapshot.enemy_back_target.point, 'color': (255, 120, 255)})
        if not level_only_targeting:
            for index, hp_target in enumerate(snapshot.enemy_hp_targets):
                points.append({'name': 'enemy_hp_anchor' if index > 0 else 'enemy_hp_anchor_primary', 'point': hp_target.anchor_point, 'color': (255, 190, 0) if index == 0 else (220, 140, 0)})
        for index, level_target in enumerate(snapshot.enemy_level_targets):
            rects.append({'name': 'enemy_level_rect' if index > 0 else 'enemy_level_primary_rect', 'rect': level_target.icon_rect, 'color': (160, 255, 0) if index == 0 else (110, 220, 0)})
            points.append({'name': 'enemy_level_anchor' if index > 0 else 'enemy_level_anchor_primary', 'point': level_target.icon_point, 'color': (140, 255, 0) if index == 0 else (100, 220, 0)})
            points.append({'name': 'enemy_level_aim' if index > 0 else 'enemy_level_aim_primary', 'point': level_target.aim_point, 'color': (80, 255, 80) if index == 0 else (60, 220, 60)})
        for index, nn_target in enumerate(snapshot.enemy_nn_targets):
            rects.append({'name': 'enemy_nn_rect' if index > 0 else 'enemy_nn_primary_rect', 'rect': nn_target.rect, 'color': (255, 90, 20) if index == 0 else (220, 70, 20)})
            points.append({'name': 'enemy_nn_point' if index > 0 else 'enemy_nn_primary', 'point': nn_target.point, 'color': (255, 120, 40) if index == 0 else (220, 100, 30)})
        if not level_only_targeting:
            for index, body_target in enumerate(snapshot.enemy_body_targets):
                rects.append({'name': 'enemy_body_rect' if index > 0 else 'enemy_body_primary_rect', 'rect': body_target.body_rect, 'color': (0, 180, 255) if index == 0 else (0, 120, 220)})
                points.append({'name': 'enemy_body' if index > 0 else 'enemy_body_primary', 'point': body_target.body_point, 'color': (0, 220, 255) if index == 0 else (0, 170, 220)})
        enemy_hp_targets = {'phase': phase_name, 'status': status, 'target_locked': snapshot.target_locked, 'red_ratio': round(snapshot.target_red_ratio, 4), 'idle_ratio': round(snapshot.reticle_idle_ratio, 4) if level_only_targeting or snapshot.hp_vertical_ratio is None else False, 'name_present': round(snapshot.hp_vertical_ratio, 3) if level_only_targeting or snapshot.name_edge_ratio is None else None, 'stamina': round(snapshot.stamina_ratio, 3) if level_only_targeting else None, 'distance': round(snapshot.distance_value, 3) if level_only_targeting else None, 'coord_x': round(snapshot.world_x, 3) if level_only_targeting else None, 'coord_y': round(snapshot.world_y, 3), 'world_z': round(snapshot.len, 3) if level_only_targeting else None, 'minimap_enemies': round(snapshot.minimap_heading_confidence, 3) if level_only_targeting else None, 'enemy_back_target':
            pass
        if route_points:
            active_step = 0 if route_active_index is None else max(0, route_active_index) + 1
            metrics['route_steps'] = len(route_points)
            metrics['route_active_step'] = active_step
            if route_weights:
                metrics['route_weights'] = ','.join((str(weight) for weight in route_weights))
            if center is not None and route_terminal is not None:
                    metrics['route_terminal_distance'] = round(float(np.hypot(route_terminal[0] - center[0], route_terminal[1] - center[1])), 1)
        if not level_only_targeting and snapshot.enemy_hp_targets:
                closest_hp_distance = snapshot.enemy_hp_targets[0].distance_to_aim
                metrics['closest_hp_distance'] = None if closest_hp_distance is None else round(closest_hp_distance, 1)
        if snapshot.enemy_level_targets:
            closest_level_distance = snapshot.enemy_level_targets[0].distance_to_aim
            metrics['closest_level_distance'] = None if closest_level_distance is None else round(closest_level_distance, 1)
        if snapshot.enemy_nn_targets:
            closest_nn_distance = snapshot.enemy_nn_targets[0].distance_to_aim
            metrics['closest_nn_distance'] = None if closest_nn_distance is None else round(closest_nn_distance, 1)
            metrics['nn_score'] = round(snapshot.enemy_nn_targets[0].score, 3)
            metrics['nn_label'] = snapshot.enemy_nn_targets[0].label
        if snapshot.enemy_back_target is not None:
            metrics['back_target_score'] = round(snapshot.enemy_back_target.template_score, 3)
            metrics['back_target_distance'] = None if snapshot.enemy_back_target.distance_to_aim is None else round(snapshot.enemy_back_target.distance_to_aim, 1)
        if not level_only_targeting and snapshot.enemy_body_targets:
                closest_body_distance = snapshot.enemy_body_targets[0].distance_to_aim
                metrics['closest_body_distance'] = None if closest_body_distance is None else round(closest_body_distance, 1)
        if center is not None and current_target is not None:
                target_distance = float(np.hypot(current_target[0] - center[0], current_target[1] - center[1]))
                metrics['target_distance'] = round(target_distance, 1)
                metrics['target_sector'] = self._vector_to_cardinal((float(current_target[0] - center[0]), float(current_target[1] - center[1])))
        heading_sector = self._vector_to_cardinal(snapshot.minimap_heading_vector)
        if heading_sector is not None:
            metrics['heading_sector'] = heading_sector
        return {'rects': rects, 'points': points, 'lines': lines, 'metrics': metrics}