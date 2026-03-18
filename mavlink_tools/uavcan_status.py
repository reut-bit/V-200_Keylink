#!/usr/bin/env python3
"""Запрос статуса DroneCAN-нод через MAVLink."""
import time, sys, os

sys.path.insert(0, '/Users/reutov/.local/pipx/venvs/mavproxy/lib/python3.13/site-packages')
os.environ['MAVLINK20'] = '1'
from pymavlink import mavutil

port = sys.argv[1] if len(sys.argv) > 1 else '/dev/tty.usbmodem14301'
print(f"Подключение к {port} ...")
master = mavutil.mavlink_connection(port, baud=115200)
print("Ожидание heartbeat...")
master.wait_heartbeat()
print(f"Подключено: system={master.target_system}")

master.mav.request_data_stream_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

print("\nСлушаю DroneCAN-ноды (15 сек)...\n")

seen_nodes = {}
start = time.time()
while time.time() - start < 15:
    msg = master.recv_match(blocking=True, timeout=1)
    if not msg:
        continue
    mtype = msg.get_type()

    if mtype == 'UAVCAN_NODE_STATUS':
        nid = getattr(msg, 'node_id', '?')
        health = getattr(msg, 'health', '?')
        mode = getattr(msg, 'mode', '?')
        uptime = getattr(msg, 'uptime_sec', 0)
        seen_nodes[nid] = {'health': health, 'mode': mode, 'uptime': uptime}
        if len(seen_nodes) == 1 or nid not in seen_nodes:
            print(f"  [NODE] id={nid} health={health} mode={mode} uptime={uptime}s")

    elif mtype == 'UAVCAN_NODE_INFO':
        nid = getattr(msg, 'node_id', '?')
        name = getattr(msg, 'name', '?')
        print(f"  [INFO] id={nid} name={name}")

    elif mtype == 'STATUSTEXT':
        text = msg.text.strip()
        if text:
            print(f"  [STATUS] {text}")

print("\n" + "=" * 50)
print("  РЕЗУЛЬТАТ: DroneCAN ноды на шине")
print("=" * 50)
if seen_nodes:
    health_map = {0: 'OK', 1: 'WARNING', 2: 'ERROR', 3: 'CRITICAL'}
    mode_map = {0: 'OPERATIONAL', 1: 'INITIALIZATION', 2: 'MAINTENANCE', 3: 'SOFTWARE_UPDATE'}
    for nid, info in sorted(seen_nodes.items()):
        h = health_map.get(info['health'], str(info['health']))
        m = mode_map.get(info['mode'], str(info['mode']))
        print(f"  Node {nid}: health={h}, mode={m}, uptime={info['uptime']}s")
else:
    print("  Ни одной DroneCAN-ноды не обнаружено")
