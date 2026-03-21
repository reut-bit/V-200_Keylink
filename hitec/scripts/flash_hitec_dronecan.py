"""
Прошивка Hitec SG50BL: CAN 2.0A -> DroneCAN.
Записывает регистры через SLCAN и сохраняет конфигурацию.

Использование:
  python flash_hitec_dronecan.py <порт> <node_id>
  python flash_hitec_dronecan.py /dev/cu.usbmodem14301 55
"""

import can
import sys
import time

SLCAN_PORT = '/dev/cu.usbmodem14301'
BITRATE = 1000000  # серво уже на 1000 kbps
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
    node_id = int(sys.argv[2]) if len(sys.argv) > 2 else 55

    print(f"=== Прошивка Hitec SG50BL на DroneCAN ===")
    print(f"Порт: {port}")
    print(f"Node ID: {node_id}")
    print(f"Bitrate CAN: {BITRATE} bps")
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
        print("\nСерво не отвечает! Проверьте подключение.")
        bus.shutdown()
        sys.exit(1)

    print(f"\nСвязь OK. Версия: {ver}, режим: {mode}")
    print()

    # --- Шаг 2: Запись регистров ---
    print("--- Шаг 2: Запись регистров ---")

    write_register(bus, 0x6A, 2, "REG_CAN_MODE = 2 (DroneCAN)")
    write_register(bus, 0x38, 0, "REG_CAN_BAUDRATE = 0 (1000 kbps)")
    write_register(bus, 0x32, node_id, f"REG_ID = {node_id}")
    write_register(bus, 0x3C, 0, "REG_CAN_BUS_ID_H = 0")
    write_register(bus, 0x3E, 128, "REG_CAN_BUS_ID_L = 128")
    write_register(bus, 0x40, 1, "REG_SAMPLE_POINT = 1 (87.5%)")
    write_register(bus, 0x44, 1, "REG_RUN_MODE = 1 (Servo Mode)")
    print()

    # --- Шаг 3: Верификация ---
    print("--- Шаг 3: Верификация записанных значений ---")
    read_register(bus, 0x6A, "REG_CAN_MODE")
    read_register(bus, 0x38, "REG_CAN_BAUDRATE")
    read_register(bus, 0x32, "REG_ID")
    read_register(bus, 0x3C, "REG_CAN_BUS_ID_H")
    read_register(bus, 0x3E, "REG_CAN_BUS_ID_L")
    read_register(bus, 0x40, "REG_SAMPLE_POINT")
    read_register(bus, 0x44, "REG_RUN_MODE")
    print()

    # --- Шаг 4: Сохранение ---
    print("--- Шаг 4: Сохранение в память ---")
    time.sleep(0.2)
    write_register(bus, 0x70, 0xFFFF, "REG_CONFIG_SAVE = 0xFFFF")

    print("Ожидание 2 секунды...")
    time.sleep(2.0)

    print()
    print(f"Готово! Отключите и включите питание серво.")
    print(f"После перезагрузки серво будет на DroneCAN @ 1000 kbps, Node ID = {node_id}.")

    bus.shutdown()


if __name__ == '__main__':
    main()
