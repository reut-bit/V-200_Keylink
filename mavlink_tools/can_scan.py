#!/usr/bin/env python3
"""Сканирование DroneCAN-нод на CAN-шине через MAVLink."""
import time, sys, os
os.environ['MAVLINK20'] = '1'
sys.path.insert(0, '/Users/reutov/.local/pipx/venvs/mavproxy/lib/python3.13/site-packages')
from pymavlink import mavutil

conn = sys.argv[1] if len(sys.argv) > 1 else '/dev/tty.usbmodem14301'
baud = 115200 if '/dev/' in conn else 0

print(f'Подключение к {conn} ...')
if baud:
    master = mavutil.mavlink_connection(conn, baud=baud)
else:
    master = mavutil.mavlink_connection(conn)

print('Ожидание heartbeat...')
master.wait_heartbeat()
print(f'Подключено: system={master.target_system}\n')

master.mav.request_data_stream_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

master.mav.param_request_list_send(master.target_system, master.target_component)
params = {}
start = time.time()
while time.time() - start < 8:
    msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
    if msg:
        params[msg.param_id] = msg.param_value

print('=== CAN ПОРТЫ ===')
for i in [1, 2]:
    drv = int(params.get(f'CAN_P{i}_DRIVER', 0))
    br = int(params.get(f'CAN_P{i}_BITRATE', 0))
    proto_drv = int(params.get(f'CAN_D{i}_PROTOCOL', 0))
    proto_name = {0: 'None', 1: 'DroneCAN', 4: 'PiccoloCAN'}.get(proto_drv, f'?({proto_drv})')
    status = 'ВКЛ' if drv > 0 else 'ВЫКЛ'
    print(f'  CAN{i}: driver={drv} [{status}]  bitrate={br}  protocol={proto_name}')

srv1 = int(params.get('CAN_D1_UC_SRV_BM', 0))
srv2 = int(params.get('CAN_D2_UC_SRV_BM', 0))
esc1 = int(params.get('CAN_D1_UC_ESC_BM', 0))
esc2 = int(params.get('CAN_D2_UC_ESC_BM', 0))
print(f'\n  SRV bitmask: D1={srv1} D2={srv2}')
print(f'  ESC bitmask: D1={esc1} D2={esc2}')

print(f'\n=== СКАНИРОВАНИЕ DRONECAN НОД (12 сек) ===\n')
nodes = {}
node_names = {}
start = time.time()
while time.time() - start < 12:
    msg = master.recv_match(blocking=True, timeout=1)
    if not msg:
        continue
    mtype = msg.get_type()
    if mtype == 'UAVCAN_NODE_STATUS':
        nid = msg.node_id
        h = {0: 'OK', 1: 'WARNING', 2: 'ERROR', 3: 'CRITICAL'}.get(msg.health, str(msg.health))
        m = {0: 'OPERATIONAL', 1: 'INIT', 2: 'MAINTENANCE', 3: 'SW_UPDATE'}.get(msg.mode, str(msg.mode))
        if nid not in nodes:
            print(f'  [+] Node {nid}: health={h}  mode={m}  uptime={msg.uptime_sec}s')
        nodes[nid] = (h, m, msg.uptime_sec)
    elif mtype == 'UAVCAN_NODE_INFO':
        name = bytes(msg.name).decode('utf-8', errors='ignore').strip('\x00')
        node_names[msg.node_id] = name
        print(f'  [i] Node {msg.node_id}: name="{name}"')
    elif mtype == 'STATUSTEXT':
        t = msg.text.strip()
        if t:
            print(f'  [autopilot] {t}')

print(f'\n{"="*50}')
if nodes:
    print(f'  Найдено {len(nodes)} DroneCAN нод(а):\n')
    for nid, (h, m, u) in sorted(nodes.items()):
        name = node_names.get(nid, '')
        extra = f'  "{name}"' if name else ''
        print(f'    Node {nid}: health={h}  mode={m}  uptime={u}s{extra}')
else:
    print('  DroneCAN нод НЕ обнаружено')
print(f'{"="*50}')
