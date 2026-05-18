# Source Generated with Decompyle++
# File: gather_logic_modes.pyc (Python 3.11)

from __future__ import annotations
from dataclasses import dataclass
DEFAULT_GATHER_LOGIC_MODE = 'nearest_target'
GatherLogicModeSpec = <NODE:12>()
GATHER_LOGIC_MODES: 'tuple[GatherLogicModeSpec, ...]' = (GatherLogicModeSpec('adaptive_route', 'Adaptive route', 'Адаптивный маршрут', 'Balanced cluster-route logic with live minimap route updates.', 'Сбалансированная маршрутизация по кластерам с живым обновлением точек по миникарте.'), GatherLogicModeSpec('nearest_target', 'Nearest target', 'Ближайшая цель', 'Always prefers the closest not-yet-collected enemy or cluster.', 'Всегда выбирает ближайшего ещё не собранного моба или ближайший кластер.'), GatherLogicModeSpec('densest_cluster', 'Densest cluster', 'Самый плотный кластер', 'Prioritizes clusters with the largest nearby enemy density.', 'Приоритет у кластера с наибольшей локальной плотностью монстров.'), GatherLogicModeSpec('forward_sweep', 'Forward sweep', 'Сбор по курсу', 'Prefers targets that stay ahead of the current minimap heading.', 'Предпочитает цели, лежащие впереди по текущему курсу на миникарте.'), GatherLogicModeSpec('clockwise_sweep', 'Clockwise sweep', 'Сбор по часовой', 'Rotates target preference clockwise around the player center.', 'Обходит цели по часовой стрелке вокруг центра игрока.'), GatherLogicModeSpec('counter_clockwise_sweep', 'Counter-clockwise sweep', 'Сбор против часовой', 'Rotates target preference counter-clockwise around the player center.', 'Обходит цели против часовой стрелки вокруг центра игрока.'), GatherLogicModeSpec('inward_pull', 'Inward pull', 'Стягивание к центру', 'Favors targets that are already moving inward and can be dragged into the center fast.', 'Предпочитает цели, которые уже хорошо стягиваются к центру и быстро доходят до него.'), GatherLogicModeSpec('stable_lock', 'Stable lock', 'Жёсткий лок', 'Minimizes target switching and commits longer to the same minimap target.', 'Сильно снижает переключения и дольше держится за ту же цель на миникарте.'), GatherLogicModeSpec('pack_builder', 'Pack builder', 'Строитель пака', 'Chooses paths that sweep through multiple nearby clusters to build a denser pull.', 'Выбирает траектории, которые по пути захватывают несколько соседних кластеров и наращивают пак.'), GatherLogicModeSpec('terminal_push', 'Terminal push', 'Дальний вектор', 'Pushes deeper to a terminal outer cluster before collapsing back inward.', 'Тянет к дальней терминальной группе, а потом собирает остальное обратно внутрь.'))
GATHER_LOGIC_MODE_KEYS = (lambda .0: pass# WARNING: Decompyle incomplete
)(GATHER_LOGIC_MODES())

def normalize_gather_logic_mode(value = dataclass(frozen = True)):
    if isinstance(value, str) and value in GATHER_LOGIC_MODE_KEYS:
        return value


def get_gather_logic_spec(key = None):
    normalized = normalize_gather_logic_mode(key)
    for spec in GATHER_LOGIC_MODES:
        if spec.key == normalized:
            
            return None, spec
        return GATHER_LOGIC_MODES[0]

