# PacketLab — контекст проекта

## Что мы делаем

Перехватываем сетевые TCP-пакеты игры через **mitmproxy** и в реальном времени извлекаем
позицию (X, Y, Z) и угол поворота камеры (ROT) игрока. Скрипт работает как аддон mitmproxy.

## Стек

- **mitmproxy** — перехват трафика, запуск: `mitmdump -p 8081 -s live_packets.py`
- **Python 3** — логика парсинга пакетов (аддон для mitmproxy)
- **Формат пакетов** — бинарный TCP, little-endian
- **ОС** — Windows

## Структура пакетов (то что мы выяснили)

### Маркер координат
Байтовый маркер: `0204000000` (5 байт)
Сразу после маркера идёт float32 (little-endian) — значение координаты.
Три подряд идущих маркера = тройка X, Y, Z.

### Фильтр "своих" координат
- `|X| > 1000`, `|Z| > 1000`, `|Y| < 5000` — санити-чек что это координаты игрока
- Пакеты с маркеров **≤ 6** — пакет позиции игрока (личный)
- Пакеты с маркеров **> 6** — пакет сущностей (другие игроки/мобы), пропускаем
- Первая подходящая тройка `[0]` — координаты игрока

### Координаты (проверено на практике)
Работают правильно. Точность ±1 единица.
Пример реальных значений: `X=-11346, Y=494, Z=-7351`

### ROT (угол поворота камеры) — В ПРОЦЕССЕ ОТЛАДКИ
**Проблема**: ROT пока не работает корректно, всегда показывает 0 или статичное значение.

**Что выяснили:**
- ROT передаётся в **отдельном пакете размером 31 байт**
- Формат: **int16 little-endian** на смещении `0x1A` (26 байт от начала)
- Делитель: предположительно `10000` (т.е. `raw_int / 10000 = радианы`)
- Значения меняются при повороте камеры: видели `18432 → 22784`
- Но в скрипте ROT всё равно остаётся статичным — возможно нужно уточнить делитель или offset

**Что нужно найти:**
- Точный offset в 31-байтном пакете где лежит ROT
- Точный делитель для перевода в радианы/градусы
- Возможно ROT приходит в пакете другого размера

## Текущий рабочий скрипт (live_packets.py)

