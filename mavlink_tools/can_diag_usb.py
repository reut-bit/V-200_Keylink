#!/usr/bin/env python3
"""Быстрая диагностика CAN через USB."""
import time, sys
sys.path.insert(0, '/Users/reutov/.local/pipx/venvs/mavproxy/lib/python3.13/site-packages')
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

print("\nСлушаю телеметрию 12 сек...")
seen = {}
can_devices = []
start = time.time()
while time.time() - start < 12:
    msg = master.recv_match(blocking=True, timeout=1)
    if not msg:
        continue
    mtype = msg.get_type()
    seen[mtype] = seen.get(mtype, 0) + 1
    if mtype == 'STATUSTEXT':
        print(f"  [STATUS] {msg.text.strip()}")
    elif mtype == 'GPS2_RAW' and seen[mtype] <= 2:
        can_devices.append(f"GPS2: fix={msg.fix_type} sat={msg.satellites_visible}")
    elif mtype == 'SCALED_PRESSURE3' and seen[mtype] <= 2:
        can_devices.append(f"Pressure3(CAN): {msg.press_abs:.1f} hPa")
    elif mtype == 'VFR_HUD' and seen[mtype] <= 2:
        print(f"  Airspeed={msg.airspeed:.2f} Groundspeed={msg.groundspeed:.2f}")

print("\n=== CAN-УСТРОЙСТВА ===")
if can_devices:
    for d in can_devices:
        print(f"  ✓ {d}")
else:
    print("  ✗ CAN-устройств НЕ обнаружено в телеметрии")

print("\n=== ВСЕ СООБЩЕНИЯ ===")
for mtype, cnt in sorted(seen.items()):
    mark = " ← CAN?" if mtype in ('GPS2_RAW','SCALED_PRESSURE3','ESC_TELEMETRY_1_TO_4','RAW_RPM') else ""
    print(f"  {mtype}: {cnt}{mark}")
