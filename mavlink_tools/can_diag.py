#!/usr/bin/env python3
"""Полная диагностика CAN-шин и периферии через MAVLink.

Выводит конфигурацию CAN, обнаруженные устройства (по DEVID),
параметры GPS/компасов/ПВД/баро, и слушает телеметрию.

Использование:
    python3 can_diag.py [--port PORT] [--duration SEC]
"""
import argparse, time, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from mavlink_utils import (
    connect, fetch_params, find_can_devices, can_bus_label,
    get_can_config, decode_devid, print_header, mavutil,
)


def show_can_config(params):
    print_header('CAN ПОРТЫ И ДРАЙВЕРЫ')
    for p in get_can_config(params):
        status = 'ВКЛ' if p['enabled'] else 'ВЫКЛ'
        print(f"  CAN{p['index']}: driver={p['driver']} [{status}]"
              f"  bitrate={p['bitrate']}  protocol={p['protocol']}"
              f"  node_id={p['node_id']}")
        print(f"         SRV_BM={p['srv_bm']}  ESC_BM={p['esc_bm']}")
    loglevel = int(params.get('CAN_LOGLEVEL', 0))
    print(f'\n  CAN_LOGLEVEL={loglevel}')


def show_can_devices(params):
    print_header('CAN-УСТРОЙСТВА (UAVCAN DEVID)')
    devices = find_can_devices(params)
    if devices:
        for d in devices:
            print(f"  {d['param']:25s}  {can_bus_label(d['bus'])}  node={d['address']}"
                  f"  devtype={d['devtype']}")
    else:
        print('  Не обнаружено')
    return devices


def show_all_devids(params):
    print_header('ВСЕ DEVID')
    for key in sorted(params):
        if 'DEV' not in key or 'ID' not in key:
            continue
        val = int(params[key])
        if val == 0:
            continue
        info = decode_devid(val)
        tag = ' <<< CAN' if info['bus_type_id'] == 3 else ''
        print(f"  {key:25s} = {val:>10}  {info['bus_type']:7s}"
              f"  bus={info['bus']}  addr={info['address']}"
              f"  devtype={info['devtype']}{tag}")


def show_gps(params):
    print_header('GPS')
    type_map = {0: 'None', 1: 'Auto', 2: 'uBlox', 5: 'NMEA', 9: 'DroneCAN'}
    for prefix in ['GPS1', 'GPS2']:
        gtype = int(params.get(f'{prefix}_TYPE', 0))
        if gtype == 0 and prefix == 'GPS2':
            continue
        tname = type_map.get(gtype, f'Type({gtype})')
        node_id = int(params.get(f'{prefix}_CAN_NODEID', 0))
        com = int(params.get(f'{prefix}_COM_PORT', -1))
        print(f"  {prefix}: type={tname}({gtype})  com_port={com}"
              f"  can_node={node_id}")


def show_compass(params):
    print_header('КОМПАСЫ')
    for i in ['', '2', '3', '4', '5', '6', '7', '8']:
        key = f'COMPASS_DEV_ID{i}'
        val = int(params.get(key, 0))
        if val == 0:
            continue
        info = decode_devid(val)
        idx = i if i else '1'
        can_tag = f'  {can_bus_label(info["bus"])} node={info["address"]}' if info['bus_type_id'] == 3 else ''
        ext_key = f'COMPASS_EXTERN{i}' if i else 'COMPASS_EXTERNAL'
        ext = {0: 'внутр.', 1: 'внешн.'}.get(int(params.get(ext_key, -1)), '')
        prio_key = f'COMPASS_PRIO{idx}_ID'
        prio = int(params.get(prio_key, 0))
        prio_tag = ' [приоритет]' if prio == val else ''
        print(f"  #{idx}: {info['bus_type']}  bus={info['bus']}"
              f"  devtype={info['devtype']}{can_tag}  {ext}{prio_tag}")


