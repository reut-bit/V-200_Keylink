#!/usr/bin/env python3
"""
Считывание всех параметров сервопривода Hitec SG50BL через SLCAN (CAN 2.0A).
Только чтение — никакие регистры не записываются.

Подключение:
  [ПК] —USB— [CAN-адаптер / DPC-CAN / Pixhawk SLCAN] —[SG Dongle]— [SG50BL] + [БП 24V]

Перед запуском (для Pixhawk SLCAN):
  1. CAN_SLCAN_CPORT = 1
  2. CAN_SLCAN_TIMOUT = 0
  3. Перезагрузить полётник
  4. CAN_SLCAN_SERNUM = 0 (без перезагрузки!)
  5. Закрыть QGroundControl

Использование:
  python read_hitec_params.py
  python read_hitec_params.py /dev/cu.usbmodem14301
  python read_hitec_params.py /dev/cu.usbmodem14301 1000000
  python read_hitec_params.py /dev/cu.usbmodem14301 1000000 55
"""

import can
import sys
import time
import math

# ============================================================
# Настройки — изменить при необходимости
# ============================================================
SLCAN_PORT = '/dev/cu.usbmodem14301'
BITRATE = 1000000
SERVO_ID = 0x00  # 0x00 = broadcast

# ============================================================
# Таблица регистров Hitec CAN Servo (из Servo_manual.pdf)
# ============================================================

CAN_BAUDRATE_MAP = {
    0: '1000 kbps', 1: '800 kbps', 2: '750 kbps', 3: '500 kbps',
    4: '400 kbps', 5: '250 kbps', 6: '200 kbps', 7: '150 kbps',
    8: '125 kbps',
}

CAN_MODE_MAP = {0: 'CAN 2.0A', 1: 'CAN 2.0B', 2: 'DroneCAN'}

RUN_MODE_MAP = {0: 'Multi-Turn', 1: 'Servo', 2: 'CR', 3: 'Speed'}

SAMPLE_POINT_MAP = {0: '50%', 1: '87.5%'}


def decode_emergency_stop(val):
    """Декодирование битового поля REG_EMERGENCY_STOP."""
    flags = []
    if val & (1 << 8):
        flags.append('POS_MIN_ERROR')
    if val & (1 << 9):
        flags.append('POS_MAX_ERROR')
    if val & (1 << 10):
        flags.append('MCU_TEMP_UNDER')
    if val & (1 << 11):
        flags.append('MCU_TEMP_OVER')
    if val & (1 << 13):
        flags.append('VOLT_UNDER')
    if val & (1 << 14):
        flags.append('VOLT_OVER')
    return ', '.join(flags) if flags else 'OK'


def decode_status(val):
    """Декодирование REG_STATUS."""
    parts = []
    enabled = val & 1
    parts.append(f"enabled={'yes' if enabled else 'no'}")
    if val & 2:
        parts.append('OVER_CURRENT')
    return ', '.join(parts)


def decode_setup(val):
    """Декодирование REG_SETUP битов."""
    flags = []
    if val & (1 << 0):
        flags.append('PAD_VOLT2')
    if val & (1 << 1):
        flags.append('START_POS')
    if val & (1 << 2):
        flags.append('BRAKE_FREE')
    if val & (1 << 3):
        flags.append('OVERVOLT_BRAKE')
    if val & (1 << 7):
        flags.append('STREAM_CAN_ID')
    if val & (1 << 10):
        flags.append('FAIL_SAFE')
    if val & (1 << 12):
        flags.append('REALTIME_ID')
    if val & (1 << 15):
        flags.append('MOTOR_REV')
    return ', '.join(flags) if flags else 'none'


def pos_to_deg(pos):
    """Позиция (4096=90°) → градусы."""
    return pos * 90.0 / 4096.0


def voltage_format(val):
    """Значение напряжения (100 = 1.00V) → строка."""
    return f"{val / 100.0:.2f} V"


