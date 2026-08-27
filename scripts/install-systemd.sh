#!/bin/sh
set -eu

REPO_DIR="${INNAWARE_PMS_REPO_DIR:-/opt/innaware/innaware-pms-emulator}"
DATA_DIR="${INNAWARE_PMS_DATA_DIR:-/var/lib/innaware-pms-emulator}"
BIND_ADDR="${INNAWARE_PMS_BIND:-127.0.0.1}"
PORT="${INNAWARE_PMS_PORT:-8080}"
SERVICE_USER="innaware-pms-emulator"
UNIT_SOURCE="$REPO_DIR/packaging/systemd/innaware-pms-emulator.service"
UNIT_TARGET="/etc/systemd/system/innaware-pms-emulator.service"
DEFAULT_FILE="/etc/default/innaware-pms-emulator"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root (sudo)." >&2
    exit 1
fi

for cmd in python3 systemctl install; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "Required command not found: $cmd" >&2
        exit 1
    }
done

[ -f "$REPO_DIR/pyproject.toml" ] || {
    echo "Repository not found at $REPO_DIR" >&2
    exit 1
}
[ -f "$UNIT_SOURCE" ] || {
    echo "Systemd unit template not found at $UNIT_SOURCE" >&2
    exit 1
}

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$DATA_DIR" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

if getent group dialout >/dev/null 2>&1; then
    usermod -aG dialout "$SERVICE_USER"
fi

install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR"

if [ ! -x "$REPO_DIR/.venv/bin/python" ]; then
    python3 -m venv "$REPO_DIR/.venv"
fi
"$REPO_DIR/.venv/bin/python" -m pip install --upgrade pip
"$REPO_DIR/.venv/bin/python" -m pip install -e "$REPO_DIR"

install -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
cat > "$DEFAULT_FILE" <<EOF
INNAWARE_PMS_BIND=$BIND_ADDR
INNAWARE_PMS_PORT=$PORT
INNAWARE_PMS_DATA_DIR=$DATA_DIR
EOF
chmod 0644 "$DEFAULT_FILE"

systemctl daemon-reload
systemctl enable --now innaware-pms-emulator.service

echo ""
echo "InnAware PMS Emulator service installed."
echo "Service: innaware-pms-emulator.service"
echo "Bind:    $BIND_ADDR:$PORT"
echo "Data:    $DATA_DIR"
echo ""
echo "Check status with:"
echo "  systemctl status innaware-pms-emulator.service --no-pager"
echo "  journalctl -u innaware-pms-emulator.service -n 100 --no-pager"