def show_airspeed(params):
    print_header('ПВД (AIRSPEED)')
    type_map = {0: 'None', 1: 'Analog', 2: 'DLVR', 3: 'MS4525',
                6: 'MS5525', 8: 'DroneCAN', 11: 'SITL'}
    for prefix in ['ARSPD', 'ARSPD2']:
        enable = int(params.get(f'{prefix}_ENABLE', params.get('ARSPD_ENABLE', 0)))
        atype = int(params.get(f'{prefix}_TYPE', 0))
        if atype == 0 and prefix == 'ARSPD2':
            continue
        devid = int(params.get(f'{prefix}_DEVID', 0))
        tname = type_map.get(atype, f'Type({atype})')
        detected = 'ОБНАРУЖЕН' if devid != 0 else 'НЕ ОБНАРУЖЕН'
        info_str = ''
        if devid:
            info = decode_devid(devid)
            info_str = f"  {info['bus_type']}(bus={info['bus']}) node={info['address']}"
        print(f"  {prefix}: enable={enable}  type={tname}({atype})"
              f"  devid={devid} [{detected}]{info_str}")


def show_baro(params):
    print_header('БАРОМЕТРЫ')
    for prefix in ['BARO1', 'BARO2', 'BARO3']:
        key = f'{prefix}_DEVID'
        val = int(params.get(key, 0))
        if val == 0:
            continue
        info = decode_devid(val)
        can_tag = f'  {can_bus_label(info["bus"])} node={info["address"]}' if info['bus_type_id'] == 3 else ''
        print(f"  {prefix}: {info['bus_type']}  bus={info['bus']}"
              f"  devtype={info['devtype']}{can_tag}")


def listen_telemetry(master, duration=15):
    print_header(f'ТЕЛЕМЕТРИЯ ({duration} сек)')
    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

    seen = {}
    start = time.time()
    while time.time() - start < duration:
        msg = master.recv_match(blocking=True, timeout=1)
        if not msg:
            continue
        mtype = msg.get_type()
        seen[mtype] = seen.get(mtype, 0) + 1

        if mtype == 'VFR_HUD' and seen[mtype] <= 2:
            print(f"  Airspeed: {msg.airspeed:.2f} m/s  "
                  f"Groundspeed: {msg.groundspeed:.2f} m/s")
        elif mtype == 'GPS_RAW_INT' and seen[mtype] <= 2:
            print(f"  GPS: fix={msg.fix_type} sat={msg.satellites_visible}")
        elif mtype == 'STATUSTEXT':
            t = msg.text.strip()
            if t:
                print(f"  [autopilot] {t}")

    print_header('ТИПЫ СООБЩЕНИЙ')
    for mt, cnt in sorted(seen.items(), key=lambda x: -x[1]):
        flag = ''
        if 'GPS' in mt or 'PRESS' in mt:
            flag = ' ← GPS/Baro'
        if 'ESC' in mt or 'RPM' in mt:
            flag = ' ← ESC/CAN'
        print(f'  {mt}: {cnt}{flag}')


def main():
    parser = argparse.ArgumentParser(description='Полная диагностика CAN через MAVLink')
    parser.add_argument('conn', nargs='?', default='udpin:0.0.0.0:14550',
                        help='Строка подключения (default: udpin:0.0.0.0:14550)')
    parser.add_argument('--duration', default=15, type=int,
                        help='Длительность прослушивания телеметрии (сек)')
    args = parser.parse_args()

    master = connect(args.conn)
    params = fetch_params(master)

    show_can_config(params)
    devices = show_can_devices(params)
    show_all_devids(params)
    show_gps(params)
    show_compass(params)
    show_airspeed(params)
    show_baro(params)
    listen_telemetry(master, args.duration)

    print_header('ИТОГ')
    active = sum(1 for p in get_can_config(params) if p['enabled'])
    print(f'  Активных CAN-портов: {active}/2')
    print(f'  CAN-устройств (DEVID): {len(devices)}')
    for d in devices:
        print(f'    ✓ {d["param"]}  →  {can_bus_label(d["bus"])} node {d["address"]}')
    if not devices and active:
        print('  ✗ Шины активны, устройств нет. Проверьте железо.')


if __name__ == '__main__':
    main()
