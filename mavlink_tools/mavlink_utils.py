#!/usr/bin/env python3
"""Общие утилиты для MAVLink-скриптов: подключение, параметры, DEVID-декодер."""
import time, sys, os

PYMAV_PATH = '/Users/reutov/.local/pipx/venvs/mavproxy/lib/python3.13/site-packages'
sys.path.insert(0, PYMAV_PATH)
os.environ['MAVLINK20'] = '1'

from pymavlink import mavutil

BUS_TYPE_NAMES = {
    0: 'Unknown', 1: 'I2C', 2: 'SPI', 3: 'UAVCAN',
    4: 'SITL', 5: 'MSP', 6: 'SERIAL', 7: 'QSPI',
}

PROTOCOL_NAMES = {0: 'None', 1: 'DroneCAN', 4: 'PiccoloCAN'}


def connect(conn_str, wait=True):
    """Подключение к автопилоту. Возвращает mavutil.mavlink_connection."""
    baud = 115200 if '/dev/' in conn_str else 0
    print(f'Подключение к {conn_str} ...')
    master = mavutil.mavlink_connection(conn_str, baud=baud) if baud else \
             mavutil.mavlink_connection(conn_str)
    if wait:
        print('Ожидание heartbeat...')
        master.wait_heartbeat()
        print(f'Подключено: system={master.target_system}\n')
    return master


def fetch_params(master, timeout=20):
    """Запрос всех параметров. Возвращает dict {param_id: value}."""
    master.mav.param_request_list_send(master.target_system, master.target_component)
    params = {}
    total = None
    start = time.time()
    while time.time() - start < timeout:
        msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if msg:
            params[msg.param_id] = msg.param_value
            if total is None:
                total = msg.param_count
            if total and len(params) >= total:
                break
    print(f'  Получено {len(params)}/{total or "?"} параметров\n')
    return params


def decode_devid(devid):
    """Декодирование ArduPilot DeviceId (AP_HAL/Device.h).

    Раскладка битов:
      0-2:   bus_type (3 бита): 0=Unknown 1=I2C 2=SPI 3=UAVCAN ...
      3-7:   bus (5 бит): внутренний _driver_index (0-based)
             для UAVCAN: 0 → CAN1, 1 → CAN2
      8-15:  address (8 бит): для UAVCAN = node ID
      16-23: devtype (8 бит)
    """
    d = int(devid)
    if d == 0:
        return None
    return {
        'bus_type_id': d & 0x07,
        'bus_type': BUS_TYPE_NAMES.get(d & 0x07, '?'),
        'bus': (d >> 3) & 0x1F,
        'address': (d >> 8) & 0xFF,
        'devtype': (d >> 16) & 0xFF,
    }


def find_can_devices(params):
    """Поиск CAN-устройств по DeviceId в параметрах (bus_type=3 → UAVCAN)."""
    devices = []
    for key in sorted(params):
        if 'DEV' not in key or 'ID' not in key:
            continue
        val = int(params[key])
        if val == 0:
            continue
        info = decode_devid(val)
        if info and info['bus_type_id'] == 3:
            devices.append({'param': key, 'raw': val, **info})
    return devices


def can_bus_label(driver_index):
    """driver_index (из DEVID bus field, 0-based) → физический порт CAN.

    ArduPilot DEVID bus = внутренний _driver_index (0-based):
      0 → CAN_D1 (CAN_P1_DRIVER=1) → физический CAN1
      1 → CAN_D2 (CAN_P2_DRIVER=2) → физический CAN2
    """
    return f'CAN{driver_index + 1}'


def get_can_config(params):
    """Конфигурация CAN-портов и драйверов из параметров."""
    ports = []
    for i in [1, 2]:
        drv = int(params.get(f'CAN_P{i}_DRIVER', 0))
        br = int(params.get(f'CAN_P{i}_BITRATE', 0))
        proto = int(params.get(f'CAN_D{i}_PROTOCOL', 0))
        node = int(params.get(f'CAN_D{i}_UC_NODE', 0))
        srv_bm = int(params.get(f'CAN_D{i}_UC_SRV_BM', 0))
        esc_bm = int(params.get(f'CAN_D{i}_UC_ESC_BM', 0))
        ports.append({
            'index': i, 'driver': drv, 'bitrate': br,
            'protocol': PROTOCOL_NAMES.get(proto, f'?({proto})'),
            'node_id': node, 'srv_bm': srv_bm, 'esc_bm': esc_bm,
            'enabled': drv > 0,
        })
    return ports


def print_header(title):
    """Заголовок секции."""
    print(f'\n{"="*55}')
    print(f'  {title}')
    print(f'{"="*55}')
