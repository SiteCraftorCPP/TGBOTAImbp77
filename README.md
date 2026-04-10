# Telegram-бот: Коран и достоверные хадисы (DeepSeek)

Ответы формирует нейросеть **DeepSeek** с учётом истории чата. Тексты **не** подтягиваются из локальной базы — проверяйте аяты и хадисы по Мусхафу и проверенным изданиям.

## Как устроен бот

- **На каждый вопрос** (бесплатно и с подпиской): в ответе **ровно один аят** и **ровно один хадис** — арабский текст, транскрипция, перевод, источник (структурированный шаблон в `app/advisor_prompt.py`).
- **Без подписки** после первого такого ответа новые вопросы не обрабатываются (если задан `PAYMENT_PROVIDER_TOKEN`); предлагается подписка **100 ₽ / 30 дней**.
- **С подпиской:** тот же формат **1 аят + 1 хадис** на вопрос, но **без лимита** числа вопросов за период.

## Запуск

```bash
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env`, укажите `BOT_TOKEN` и `DEEPSEEK_API_KEYS`.

```bash
python main.py
```

Проверка БД и API:

```bash
python scripts/test_deepseek_keys.py
python scripts/test_deepseek_keys.py --no-llm
```

## Подписка и оплата

1. Подключите провайдера в **[@BotFather](https://t.me/BotFather)** и получите **`PAYMENT_PROVIDER_TOKEN`**.
2. В `.env`: `PAYMENT_PROVIDER_TOKEN=...`, при необходимости `SUBSCRIPTION_PRICE_KOPECKS=10000` (100 ₽).
3. Без токена пользователь видит подсказку; админ может выдать доступ: **`/grant_sub <user_id> <дней>`** (нужен id в списке админов).

## Админ

Два (и более) админа: в `.env` одна строка **`ADMIN_IDS=id1,id2`** (лишняя запятая в конце допустима). Узнать свой Telegram user id можно у **[@userinfobot](https://t.me/userinfobot)**.

- `/admin` — список админ-команд.
- `/admin_stats` — счётчики и модель ответов.
- `/grant_sub <telegram_user_id> <дней>` — продление подписки.

## Перезапуск при сбое

`main.py` в цикле перезапускает бота после **необработанного исключения** в `run()` (пауза **`BOT_RESTART_DELAY_SEC`**, по умолчанию 5 с). **Ctrl+C** и **`SystemExit`** (например, код 2 при ошибке сети на старте) процесс не зацикливают.

На VPS автоперезапуск даёт **systemd** (`deploy/install-systemd.sh` или `deploy/tgbot.service.example`).

## Модель и лимиты

См. [DeepSeek API](https://api-docs.deepseek.com). `DEEPSEEK_ANSWER_MAX_TOKENS` по умолчанию **2560** (см. `app/config.py`); верхняя граница в клиенте — `app/ai_client.py`.

## Сеть

Telegram: `TELEGRAM_PROXY_URL` или VPN. DeepSeek: `DEEPSEEK_PROXY_URL` / `HTTP_PROXY_URL`.

## Git и VPS

Репозиторий: [github.com/SiteCraftorCPP/TGBOTAImbp77](https://github.com/SiteCraftorCPP/TGBOTAImbp77).

### Первый раз: поставить бота на VPS (проекта ещё нет)

Делается **только в новой папке** — остальные каталоги на сервере не трогаем.

1. Зайти по SSH на VPS.

2. Создать каталог под этот бот и клонировать репозиторий внутрь него (пример без `sudo`, в домашней директории):

```bash
mkdir -p ~/bots
cd ~/bots
git clone https://github.com/SiteCraftorCPP/TGBOTAImbp77.git
cd TGBOTAImbp77
```

При желании другой путь — например `/opt/tgbot-imbp77`: сначала `sudo mkdir -p /opt/tgbot-imbp77`, выдать права своему пользователю, затем `cd /opt/tgbot-imbp77` и `git clone https://github.com/SiteCraftorCPP/TGBOTAImbp77.git .` (точка в конце — клон в **текущую** пустую папку).

3. Виртуальное окружение и зависимости:

```bash
cd ~/bots/TGBOTAImbp77   # если клонировали как выше; иначе — ваш путь к проекту
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

4. Настроить секреты (в git их нет):

```bash
cp .env.example .env
nano .env   # BOT_TOKEN, DEEPSEEK_API_KEYS, ADMIN_IDS, при необходимости прокси
```

5. Проверка вручную:

```bash
python main.py
```

Остановка: Ctrl+C.

### Автозапуск (systemd)

На VPS, из **корня клона** (где лежат `main.py` и `deploy/`), подставьте свой путь и пользователя Linux:

```bash
cd ~/bots/TGBOTAImbp77
# второй аргумент — пользователь, от имени которого крутится бот (не root); при sudo обычно это вы:
sudo bash deploy/install-systemd.sh "$(pwd)" "${SUDO_USER:-$USER}"
```

Скрипт создаст `/etc/systemd/system/tgbot-imbp77.service`, выполнит `daemon-reload`, **enable** и **restart**, покажет `status`.

Полезные команды:

```bash
sudo systemctl status tgbot-imbp77   # статус и логи за последний запуск
sudo journalctl -u tgbot-imbp77 -f   # поток логов
sudo systemctl restart tgbot-imbp77  # после правок кода / .env
```

Ручная правка unit-файла: шаблон `deploy/tgbot.service.example`.

### Уже установлен: обновить код с GitHub

Только зайти **в каталог этого клона** (тот же `cd`, что в п. 2–3), больше никуда не переходить:

```bash
cd ~/bots/TGBOTAImbp77
git pull origin main
.venv/bin/pip install -r requirements.txt
```

`.env` и `bot.db` репозиторием не затираются. Затем перезапуск процесса бота (`systemctl restart …`, screen/tmux или снова `python main.py`).

### Пуш с разработческого ПК

```bash
git add -A && git commit -m "..." && git push origin main
```

Для SSH-URL: `git@github.com:SiteCraftorCPP/TGBOTAImbp77.git`.
