# Перепрошивка Hitec SG50BL на DroneCAN через Pixhawk6X Pro

Цель: переключить серво Hitec SG50BL с протокола CAN 2.0A на DroneCAN,
используя Pixhawk6X Pro в режиме SLCAN как CAN-адаптер.  
Node ID серво: **51**.

## Схема подключения

```
[ПК] —USB— [Pixhawk6X Pro (CAN2)] —CAN H/L— [SG50BL] + [БП 24V]
```

Серво подключается к порту **CAN2** на Pixhawk (CAN H, CAN L, GND).  
Питание 24V подаётся на серво отдельно (V+, V–).

---

## Фаза A: Подготовка ArduPilot (SLCAN на CAN2, 250 kbps)

Серво из коробки работает на CAN 2.0A @ 250 kbps. Pixhawk по умолчанию на CAN2 @ 1000 kbps.
Нужно временно понизить скорость и включить SLCAN passthrough.

### Параметры для изменения

В Mission Planner / QGroundControl / MAVProxy:

| Параметр           | Было     | Ставим    | Описание                            |
|--------------------|----------|-----------|-------------------------------------|
| `CAN_P2_BITRATE`   | 1000000  | **250000**| Скорость CAN2 = 250 kbps (как у серво) |
| `CAN_SLCAN_CPORT`  | 1        | **2**     | SLCAN привязан к CAN2               |
| `CAN_SLCAN_TIMOUT`  | 0        | **0**     | Без таймаута (SLCAN всегда активен) |

После изменения — **перезагрузить полётник**.

> **Важно**: пока SLCAN активен на CAN2, ArduPilot не будет использовать CAN2
> для своих целей (DroneCAN-устройства на CAN2 временно не работают).

---

## Фаза B: Прошивка серво через SLCAN

### Вариант 1: Python-скрипт (`python-can`)

Установить зависимость:

```bash
pip install python-can
```

Определить порт Pixhawk (macOS: `/dev/cu.usbmodem*`, Linux: `/dev/ttyACM0`):

```bash
ls /dev/cu.usbmodem*   # macOS
ls /dev/ttyACM*         # Linux
```

Скрипт `flash_hitec_dronecan.py`:

```python
import can
import time

SLCAN_PORT = '/dev/cu.usbmodemXXXX'  # <-- заменить на реальный порт Pixhawk

bus = can.Bus(interface='slcan', channel=SLCAN_PORT, bitrate=250000)

servo_id = 0x00  # broadcast — обращаемся ко всем серво на шине

def write_register(addr, value):
    """Записать 16-битное значение в регистр серво (New Packet Format)."""
    data = [ord('w'), servo_id, addr, value & 0xFF, (value >> 8) & 0xFF]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)
    time.sleep(0.05)

def read_register(addr):
    """Запросить значение регистра серво."""
    data = [ord('r'), servo_id, addr]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)
    response = bus.recv(timeout=1.0)
    if response:
        print(f"  Ответ: {response}")
    else:
        print(f"  Нет ответа (таймаут)")
    return response

# --- Шаг 1: Проверка связи ---
print("=== Проверка связи ===")
print("Читаем REG_VERSION (0xFC)...")
read_register(0xFC)

print("Читаем REG_CAN_MODE (0x6A)...")
read_register(0x6A)

input("\nЕсли получены ответы — связь работает. Enter для продолжения, Ctrl+C для отмены...")

# --- Шаг 2: Запись регистров ---
print("\n=== Запись регистров ===")

print("REG_CAN_MODE = 2 (DroneCAN)")
write_register(0x6A, 2)

print("REG_CAN_BAUDRATE = 0 (1000 kbps)")
write_register(0x38, 0)

print("REG_ID = 51 (Node ID)")
write_register(0x32, 51)

print("REG_CAN_BUS_ID_H = 0")
write_register(0x3C, 0)

print("REG_CAN_BUS_ID_L = 128")
write_register(0x3E, 128)

print("REG_RUN_MODE = 1 (Servo Mode)")
write_register(0x44, 1)

# --- Шаг 3: Сохранение ---
print("\n=== Сохранение ===")
time.sleep(0.2)
print("REG_CONFIG_SAVE = 0xFFFF")
write_register(0x70, 0xFFFF)

print("Ожидание 2 секунды...")
time.sleep(2.0)

print("\n✓ Готово! Отключите и включите питание серво.")
print("  После перезагрузки серво будет работать на DroneCAN @ 1000 kbps, Node ID = 51.")

bus.shutdown()
```

