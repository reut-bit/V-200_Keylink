"""
Сканирование CAN1 через MAVLink CAN_FRAME.
Отправляет CAN 2.0A запросы (11-bit ID) и слушает ответы.
Не требует SLCAN — работает через обычное MAVLink-соединение.
"""

import sys
import time
import serial

BAUD = 115200
TIMEOUT = 1.0

MAVLINK_V2_HEADER = 0xFD
CAN_FRAME_MSG_ID = 386      # MAVLink CAN_FRAME message ID
CAN_FILTER_MSG_ID = 387     # MAVLink CAN_FILTER_MODIFY

REGISTERS = {
    0xFC: 'REG_VERSION',
    0x6A: 'REG_CAN_MODE',
    0x38: 'REG_CAN_BAUDRATE',
    0x32: 'REG_ID',
    0x44: 'REG_RUN_MODE',
}


def mavlink_crc(buf):
    """MAVLink CRC-16/MCRF4XX."""
    crc = 0xFFFF
    for b in buf:
        tmp = b ^ (crc & 0xFF)
        tmp ^= (tmp << 4) & 0xFF
        crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)
        crc &= 0xFFFF
    return crc


def build_heartbeat():
    """MAVLink v2 HEARTBEAT для поддержания связи."""
    payload = bytes([
        0x00, 0x00, 0x00, 0x00,  # custom_mode
        0x06,                     # type = GCS
        0x00,                     # autopilot = generic
        0x00,                     # base_mode
        0x00,                     # system_status
        0x03,                     # mavlink_version
    ])
    return _build_mavlink_msg(0, payload, 50)


def _build_mavlink_msg(msg_id, payload, crc_extra, seq=0):
    header = bytes([
        MAVLINK_V2_HEADER,
        len(payload),
        0, 0,           # incompat_flags, compat_flags
        seq & 0xFF,
        255,             # system ID (GCS)
        0,               # component ID
        msg_id & 0xFF,
        (msg_id >> 8) & 0xFF,
        (msg_id >> 16) & 0xFF,
    ])
    crc_input = header[1:] + payload + bytes([crc_extra])
    crc = mavlink_crc(crc_input)
    return header + payload + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def read_mavlink_messages(ser, duration=3.0):
    """Читаем MAVLink-сообщения и выводим CAN_FRAME ответы."""
    start = time.time()
    buf = b''
    can_frames = []
    msg_types = set()

    while time.time() - start < duration:
        chunk = ser.read(256)
        if not chunk:
            continue
        buf += chunk

        while len(buf) > 12:
            idx = buf.find(bytes([MAVLINK_V2_HEADER]))
            if idx < 0:
                buf = b''
                break
            if idx > 0:
                buf = buf[idx:]

            if len(buf) < 12:
                break

            payload_len = buf[1]
            msg_len = 12 + payload_len
            if len(buf) < msg_len:
                break

            msg_id = buf[7] | (buf[8] << 8) | (buf[9] << 16)
            payload = buf[10:10 + payload_len]
            msg_types.add(msg_id)

            if msg_id == CAN_FRAME_MSG_ID and payload_len >= 16:
                can_id = int.from_bytes(payload[4:8], 'little')
                bus = payload[8]
                dlc = payload[9]
                can_data = payload[10:10 + dlc]
                is_ext = bool(can_id & 0x80000000)
                raw_id = can_id & 0x1FFFFFFF
                id_type = "EXT" if is_ext else "STD"
                print(f"  CAN [{id_type}] bus={bus} ID=0x{raw_id:03X} DLC={dlc} data={can_data.hex(' ')}")
                can_frames.append((raw_id, is_ext, can_data))

            buf = buf[msg_len:]

    return can_frames, msg_types


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/cu.usbmodem14303'
    print(f"Подключение к {port} @ {BAUD} bps (MAVLink)...")

    try:
        ser = serial.Serial(port, BAUD, timeout=TIMEOUT)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    time.sleep(1.0)
    ser.reset_input_buffer()

    print("Отправляем HEARTBEAT...")
    ser.write(build_heartbeat())
    time.sleep(0.5)

    print("\n=== Пассивное прослушивание MAVLink (5 сек) ===")
    print("Ищем CAN_FRAME сообщения...")
    frames, msg_types = read_mavlink_messages(ser, duration=5.0)

    print(f"\nОбнаруженные типы MAVLink-сообщений: {sorted(msg_types)}")
    if frames:
        print(f"Получено CAN-фреймов: {len(frames)}")
    else:
        print("CAN-фреймов не обнаружено.")
        print("  Возможно CAN_FORWARD не включен или на CAN1 нет устройств.")
        print("  Проверьте параметр CAN_D1_UC_OPTION (бит 7 = CAN forwarding).")

    ser.close()
    print("\nГотово.")


if __name__ == '__main__':
    main()
