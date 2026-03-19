#!/usr/bin/env python3
"""Сканирование DroneCAN-устройств на CAN-шине через MAVLink.

Определяет устройства по DeviceId параметров (bus_type=UAVCAN),
а также выводит конфигурацию CAN-портов, GPS, компасов и ПВД.

Использование:
    python3 can_scan.py [connection_string]

    # Ethernet (по умолчанию, порт 14550):
    python3 can_scan.py udpin:0.0.0.0:14550

    # USB:
    python3 can_scan.py /dev/tty.usbmodem14301
"""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from mavlink_utils import (
    connect, fetch_params, find_can_devices, can_bus_label,
    get_can_config, decode_devid, print_header,
)

conn = sys.argv[1] if len(sys.argv) > 1 else 'udpin:0.0.0.0:14550'
master = connect(conn)
params = fetch_params(master)

# --- CAN порты ---
print_header('CAN ПОРТЫ')
for p in get_can_config(params):
    status = 'ВКЛ' if p['enabled'] else 'ВЫКЛ'
    print(f"  CAN{p['index']}: driver={p['driver']} [{status}]"
          f"  bitrate={p['bitrate']}  protocol={p['protocol']}"
          f"  node_id={p['node_id']}")
    if p['srv_bm'] or p['esc_bm']:
        print(f"         SRV_BM={p['srv_bm']}  ESC_BM={p['esc_bm']}")

# --- CAN-устройства через DEVID ---
print_header('ОБНАРУЖЕННЫЕ CAN-УСТРОЙСТВА (UAVCAN)')
devices = find_can_devices(params)
if devices:
    for d in devices:
        print(f"  {d['param']:25s}  {can_bus_label(d['bus'])}  node={d['address']}"
              f"  devtype={d['devtype']}")
else:
    print('  Не обнаружено')

# --- GPS ---
print_header('GPS')
for prefix in ['GPS1', 'GPS2']:
    gtype = int(params.get(f'{prefix}_TYPE', 0))
    if gtype == 0 and prefix == 'GPS2':
        continue
    type_map = {
        0: 'None', 1: 'Auto', 2: 'uBlox', 5: 'NMEA', 9: 'DroneCAN',
    }
    tname = type_map.get(gtype, f'Type({gtype})')
    node_id = int(params.get(f'{prefix}_CAN_NODEID', 0))
    com = int(params.get(f'{prefix}_COM_PORT', -1))
    extra = f'  can_node={node_id}' if node_id else ''
    print(f"  {prefix}: type={tname}({gtype})  com_port={com}{extra}")

# --- Компасы ---
print_header('КОМПАСЫ')
for i in ['', '2', '3', '4', '5', '6', '7', '8']:
    key = f'COMPASS_DEV_ID{i}'
    val = int(params.get(key, 0))
    if val == 0:
        continue
    info = decode_devid(val)
    idx = i if i else '1'
    bus_info = f"{info['bus_type']}"
    can_tag = f"  {can_bus_label(info['bus'])} node={info['address']}" if info['bus_type_id'] == 3 else ''
    ext_key = f'COMPASS_EXTERN{i}' if i else 'COMPASS_EXTERNAL'
    ext = int(params.get(ext_key, -1))
    ext_label = {0: 'внутр.', 1: 'внешн.'}.get(ext, '')
    print(f"  #{idx}: DEVID={val}  bus={bus_info}({info['bus']}) "
          f" devtype={info['devtype']}{can_tag}"
          f"  {ext_label}")

# --- ПВД (Airspeed) ---
print_header('ПВД (AIRSPEED)')
for prefix in ['ARSPD', 'ARSPD2']:
    enable = int(params.get(f'{prefix}_ENABLE', params.get('ARSPD_ENABLE', 0)))
    atype = int(params.get(f'{prefix}_TYPE', 0))
    if atype == 0 and prefix == 'ARSPD2':
        continue
    devid = int(params.get(f'{prefix}_DEVID', 0))
    type_map = {
        0: 'None', 1: 'Analog', 2: 'DLVR-L10D', 3: 'I2C-MS4525',
        6: 'I2C-MS5525', 8: 'DroneCAN', 11: 'SITL',
    }
    tname = type_map.get(atype, f'Type({atype})')
    detected = 'ОБНАРУЖЕН' if devid != 0 else 'НЕ ОБНАРУЖЕН'
    info_str = ''
    if devid:
        info = decode_devid(devid)
        info_str = f"  bus={info['bus_type']}({info['bus']}) node={info['address']}"
    print(f"  {prefix}: enable={enable}  type={tname}({atype})  "
          f"devid={devid} [{detected}]{info_str}")

# --- Итог ---
print_header('ИТОГ')
active_ports = sum(1 for p in get_can_config(params) if p['enabled'])
print(f'  Активных CAN-портов: {active_ports}/2')
print(f'  CAN-устройств (DEVID): {len(devices)}')
if devices:
    for d in devices:
        print(f'    ✓ {d["param"]}  →  {can_bus_label(d["bus"])} node {d["address"]}')
else:
    print('  ✗ CAN-устройств не обнаружено через DEVID')
    if active_ports:
        print('    Шины активны, но устройства не отвечают.')
        print('    Проверьте: кабели, питание, терминацию 120 Ом, физический порт CAN.')
