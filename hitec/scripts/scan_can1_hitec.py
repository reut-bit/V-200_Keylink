"""
Сканирование CAN1 на наличие Hitec SG50BL через SLCAN.
Только чтение — никакие регистры не записываются.

Перед запуском:
  1. CAN_SLCAN_CPORT = 1
  2. CAN_SLCAN_TIMOUT = 0
  3. Перезагрузить полётник
  4. Выставить CAN_SLCAN_SERNUM = 0 (без перезагрузки!)

Использование:
  python scan_can1_hitec.py [порт] [битрейт]
  python scan_can1_hitec.py /dev/cu.usbmodem14301 1000000
"""

import can
import sys
import time

SLCAN_PORT = '/dev/cu.usbmodem14301'
BITRATE = 1000000
SERVO_ID = 0x00  # broadcast

REGISTERS = {
    0xFC: 'REG_VERSION',
    0xFE: 'REG_VERSION_INV',
    0x74: 'REG_PRODUCT_NO',
    0x06: 'REG_STATUS',
    0x6A: 'REG_CAN_MODE',
    0x38: 'REG_CAN_BAUDRATE',
    0x32: 'REG_ID',
    0x3C: 'REG_CAN_BUS_ID_H',
    0x3E: 'REG_CAN_BUS_ID_L',
    0x40: 'REG_SAMPLE_POINT',
    0x44: 'REG_RUN_MODE',
    0xA2: 'REG_SETUP',
    0xA0: 'REG_SETUP_2',
    0x2C: 'REG_UNITLESS_RAD_MODE',
}


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


def listen_passive(bus, duration=3.0):
    """Пассивное прослушивание шины — ловим любые фреймы."""
    print(f"\nПассивное прослушивание {duration} сек...")
    start = time.time()
    count = 0
    while time.time() - start < duration:
        msg = bus.recv(timeout=0.5)
        if msg:
            count += 1
            id_type = "EXT" if msg.is_extended_id else "STD"
            print(f"  [{id_type}] ID=0x{msg.arbitration_id:08X} DLC={msg.dlc} data={msg.data.hex(' ')}")
    if count == 0:
        print("  Фреймов не получено.")
    else:
        print(f"  Всего фреймов: {count}")


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SLCAN_PORT
    bitrate = int(sys.argv[2]) if len(sys.argv) > 2 else BITRATE
    print(f"Подключение к {port} @ {bitrate} bps (SLCAN)...")

    try:
        bus = can.Bus(interface='slcan', channel=port, bitrate=bitrate)
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        sys.exit(1)

    print("Подключено.\n")

    print("=== Пассивное прослушивание ===")
    listen_passive(bus)

    print("\n=== Опрос регистров (broadcast) ===")
    for addr, name in REGISTERS.items():
        read_register(bus, addr, name)

    print("\nСканирование завершено.")
    bus.shutdown()


if __name__ == '__main__':
    main()