### Вариант 2: DroneCAN GUI Tool + SLCAN

DroneCAN GUI Tool работает с SLCAN, но **только для DroneCAN-устройств**.
Пока серво на CAN 2.0A — этот инструмент не подходит. Используйте Python-скрипт.

---

## Фаза C: Возврат параметров ArduPilot

После успешной прошивки серво и его перезагрузки.

| Параметр           | Ставим      | Описание                              |
|--------------------|-------------|---------------------------------------|
| `CAN_P2_BITRATE`   | **1000000** | Возвращаем 1000 kbps                  |
| `CAN_SLCAN_CPORT`  | **0**       | Отключаем SLCAN (или вернуть 1)       |

**Перезагрузить полётник.**

---

## Фаза D: Проверка и назначение сервовыходов

### 1. Проверить что серво видна

В Mission Planner: **Setup → Optional Hardware → DroneCAN/UAVCAN**  
Или в `DroneCAN GUI Tool` (подключение через MAVLink).

Серво должна отображаться как Node ID **51**.

### 2. Назначить сервовыход на CAN2

Определить, на какой канал (SERVO output) назначить серво.
Например, если серво управляет каналом **5** (SERVO5):

```
CAN_D2_UC_SRV_BM = 16
```

Битовая маска: бит N-1 = канал N.

| Канал   | Бит | Значение SRV_BM |
|---------|-----|------------------|
| SERVO1  | 0   | 1                |
| SERVO2  | 1   | 2                |
| SERVO3  | 2   | 4                |
| SERVO4  | 3   | 8                |
| SERVO5  | 4   | 16               |
| SERVO6  | 5   | 32               |
| SERVO7  | 6   | 64               |
| SERVO8  | 7   | 128              |

Для нескольких каналов — сложить значения.

### 3. Назначить функцию канала

```
SERVOx_FUNCTION = <нужная функция>
```

---

## Чеклист

- [ ] Серво подключена к CAN2 (CAN H, CAN L, GND) + БП 24V
- [ ] `CAN_P2_BITRATE` = 250000
- [ ] `CAN_SLCAN_CPORT` = 2
- [ ] Полётник перезагружен
- [ ] Запущен скрипт, проверка связи прошла (ответ от серво)
- [ ] Регистры записаны, сохранение выполнено
- [ ] Питание серво отключено и включено
- [ ] `CAN_P2_BITRATE` возвращён в 1000000
- [ ] `CAN_SLCAN_CPORT` = 0
- [ ] Полётник перезагружен
- [ ] Серво видна в DroneCAN (Node ID 51)
- [ ] `CAN_D2_UC_SRV_BM` настроен
- [ ] Функция канала (`SERVOx_FUNCTION`) назначена
- [ ] Серво реагирует на команды

---

## Откат: если что-то пошло не так

Если серво не отвечает на CAN-пакеты:
- Проверить физическое подключение (CAN H / CAN L не перепутаны)
- Убедиться что питание 24V подано
- Попробовать другие bitrate (серво может быть на 1000 kbps если уже прошивали)
- Использовать `servo_id = 0x00` (broadcast) в скрипте

Если нужно вернуть серво на заводские настройки:
- Записать **3855** (0x0F0F) в `REG_FACTORY_DEFAULT` (адрес `0x6E`)
- Затем сохранить через `REG_CONFIG_SAVE` (адрес `0x70`) = 0xFFFF
- Перезагрузить серво
