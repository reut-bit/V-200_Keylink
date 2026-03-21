# Переключение Hitec SG50BL с CAN 2.0A на DroneCAN

## Оборудование

- **Hitec SG50BL-CAN-24V-CIRCULAR-CONN** — сервомашинка
- **SG Series DroneCAN/CAN Dongle** — переходник с разъёма серво на разъём программатора
- **CAN-адаптер** — DPC-CAN / DPC-20 (Hitec) или любой USB-CAN адаптер (Canable, Innomaker USB2CAN, Waveshare USB-CAN-A и др.)
- **Блок питания 18–32V** для серво
- **ПО** — [Hitec Configuration App](https://www.hiteccs.com/public/uploads/ckeditor/622a83814860b1646953345.zip) (для DPC-CAN/DPC-20) или `python-can` (для USB-CAN адаптеров)

## Документация

- [Страница продукта SG50BL](https://www.hiteccs.com/actuators/product-details/SG50BL-CAN-24V-CIRCULAR-CONN)
- [SG Series DroneCAN/CAN Dongle](https://www.hiteccs.com/actuators/product-details/SG-Series-DroneCAN-CAN-Dongle/)
- [Hitec Wiki](http://support.hitecrcd.net:7700/index.php/Main_Page)
- Протокольный мануал: `docs/Servo_manual.pdf`

## Предварительные условия

- Тип прошивки (F/W Type) должен быть **A** (поддерживает CAN и DroneCAN). Тип **C** — только CAN, тип **U** — только DroneCAN.
- Версия F/W **>= 1.6(2)** для полноценной работы DroneCAN с RUN_MODE.
- Версию можно прочитать из регистра `REG_VERSION` (адрес `0xFC`).

## Схема подключения

```
[ПК] —USB— [CAN-адаптер / DPC-CAN] —[SG Dongle]— [SG50BL] + [БП 24V]
```

Параметры связи DPC-CAN: baud rate 115200, stop bit 1, parity none.

## Процедура переключения на DroneCAN

### 1. Записать регистры

| Регистр                | Адрес  | Значение | Описание                                   |
|------------------------|--------|----------|--------------------------------------------|
| `REG_CAN_MODE`         | `0x6A` | **2**    | Протокол: 0 = CAN 2.0A, 1 = 2.0B, 2 = DroneCAN |
| `REG_CAN_BAUDRATE`     | `0x38` | **0**    | 1000 kbps (стандарт для DroneCAN/ArduPilot) |
| `REG_ID`               | `0x32` | **1–127**| Node ID серво (уникальный в CAN-сети)      |
| `REG_CAN_BUS_ID_H`     | `0x3C` | **0**    | Для DroneCAN всегда 0                      |
| `REG_CAN_BUS_ID_L`     | `0x3E` | **128**  | Для DroneCAN рекомендуется 128             |
| `REG_RUN_MODE`         | `0x44` | **1**    | 0 = Multi-Turn, 1 = Servo, 2 = CR, 3 = Speed |

### 2. Сохранить

- Остановить серво (убедиться, что мотор не вращается).
- Записать **0xFFFF** (65535) в регистр `REG_CONFIG_SAVE` (адрес `0x70`).
- Подождать **1 секунду**.

### 3. Перезагрузить

- Выключить и включить питание сервомашинки.
- После включения серво работает по протоколу DroneCAN.

### 4. Проверить

Серво должна определяться в DroneCAN-сети: через Mission Planner / QGroundControl (раздел DroneCAN) или через `DroneCAN GUI Tool`.

## Альтернатива: USB-CAN адаптер + Python

Если нет программатора DPC-CAN / DPC-20, можно использовать любой USB-CAN адаптер и скрипт на Python.

Формат CAN-пакета для записи регистра (New Packet Format, раздел 1-4 мануала):

| Поле       | Значение                      |
|------------|-------------------------------|
| Message ID | `'w'` (0x77) — запись 1 регистра |
| ID         | ID серво (0x00 — broadcast)   |
| Address    | Адрес регистра                |
| Data Low   | Младший байт значения         |
| Data High  | Старший байт значения         |

### Пример скрипта

```python
import can
import time

bus = can.Bus(interface='slcan', channel='/dev/ttyACM0', bitrate=250000)

servo_id = 0x00  # broadcast

def write_register(addr, value):
    data = [ord('w'), servo_id, addr, value & 0xFF, (value >> 8) & 0xFF]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)
    time.sleep(0.05)

write_register(0x6A, 2)       # REG_CAN_MODE = DroneCAN
write_register(0x38, 0)       # REG_CAN_BAUDRATE = 1000 kbps
write_register(0x32, 10)      # REG_ID = 10 (выбрать свой Node ID)
write_register(0x3C, 0)       # REG_CAN_BUS_ID_H = 0
write_register(0x3E, 128)     # REG_CAN_BUS_ID_L = 128
write_register(0x44, 1)       # REG_RUN_MODE = Servo

time.sleep(0.1)
write_register(0x70, 0xFFFF)  # REG_CONFIG_SAVE

print("Сохранено. Отключите и включите питание серво.")
```

> **Важно**: `bitrate=250000` — это текущая скорость серво по умолчанию (до смены). После перезагрузки серво переключится на 1000 kbps.

## Справочник скоростей (REG_CAN_BAUDRATE)

| Значение | Скорость   |
|----------|------------|
| 0        | 1000 kbps  |
| 1        | 800 kbps   |
| 2        | 750 kbps   |
| 3        | 500 kbps   |
| 4        | 400 kbps   |
| 5        | 250 kbps   |
| 6        | 200 kbps   |
| 7        | 150 kbps   |
| 8        | 125 kbps   |
