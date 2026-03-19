#!/bin/bash
# MAVLink хаб: принимает поток от автопилота и раздаёт на несколько приложений.
#
# ОГРАНИЧЕНИЯ:
#   Хаб ретранслирует исходящий поток автопилота → приложения.
#   Запросы параметров от приложений на --out портах НЕ ПРОХОДЯТ обратно
#   к автопилоту надёжно. Для скана с параметрами — напрямую на 14550.
#
# После запуска:
#   - QGroundControl:     Comm Links → UDP → Port: 14551
#   - Мониторинг:         python3 can_scan.py udpin:127.0.0.1:14552
#                         (только телеметрия, БЕЗ запроса параметров)
#
# DroneCAN GUI Tool (прямой доступ к CAN-шине):
#   Закрыть хаб и QGC, затем:
#     dronecan_gui_tool
#     Interface: mavcan:0.0.0.0:14550
#     Bus Number: 2 (CAN2) или 1 (CAN1)
#     CAN bus bit rate: 1000000
#     → OK → нажать галочку у Node ID 127
#
# Полный скан (с параметрами):
#   Закрыть хаб и QGC, затем: ./can_scan.sh eth
#
# Остановка: Ctrl+C

echo "=== MAVLink Hub ==="
echo ""
echo "Автопилот → MAVProxy → QGC (14551) + Tools (14552)"
echo ""
echo "⚠  Хаб: только ретрансляция. Для скана с параметрами — напрямую 14550."
echo ""
echo "Настройка QGC:"
echo "  Comm Links → Add → UDP → Port: 14551 → Connect"
echo ""
echo "Остановка: Ctrl+C"
echo "---"

mavproxy.py \
    --master=udpin:0.0.0.0:14550 \
    --master=udpin:0.0.0.0:14555 \
    --out=udp:127.0.0.1:14551 \
    --out=udp:127.0.0.1:14552 \
    --non-interactive