```python
from mitmproxy import tcp
import struct
import math
import time
import os

OUT_FILE = "player_live.txt"
DEBUG_FILE = "entity_debug.txt"
RESET_FILE = "reset.txt"

MARKER = bytes.fromhex("0204000000")

ROT_PACKET_SIZE = 31
ROT_OFFSET = 0x1A
ROT_DIVISOR = 10000.0

MAX_MARKERS_FOR_PLAYER_PACKET = 6

locked = False
player_x = 0.0
player_y = 0.0
player_z = 0.0
last_rot = 0.0
last_update_time = time.time()
rot_debug_count = 0
ROT_DEBUG_LIMIT = 50


def reset_state():
    global locked, player_x, player_y, player_z
    global last_rot, last_update_time, rot_debug_count
    locked = False
    player_x = 0.0
    player_y = 0.0
    player_z = 0.0
    last_rot = 0.0
    last_update_time = time.time()
    rot_debug_count = 0
    print("[RESET] Состояние сброшено")


class RealtimeReader:

    def tcp_message(self, flow: tcp.TCPFlow):
        global locked, player_x, player_y, player_z
        global last_rot, last_update_time, rot_debug_count

        try:
            if os.path.exists(RESET_FILE):
                os.remove(RESET_FILE)
                reset_state()

            if locked and time.time() - last_update_time > 3.0:
                locked = False

            data = flow.messages[-1].content

            # ROT пакет (31 байт)
            if len(data) == ROT_PACKET_SIZE:
                try:
                    raw_int = struct.unpack("<h", data[ROT_OFFSET:ROT_OFFSET + 2])[0]
                    rot = raw_int / ROT_DIVISOR
                    if rot_debug_count < ROT_DEBUG_LIMIT:
                        hex_str = " ".join(f"{b:02X}" for b in data)
                        with open("rot_live.txt", "a", encoding="utf-8") as f:
                            f.write(f"raw={raw_int:6d}  rot={round(rot,5):9.5f}  hex=[{hex_str}]\n")
                        rot_debug_count += 1
                    if abs(rot) > 0.0001:
                        last_rot = rot
                except:
                    pass
                return

            # Поиск маркеров
            found_values = []
            start = 0
            while True:
                pos = data.find(MARKER, start)
                if pos == -1:
                    break
                value_offset = pos + len(MARKER)
                if value_offset + 4 <= len(data):
                    try:
                        raw = data[value_offset:value_offset + 4]
                        value = struct.unpack("<f", raw)[0]
                        if abs(value) < 500000 and abs(value) > 1:
                            found_values.append((value, pos))
                    except:
                        pass
                start = pos + 1

            if len(found_values) < 3:
                return
            if len(found_values) > MAX_MARKERS_FOR_PLAYER_PACKET:
                return

            # XYZ
            for i in range(len(found_values) - 2):
                x = found_values[i][0]
                y = found_values[i + 1][0]
                z = found_values[i + 2][0]
                if not (abs(x) > 1000 and abs(z) > 1000 and abs(y) < 5000):
                    continue

                dist = 0.0
                if not locked:
                    player_x = x
                    player_y = y
                    player_z = z
                    locked = True
                    last_update_time = time.time()
                else:
                    dx = x - player_x
                    dy = y - player_y
                    dz = z - player_z
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist > 50:
                        continue
                    player_x = x
                    player_y = y
                    player_z = z
                    last_update_time = time.time()

                text = (
                    f"X={round(player_x, 2)}\n"
                    f"Y={round(player_y, 2)}\n"
                    f"Z={round(player_z, 2)}\n"
                    f"ROT={round(last_rot, 6)}"
                )
                print(text)
                with open(OUT_FILE, "w", encoding="utf-8") as f:
                    f.write(text)

                debug = (
                    f"\n====================\n"
                    f"X={x}\nY={y}\nZ={z}\n"
                    f"ROT={last_rot}\n"
                    f"MARKERS={len(found_values)}\n"
                    f"DIST={round(dist, 3)}\n"
                    f"LOCKED={locked}\n"
                )
                with open(DEBUG_FILE, "a", encoding="utf-8") as f:
                    f.write(debug)
                break

        except Exception as e:
            print(e)


addons = [RealtimeReader()]
```

## Файлы которые создаёт скрипт

| Файл | Содержимое |
|---|---|
| `player_live.txt` | Текущие X, Y, Z, ROT — перезаписывается каждый пакет |
| `entity_debug.txt` | Подробный лог каждого обновления (append) |
| `rot_live.txt` | Лог первых 50 ROT-пакетов с hex для диагностики |
| `reset.txt` | Создай этот файл чтобы сбросить состояние без перезахода |

## Команда запуска

```
mitmdump -p 8081 -s live_packets.py
```

## Сброс состояния без перезахода в игру

```
echo. > reset.txt        # Windows
touch reset.txt          # Linux
```

Скрипт сам удалит файл и сбросит locked/координаты.

## Что сейчас нужно решить

1. **ROT не работает** — нужно найти точный offset и делитель в 31-байтном пакете
2. Для диагностики ROT — скрипт пишет `rot_live.txt` с hex каждого 31-байтного пакета
3. Нужно сравнить несколько строк из `rot_live.txt` когда камера смотрит в разные стороны
   и найти байты которые меняются — это и будет ROT

## Игра

Не уточнялась. Судя по координатам (X ~-11000, Z ~-7000, Y ~500) — большой открытый мир.
Протокол бинарный TCP с маркерами `0204000000`.