def motor_temp_calc(data):
    """Расчёт температуры мотора из сырого значения."""
    if data == 0:
        return 'N/A'
    T0 = 298.15
    VT = 3.3 / 4096.0 * data
    if VT >= 3.3:
        return 'sensor error'
    Rt = (10.0 * VT) / (3.3 - VT)
    if Rt <= 0:
        return 'sensor error'
    try:
        temp = 1007747.0 / (math.log(Rt) * T0 - math.log(10.0) * T0 + 3380.0) - 273.15
        return f"{temp:.1f} °C"
    except (ValueError, ZeroDivisionError):
        return 'calc error'


def servo_temp_calc(data):
    """Расчёт внутренней температуры серво."""
    temp = 175.72 * data / 65536.0 - 46.85
    return f"{temp:.1f} °C"


def humidity_calc(data):
    """Расчёт влажности."""
    hum = 125.0 * data / 65536.0 - 6.0
    return f"{hum:.1f} %RH"


# Группы регистров для чтения
# (addr, name, decoder_or_None)
# decoder: callable(val) → str, или None для raw-вывода

STATUS_REGISTERS = [
    (0xFC, 'REG_VERSION', None),
    (0xFE, 'REG_VERSION_INV', None),
    (0x74, 'REG_PRODUCT_NO', None),
    (0x06, 'REG_STATUS', decode_status),
    (0x48, 'REG_EMERGENCY_STOP', decode_emergency_stop),
]

