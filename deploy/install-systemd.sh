#!/usr/bin/env bash
# Установка и включение systemd-сервиса tgbot-imbp77 (один раз).
# Запускать с правами root: sudo ... или уже из сессии root — без sudo.
#
#   bash deploy/install-systemd.sh /root/bots/TGBOTAImbp77 root
#   sudo bash deploy/install-systemd.sh /home/ubuntu/bots/TGBOTAImbp77 ubuntu
#
# Обновления кода на сервере: cd в проект → git pull origin main → systemctl restart tgbot-imbp77

set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Нужны права root. Пример: sudo bash $0 /home/ubuntu/bots/TGBOTAImbp77 ubuntu" >&2
  exit 1
fi

if [[ $# -ne 2 ]]; then
  echo "Использование: sudo bash $0 <абсолютный_путь_к_TGBOTAImbp77> <linux_пользователь>" >&2
  echo "Пример: sudo bash $0 /home/ubuntu/bots/TGBOTAImbp77 ubuntu" >&2
  exit 1
fi

RAW_DIR="$1"
SERVICE_USER="$2"

if ! id "$SERVICE_USER" &>/dev/null; then
  echo "Пользователь «$SERVICE_USER» не найден в системе." >&2
  exit 1
fi

PROJECT_DIR=$(cd "$RAW_DIR" && pwd)

if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
  echo "Не найден $PROJECT_DIR/main.py — проверьте путь к клону." >&2
  exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "Не найден $PROJECT_DIR/.venv/bin/python — сначала создайте venv и pip install -r requirements.txt" >&2
  exit 1
fi

UNIT=/etc/systemd/system/tgbot-imbp77.service

cat >"$UNIT" <<EOF
[Unit]
Description=TGBOTAImbp77 Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${PROJECT_DIR}/.venv/bin/python ${PROJECT_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tgbot-imbp77.service
systemctl restart tgbot-imbp77.service
echo "Сервис включён и запущен. Статус:"
systemctl --no-pager status tgbot-imbp77.service
