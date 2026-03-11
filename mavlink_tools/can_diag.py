#!/usr/bin/env python3
"""
Диагностика CAN-шин через MAVLink.
Подключается к автопилоту, скачивает параметры,
слушает телеметрию и выводит состояние CAN-устройств.

Использование:
    python3 can_diag.py [--host HOST] [--port PORT] [--duration SEC]
"""

import argparse
import time
import sys

PYMAV_PATH = '/Users/reutov/.local/pipx/venvs/mavproxy/lib/python3.13/site-packages'
sys.path.insert(0, PYMAV_PATH)

from pymavlink import mavutil


def fetch_params(master, timeout=10):
    master.mav.param_request_list_send(master.target_system, master.target_component)
    params = {}
    start = time.time()
    while time.time() - start < timeout:
        msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if msg:
            params[msg.param_id] = msg.param_value
    return params


def print_section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def show_can_params(params):
    print_section("CAN ПОРТЫ")
    for prefix in ['CAN_P1', 'CAN_P2']:
        driver = params.get(f'{prefix}_DRIVER', 'N/A')
        bitrate = params.get(f'{prefix}_BITRATE', 'N/A')
        status = "ВКЛЮЧЁН" if driver and driver > 0 else "ВЫКЛЮЧЕН"
        print(f"  {prefix}: driver={int(driver)} bitrate={int(bitrate) if bitrate != 'N/A' else 'N/A'} [{status}]")

    print_section("CAN ДРАЙВЕРЫ (DroneCAN)")
    for prefix in ['CAN_D1', 'CAN_D2']:
        proto = params.get(f'{prefix}_PROTOCOL', 'N/A')
        node = params.get(f'{prefix}_UC_NODE', 'N/A')
        proto_name = {0: 'None', 1: 'DroneCAN', 4: 'PiccoloCAN'}.get(int(proto), f'Unknown({int(proto)})')
        print(f"  {prefix}: protocol={proto_name} node_id={int(node)}")


def show_arspd_params(params):
    print_section("AIRSPEED (ПВД)")
    for prefix in ['ARSPD', 'ARSPD2']:
        type_val = params.get(f'{prefix}_TYPE', 0)
        bus = params.get(f'{prefix}_BUS', -1)
        devid = params.get(f'{prefix}_DEVID', 0)
        use = params.get(f'{prefix}_USE', 0)
        enable = params.get(f'{prefix}_ENABLE', params.get('ARSPD_ENABLE', 0))
        type_name = {0: 'None', 1: 'Analog', 8: 'DroneCAN'}.get(int(type_val), f'Type({int(type_val)})')
        detected = "ОБНАРУЖЕН" if int(devid) != 0 else "НЕ ОБНАРУЖЕН"
        print(f"  {prefix}: type={type_name} bus={int(bus)} devid={int(devid)} use={int(use)} [{detected}]")


def show_gps_params(params):
    print_section("GPS")
    for prefix in ['GPS1', 'GPS2']:
        type_val = params.get(f'{prefix}_TYPE', 0)
        node_id = params.get(f'{prefix}_CAN_NODEID', 0)
        type_map = {0: 'None', 1: 'Auto', 2: 'uBlox', 22: 'DroneCAN', 23: 'DroneCAN(2)'}
        type_name = type_map.get(int(type_val), f'Type({int(type_val)})')
        print(f"  {prefix}: type={type_name} can_node_id={int(node_id) if node_id else 0}")


def listen_telemetry(master, duration=15):
    print_section(f"ТЕЛЕМЕТРИЯ ({duration} сек)")

    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

    seen = {}
    can_related = []
    start = time.time()

    while time.time() - start < duration:
        msg = master.recv_match(blocking=True, timeout=1)
        if not msg:
            continue
        mtype = msg.get_type()
        seen[mtype] = seen.get(mtype, 0) + 1

        if mtype == 'VFR_HUD' and seen[mtype] <= 2:
            print(f"  Airspeed: {msg.airspeed:.2f} m/s  |  Groundspeed: {msg.groundspeed:.2f} m/s")
        elif mtype == 'GPS_RAW_INT' and seen[mtype] <= 2:
            print(f"  GPS1: fix={msg.fix_type} sat={msg.satellites_visible}")
        elif mtype == 'GPS2_RAW':
            can_related.append(f"GPS2: fix={msg.fix_type} sat={msg.satellites_visible}")
        elif mtype == 'SCALED_PRESSURE3':
            can_related.append(f"Pressure3(CAN): {msg.press_abs:.1f} hPa diff={msg.press_diff:.4f}")
        elif mtype == 'STATUSTEXT':
            text = msg.text.strip()
            if text:
                print(f"  [AUTOPILOT] {text}")
        elif mtype == 'ESC_TELEMETRY_1_TO_4':
            can_related.append(f"ESC Telemetry: rpm={msg.rpm}")

    print_section("CAN-УСТРОЙСТВА В ТЕЛЕМЕТРИИ")
    if can_related:
        for item in can_related:
            print(f"  ✓ {item}")
    else:
        print("  ✗ CAN-устройства НЕ обнаружены в потоке телеметрии")

    print_section("ВСЕ ТИПЫ СООБЩЕНИЙ")
    for mtype, count in sorted(seen.items()):
        marker = " ← CAN?" if mtype in ('GPS2_RAW', 'SCALED_PRESSURE3', 'ESC_TELEMETRY_1_TO_4', 'RAW_RPM') else ""
        print(f"  {mtype}: {count}{marker}")


def main():
    parser = argparse.ArgumentParser(description='CAN bus diagnostics via MAVLink')
    parser.add_argument('--host', default='0.0.0.0', help='Listen host (default: 0.0.0.0)')
    parser.add_argument('--port', default=14550, type=int, help='UDP port (default: 14550)')
    parser.add_argument('--duration', default=15, type=int, help='Telemetry listen duration in seconds')
    args = parser.parse_args()

    conn_str = f'udpin:{args.host}:{args.port}'
    print(f"Подключение к {conn_str} ...")

    master = mavutil.mavlink_connection(conn_str)
    print("Ожидание heartbeat...")
    master.wait_heartbeat()
    print(f"Подключено: system={master.target_system} component={master.target_component}")

    print("\nЗагрузка параметров...")
    params = fetch_params(master)
    print(f"Получено {len(params)} параметров")

    show_can_params(params)
    show_arspd_params(params)
    show_gps_params(params)
    listen_telemetry(master, args.duration)

    print_section("ИТОГО")
    arspd_devid = int(params.get('ARSPD_DEVID', 0))
    arspd2_devid = int(params.get('ARSPD2_DEVID', 0))
    gps2_type = int(params.get('GPS2_TYPE', 0))

    if arspd_devid == 0 and arspd2_devid == 0 and gps2_type == 0:
        print("  ✗ Ни одного CAN-устройства не обнаружено")
        print("  Проверьте: кабели, питание, терминирующие резисторы (120 Ом)")
    else:
        if arspd_devid:
            print(f"  ✓ ПВД1 обнаружен (DEVID={arspd_devid})")
        if arspd2_devid:
            print(f"  ✓ ПВД2 обнаружен (DEVID={arspd2_devid})")


if __name__ == '__main__':
    main()