POSITION_REGISTERS = [
    (0x0C, 'REG_POSITION', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
    (0x0E, 'REG_VELOCITY', lambda v: f"{v} pos/100ms"),
    (0x10, 'REG_TORQUE', lambda v: f"{v} ({v/4095.0*100:.1f}% duty)"),
    (0x12, 'REG_VOLTAGE', lambda v: voltage_format(v)),
    (0x14, 'REG_MCU_TEMPER', lambda v: f"{v} °C" if v != 0xFFFF else 'N/A'),
    (0x16, 'REG_CURRENT', lambda v: f"{v} mA"),
    (0x18, 'REG_TURN_COUNT', lambda v: f"{v} оборотов"),
    (0x1A, 'REG_32BITS_POS_L', None),
    (0x1C, 'REG_32BITS_POS_H', None),
]

SENSOR_REGISTERS = [
    (0xD0, 'REG_MOTOR_TEMP', motor_temp_calc),
    (0xD2, 'REG_TEMP', servo_temp_calc),
    (0xD4, 'REG_HUM', humidity_calc),
]

COMM_REGISTERS = [
    (0x32, 'REG_ID', None),
    (0x38, 'REG_CAN_BAUDRATE', lambda v: CAN_BAUDRATE_MAP.get(v, f'unknown({v})')),
    (0x3C, 'REG_CAN_BUS_ID_H', None),
    (0x3E, 'REG_CAN_BUS_ID_L', None),
    (0x40, 'REG_SAMPLE_POINT', lambda v: SAMPLE_POINT_MAP.get(v, f'unknown({v})')),
    (0x6A, 'REG_CAN_MODE', lambda v: CAN_MODE_MAP.get(v, f'unknown({v})')),
]

MODE_REGISTERS = [
    (0x44, 'REG_RUN_MODE', lambda v: RUN_MODE_MAP.get(v, f'unknown({v})')),
    (0x9A, 'REG_POS_LOCK_TIME', lambda v: f"{v} сек"),
    (0x9C, 'REG_POS_LOCK_TORQUE', lambda v: f"{v}%"),
    (0xB0, 'REG_POSITION_MAX_LIM', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
    (0xB2, 'REG_POSITION_MIN_LIM', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
    (0xC2, 'REG_POS_MID', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
]

OPTION_REGISTERS = [
    (0x2E, 'REG_STREAM_TIME', lambda v: f"{v} ms" if v <= 10000 else f"{v-10000} Hz"),
    (0x30, 'REG_STREAM_MODE', lambda v: 'ON' if v == 1 else 'OFF'),
    (0x4E, 'REG_DEADBAND', lambda v: f"{v} step"),
    (0x50, 'REG_POS_MAX', lambda v: f"{v} ({pos_to_deg(v):.2f}°)" if v else 'OFF'),
    (0x52, 'REG_POS_MIN', lambda v: f"{v} ({pos_to_deg(v):.2f}°)" if v else 'OFF'),
    (0x54, 'REG_VELOCITY_MAX', lambda v: f"{v} pos/100ms"),
    (0x56, 'REG_TORQUE_MAX', lambda v: f"{v} ({v/4095.0*100:.1f}%)"),
    (0x58, 'REG_VOLTAGE_MAX', lambda v: voltage_format(v) if v else 'OFF'),
    (0x5A, 'REG_VOLTAGE_MIN', lambda v: voltage_format(v) if v else 'OFF'),
    (0x5C, 'REG_TEMPER_MAX', lambda v: f"{v} °C" if v else 'OFF'),
    (0x6C, 'REG_TEMPER_MIN', lambda v: f"{v} °C" if v else 'OFF'),
    (0x64, 'REG_INERTIA_RANGE', lambda v: 'SS OFF (100%)' if v == 0 else ('SS AUTO' if v == 1 else f"{v} ({v/4095.0*100:.1f}%)")),
    (0xDA, 'REG_SPEED_VOLTAGE', lambda v: f"{v/10.0:.1f} V" if v else 'OFF'),
    (0xDC, 'REG_SPEED_UP', lambda v: f"{v} ms"),
    (0xDE, 'REG_SPEED_DN', lambda v: f"{v} ms"),
    (0xE0, 'REG_SPEED_ES', lambda v: f"{v} ms"),
    (0xA2, 'REG_SETUP', decode_setup),
    (0xA0, 'REG_SETUP_2', None),
]

FAILSAFE_REGISTERS = [
    (0x94, 'REG_FAIL_SAFE_POS', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
    (0xB4, 'REG_FAIL_SAFE_TIME', lambda v: f"{v} ms"),
    (0x7A, 'REG_START_POSITION', lambda v: f"{v} ({pos_to_deg(v):.2f}°)"),
]

CURRENT_CIRCUIT_REGISTERS = [
    (0x26, 'REG_SPEC_TORQUE', lambda v: f"{v} ({v*10} mW)"),
    (0xD8, 'REG_CURRENT_MAX', lambda v: f"{v} mA" if v != 65535 else 'OFF'),
]

TIME_REGISTERS = [
    (0xC8, 'REG_TIME_L', None),
    (0xCA, 'REG_TIME_H', None),
]

DRONECAN_REGISTERS = [
    (0x2C, 'REG_UNITLESS_RAD', lambda v: 'radian' if v == 1 else 'unitless'),
    (0xAC, 'REG_TURN_MULTIPLIER', None),
]

USER_REGISTERS = [
    (0xC6, 'REG_ECHO', None),
    (0xCC, 'REG_USER_1', None),
    (0xCE, 'REG_USER_2', None),
]


def read_register(bus, addr, servo_id):
    """Отправить запрос на чтение регистра, дождаться ответа."""
    data = [ord('r'), servo_id, addr]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)

    start = time.time()
    while time.time() - start < 1.0:
        response = bus.recv(timeout=0.5)
        if response and not response.is_extended_id and response.dlc >= 5:
            if response.data[0] == ord('v') and response.data[2] == addr:
                val = response.data[3] | (response.data[4] << 8)
                return val
    return None


def print_section(title, bus, registers, servo_id):
    """Считать и вывести группу регистров."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    for addr, name, decoder in registers:
        val = read_register(bus, addr, servo_id)
        if val is None:
            print(f"  {name:30s} (0x{addr:02X}):  --- нет ответа ---")
        else:
            raw = f"{val} (0x{val:04X})"
            if decoder:
                decoded = decoder(val)
                print(f"  {name:30s} (0x{addr:02X}):  {raw:20s}  →  {decoded}")
            else:
                print(f"  {name:30s} (0x{addr:02X}):  {raw}")
        time.sleep(0.02)


def print_time_info(bus, servo_id):
    """Считать и показать время работы серво."""
    time_l = read_register(bus, 0xC8, servo_id)
    time.sleep(0.02)
    time_h = read_register(bus, 0xCA, servo_id)

    print(f"\n{'='*60}")
    print(f"  Время работы")
    print(f"{'='*60}")

    if time_l is not None and time_h is not None:
        total_sec = time_l + time_h * 65536
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        print(f"  REG_TIME_L                   (0xC8):  {time_l} (0x{time_l:04X})")
        print(f"  REG_TIME_H                   (0xCA):  {time_h} (0x{time_h:04X})")
        print(f"  Итого:  {total_sec} сек = {hours}ч {mins}м {secs}с")
    else:
        print("  --- не удалось считать ---")


def print_32bit_position(bus, servo_id):
    """Считать 32-битную позицию."""
    pos_l = read_register(bus, 0x1A, servo_id)
    time.sleep(0.02)
    pos_h = read_register(bus, 0x1C, servo_id)

    if pos_l is not None and pos_h is not None:
        pos_32 = pos_l | (pos_h << 16)
        if pos_32 & 0x80000000:
            pos_32 -= 0x100000000
        deg = pos_32 * 90.0 / 4096.0
        print(f"  32-бит позиция:              {pos_32} ({deg:.2f}°)")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SLCAN_PORT
    bitrate = int(sys.argv[2]) if len(sys.argv) > 2 else BITRATE
    servo_id = int(sys.argv[3]) if len(sys.argv) > 3 else SERVO_ID

    W = 58
    print(f"╔{'═'*W}╗")
    print(f"║{'Hitec CAN Servo — Считывание параметров':^{W}}║")
    print(f"╠{'═'*W}╣")
    print(f"║  Порт:     {port:<{W-13}}║")
    print(f"║  Bitrate:  {str(bitrate) + ' bps':<{W-13}}║")
    sid_str = f"{servo_id} (0=broadcast)" if servo_id == 0 else str(servo_id)
    print(f"║  Servo ID: {sid_str:<{W-13}}║")
    print(f"╚{'═'*W}╝")

    try:
        bus = can.Bus(interface='slcan', channel=port, bitrate=bitrate)
    except Exception as e:
        print(f"\nОшибка подключения: {e}")
        print("Проверьте:")
        print("  - COM-порт / USB подключён")
        print("  - QGroundControl закрыт")
        print("  - Для Pixhawk: CAN_SLCAN_CPORT=1, CAN_SLCAN_SERNUM=0")
        sys.exit(1)

    time.sleep(0.5)

    # Проверка связи
    print("\nПроверка связи...")
    ver = read_register(bus, 0xFC, servo_id)
    if ver is None:
        print("Серво не отвечает!")
        print("Проверьте подключение, питание и скорость CAN-шины.")
        bus.shutdown()
        sys.exit(1)
    print(f"Связь установлена. F/W версия: {ver}")

    # Чтение всех групп регистров
    print_section("Идентификация", bus, STATUS_REGISTERS, servo_id)
    print_section("Связь / CAN", bus, COMM_REGISTERS, servo_id)
    print_section("Режим работы / Лимиты", bus, MODE_REGISTERS, servo_id)
    print_section("Позиция / Телеметрия", bus, POSITION_REGISTERS, servo_id)
    print_32bit_position(bus, servo_id)
    print_section("Датчики", bus, SENSOR_REGISTERS, servo_id)
    print_section("Настройки движения", bus, OPTION_REGISTERS, servo_id)
    print_section("Fail-Safe / Стартовая позиция", bus, FAILSAFE_REGISTERS, servo_id)
    print_section("Токовая цепь", bus, CURRENT_CIRCUIT_REGISTERS, servo_id)
    print_section("DroneCAN", bus, DRONECAN_REGISTERS, servo_id)
    print_section("Пользовательские регистры", bus, USER_REGISTERS, servo_id)
    print_time_info(bus, servo_id)

    print(f"\n{'='*60}")
    print(f"  Считывание завершено.")
    print(f"{'='*60}")

    bus.shutdown()


if __name__ == '__main__':
    main()
