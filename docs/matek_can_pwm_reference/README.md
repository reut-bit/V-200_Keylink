# Настройки CAN-L4-PWM ↔ Pixhawk: краткая сводка

Рабочие параметры из `reference.param` (Pixhawk) и `reference_can_pwm.param` (нода).

## Схема маршрутизации сигналов

```
Pixhawk (CAN1, 1 Mbps)                    Matek CAN-L4-PWM
─────────────────────────                  ─────────────────
SERVO1 (func 33, Motor1) ──── CAN ────►   (не назначен)
SERVO2 (func 34, Motor2) ──── CAN ────►   (не назначен)
SERVO3 (func 35, Motor3) ──── CAN ────►   (не назначен)
SERVO4 (func 36, Motor4) ──── CAN ────►   (не назначен)
SERVO5 (func 0, откл.)   ──── CAN ────►   OUT5 (func 55) → PWM-реле
SERVO6 (func 0, откл.)   ──── CAN ────►   OUT6 (func 56) → PWM-реле
RELAY1 (pin 1000, CAN)   ── hardpoint ──►  OUT7 (GPIO, pin 56) → MOSFET
```

> `CAN_D1_UC_SRV_BM = 63` (0b00111111) → SERVO1–6 передаются по CAN1.

## Выходы CAN-ноды

| Выход | `OUTn_FUNCTION` | Слушает | Устройство | Режим |
|---|---|---|---|---|
| OUT1 | 0 | — | не используется | — |
| OUT2 | 0 | — | не используется | — |
| OUT3 | 0 | — | не используется | — |
| OUT4 | 0 | — | не используется | — |
| **OUT5** | **55** (50+5) | SERVO5 | **PWM-реле** | PWM |
| **OUT6** | **56** (50+6) | SERVO6 | **PWM-реле** | PWM |
| **OUT7** | **-1** (GPIO) | RELAY1 | **MOSFET** | GPIO 0V/3.3V |
| OUT8 | 0 | — | не используется | — |
| OUT9 | 0 | — | не используется | — |

## Параметры Pixhawk (выдержка)

### CAN

| Параметр | Значение |
|---|---|
| `CAN_P1_DRIVER` | 1 |
| `CAN_P1_BITRATE` | 1000000 |
| `CAN_D1_PROTOCOL` | 1 (DroneCAN) |
| `CAN_D1_UC_NODE` | 1 |
| `CAN_D1_UC_SRV_BM` | 63 (SERVO1–6) |
| `CAN_D1_UC_SRV_RT` | 50 Гц |

### Каналы серво для CAN-выходов

| Параметр | Значение | Назначение |
|---|---|---|
| `SERVO5_FUNCTION` | 0 | Не назначена функция (PWM-реле на OUT5) |
| `SERVO5_MIN/TRIM/MAX` | 1100 / 1500 / 1900 | |
| `SERVO6_FUNCTION` | 0 | Не назначена функция (PWM-реле на OUT6) |
| `SERVO6_MIN/TRIM/MAX` | 800 / 1500 / 2200 | Расширенный диапазон |

> **Примечание:** `SERVO5_FUNCTION` и `SERVO6_FUNCTION` = 0 (Disabled). Для управления реле от тумблера нужно назначить функцию (например, `1` = RCPassThru) или управлять через `DO_SET_SERVO` в миссии.

### Relay (MOSFET на OUT7)

| Параметр | Значение |
|---|---|
| `RELAY1_PIN` | 1000 (виртуальный CAN-relay) |
| `RELAY1_FUNCTION` | 1 (Relay) |
| `BRD_SAFETY_DEFLT` | 0 |

## Параметры CAN-ноды (выдержка)

| Параметр | Значение |
|---|---|
| `CAN_BAUDRATE` | 1000000 |
| `ESC_PWM_TYPE` | 0 (обычный PWM) |
| `OUT_BLH_MASK` | 0 (DShot выкл.) |
| `OUT5_FUNCTION` | 55 → SERVO5 |
| `OUT5_MIN/TRIM/MAX` | 1100 / 1500 / 1900 |
| `OUT6_FUNCTION` | 56 → SERVO6 |
| `OUT6_MIN/TRIM/MAX` | 994 / 1500 / 2200 |
| `OUT7_FUNCTION` | -1 (GPIO) |
| `RELAY1_PIN` | 56 (GPIO-пин OUT7) |
| `RELAY1_FUNCTION` | 10 (DroneCAN relay) |

## Файлы

| Файл | Содержимое |
|---|---|
| `reference.param` | Полный дамп параметров Pixhawk |
| `reference_can_pwm.param` | Параметры ноды CAN-L4-PWM |
| `matek_can_l4_pwm_setup.md` | Подробная инструкция по настройке |
