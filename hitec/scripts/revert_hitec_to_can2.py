"""
Возврат Hitec SG50BL из DroneCAN обратно в CAN 2.0A.

Что восстанавливается:
  REG_CAN_MODE    (0x6A): 2 (DroneCAN) → 0 (CAN 2.0A)
  REG_SAMPLE_POINT (0x40): 1 (87.5%)  → 0 (50%) — заводской дефолт

Что остаётся без изменений:
  REG_CAN_BAUDRATE (0x38): 0 (1000 kbps) — уже было таким до прошивки
  REG_CAN_BUS_ID_H (0x3C): 0
  REG_CAN_BUS_ID_L (0x3E): 128
  REG_RUN_MODE     (0x44): 1 (Servo Mode)

Использование:
  python revert_hitec_to_can2.py <порт> [can_id]
  python revert_hitec_to_can2.py /dev/cu.usbmodem14301
  python revert_hitec_to_can2.py /dev/cu.usbmodem14301 1
"""

import can
import sys
import time

SLCAN_PORT = '/dev/cu.usbmodem14301'
BITRATE = 1000000  # серво сейчас на 1000 kbps
SERVO_ID = 0x00    # broadcast — обращаемся ко всем серво на шине


def write_register(bus, addr, value, name):
    data = [ord('w'), SERVO_ID, addr, value & 0xFF, (value >> 8) & 0xFF]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)
    time.sleep(0.05)
    print(f"  [WR] {name} (0x{addr:02X}) = {value} (0x{value:04X})")


def read_register(bus, addr, name):
    data = [ord('r'), SERVO_ID, addr]
    msg = can.Message(arbitration_id=0x00, data=data, is_extended_id=False)
    bus.send(msg)

    start = time.time()
    while time.time() - start < 1.0:
        response = bus.recv(timeout=0.5)
        if response and not response.is_extended_id and response.dlc >= 5:
            if response.data[0] == ord('v') and response.data[2] == addr:
                val = response.data[3] | (response.data[4] << 8)
                print(f"  [RD] {name} (0x{addr:02X}) = {val} (0x{val:04X})")
                return val
    print(f"  [--] {name} (0x{addr:02X}): нет ответа")
    return None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SLCAN_PORT
    can_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # заводской дефолт CAN 2.0A ID

    print("=== Возврат Hitec SG50BL: DroneCAN → CAN 2.0A ===")
    print(f"Порт:     {port}")
    print(f"CAN ID:   {can_id}  (REG_ID в режиме CAN 2.0A)")
    print(f"Bitrate:  {BITRATE} bps")
    print()

    try:
        bus = can.Bus(interface='slcan', channel=port, bitrate=BITRATE)
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        sys.exit(1)

    time.sleep(0.5)

    # --- Шаг 1: Проверка связи ---
    print("--- Шаг 1: Проверка связи ---")
    ver = read_register(bus, 0xFC, "REG_VERSION")
    mode = read_register(bus, 0x6A, "REG_CAN_MODE")

    if ver is None:
        print("\nСерво не отвечает! Проверьте подключение и питание.")
        bus.shutdown()
        sys.exit(1)

    mode_names = {0: "CAN 2.0A", 1: "CAN 2.0B", 2: "DroneCAN"}
    print(f"\nСвязь OK. Версия: {ver}, текущий режим: {mode} ({mode_names.get(mode, '?')})")
    print()

    # --- Шаг 2: Восстановление регистров ---
    print("--- Шаг 2: Восстановление регистров ---")
    write_register(bus, 0x6A, 0,      "REG_CAN_MODE = 0 (CAN 2.0A)")
    write_register(bus, 0x32, can_id, f"REG_ID = {can_id}")
    write_register(bus, 0x40, 0,      "REG_SAMPLE_POINT = 0 (50%) — заводской дефолт")
    print()

    # --- Шаг 3: Верификация ---
    print("--- Шаг 3: Верификация ---")
    mode_val   = read_register(bus, 0x6A, "REG_CAN_MODE")
    id_val     = read_register(bus, 0x32, "REG_ID")
    baud_val   = read_register(bus, 0x38, "REG_CAN_BAUDRATE")
    sample_val = read_register(bus, 0x40, "REG_SAMPLE_POINT")
    print()

    ok = (mode_val == 0 and id_val == can_id and sample_val == 0)
    if not ok:
        print("ВНИМАНИЕ: Не все значения записались корректно! Повторите процедуру.")
        bus.shutdown()
        sys.exit(1)

    # --- Шаг 4: Сохранение ---
    print("--- Шаг 4: Сохранение в память ---")
    time.sleep(0.2)
    write_register(bus, 0x70, 0xFFFF, "REG_CONFIG_SAVE = 0xFFFF")

    print("Ожидание 2 секунды...")
    time.sleep(2.0)

    print()
    print("Готово! Отключите и включите питание серво.")
    print(f"После перезагрузки серво будет работать по CAN 2.0A @ 1000 kbps, ID = {can_id}.")

    bus.shutdown()


if __name__ == '__main__':
    main()
