#!/bin/bash
# Сканирование DroneCAN-устройств на CAN-шине через MAVLink.
#
# Использование:
#   ./can_scan.sh              — авто-определение (USB → Ethernet 14550)
#   ./can_scan.sh usb          — подключение по USB
#   ./can_scan.sh eth          — подключение по Ethernet (порт 14550)
#
# ВАЖНО: QGroundControl должен быть закрыт при работе по Ethernet (порт 14550).
#        Для одновременной работы с QGC используйте порт 14555:
#          python3 can_scan.py udpin:0.0.0.0:14555
#        (только чтение телеметрии, запросы параметров не будут работать
#         через broadcast-поток NET_P2)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Users/reutov/.local/pipx/venvs/mavproxy/bin/python"

if [ "$1" = "eth" ]; then
    CONN="udpin:0.0.0.0:14550"
elif [ "$1" = "usb" ]; then
    PORT=$(ls /dev/tty.usbmodem* 2>/dev/null | head -1)
    if [ -z "$PORT" ]; then
        echo "USB устройство не найдено"
        exit 1
    fi
    CONN="$PORT"
else
    PORT=$(ls /dev/tty.usbmodem* 2>/dev/null | head -1)
    if [ -n "$PORT" ]; then
        CONN="$PORT"
    else
        CONN="udpin:0.0.0.0:14550"
    fi
fi

echo "Подключение: $CONN"
echo ""

exec "$PYTHON" "$SCRIPT_DIR/can_scan.py" "$CONN"
