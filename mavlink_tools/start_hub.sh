#!/bin/bash
# MAVLink хаб: принимает поток от автопилота и раздаёт на несколько приложений.
#
# После запуска:
#   - QGroundControl:     подключить UDP на порт 14551
#   - DroneCAN GUI Tool:  подключить MAVLink udpin:127.0.0.1:14552
#   - can_scan.py:        ./can_scan.py udpin:127.0.0.1:14552
#
# Остановка: Ctrl+C

echo "=== MAVLink Hub ==="
echo ""
echo "Автопилот → MAVProxy → QGC (14551) + Tools (14552)"
echo ""
echo "Настройка QGC:"
echo "  Comm Links → Add → UDP → Port: 14551 → Connect"
echo ""
echo "Настройка DroneCAN GUI Tool:"
echo "  MAVLink → udpin:127.0.0.1:14552"
echo ""
echo "Запуск can_scan.py:"
echo "  ./can_scan.py udpin:127.0.0.1:14552"
echo ""
echo "---"

mavproxy.py \
    --master=udpin:0.0.0.0:14550 \
    --master=udpin:0.0.0.0:14555 \
    --out=udp:127.0.0.1:14551 \
    --out=udp:127.0.0.1:14552 \
    --non-interactive
