# Telegram-бот: Коран и достоверные хадисы (DeepSeek)

Ответы формирует нейросеть **DeepSeek** с учётом истории чата. Стиль и правила — в `app/advisor_prompt.py` (учёный, Коран и достоверная Сунна, ихтиляф, без выдуманных источников). Проверяйте цитаты по Мусхафу и проверенным изданиям.

## Как устроен бот

- **Ответ:** живой учёный тон, гибкая структура, доводы; аяты и хадисы — с арабским текстом, транскрипцией, переводом и источником.
- **Без подписки** после первого ответа новые вопросы не обрабатываются (если задан `PAYMENT_PROVIDER_TOKEN`); подписка **100 ₽ / месяц** или **500 ₽ / год** (настраивается копейками в `.env`).
- **С подпиской:** тот же режим ответов, **без лимита** числа вопросов за период.

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
2. В `.env`: `PAYMENT_PROVIDER_TOKEN=...`, при необходимости `SUBSCRIPTION_PRICE_KOPECKS=10000` (100 ₽/мес.), `SUBSCRIPTION_YEAR_PRICE_KOPECKS=50000` (500 ₽/год).
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

См. [DeepSeek API](https://api-docs.deepseek.com). `DEEPSEEK_ANSWER_MAX_TOKENS` по умолчанию **1400** (см. `app/config.py`); верхняя граница в клиенте — `app/ai_client.py`. Меньше значение — обычно быстрее и короче ответ. Модель `deepseek-reasoner` заметно медленнее `deepseek-chat`.

## Сеть

Telegram: `TELEGRAM_PROXY_URL` или VPN. DeepSeek: `DEEPSEEK_PROXY_URL` / `HTTP_PROXY_URL`.

## Git и VPS

Репозиторий: [github.com/SiteCraftorCPP/TGBOTAImbp77](https://github.com/SiteCraftorCPP/TGBOTAImbp77).

### Обновление на VPS (обычно только это)

Зайти в **каталог этого бота**, подтянуть ветку `main`, при необходимости обновить зависимости, перезапустить сервис:

```bash
cd ~/bots/TGBOTAImbp77
git pull origin main
.venv/bin/pip install -r requirements.txt
sudo systemctl restart tgbot-imbp77
```

Если systemd-сервис ещё не ставили — сначала один раз раздел **«Автозапуск (systemd)»** ниже. Без сервиса после `git pull` достаточно перезапустить `python main.py` вручную / в screen.

`.env` и `bot.db` из git не приезжают и не затираются.

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

### Автозапуск (systemd) — делается **один раз**

Нужны `main.py`, `.venv` и `.env` в каталоге проекта. Второй аргумент — **Linux-пользователь**, под которым будет работать процесс (у него должны быть права на этот каталог).

Вы уже **root**, проект в `/root/bots/TGBOTAImbp77`:

```bash
cd /root/bots/TGBOTAImbp77
bash deploy/install-systemd.sh /root/bots/TGBOTAImbp77 root
```

Обычный пользователь **ubuntu**, проект в `~/bots/TGBOTAImbp77`:

```bash
cd ~/bots/TGBOTAImbp77
sudo bash deploy/install-systemd.sh /home/ubuntu/bots/TGBOTAImbp77 ubuntu
```

Скрипт создаст `tgbot-imbp77.service`, сделает `daemon-reload`, **enable** и **restart**, покажет `status`. Дальше обновления — только **`git pull origin main`** (см. выше).

Полезные команды:

```bash
sudo systemctl status tgbot-imbp77   # статус и логи за последний запуск
sudo journalctl -u tgbot-imbp77 -f   # поток логов
sudo systemctl restart tgbot-imbp77  # после правок кода / .env
```

Ручная правка unit-файла: шаблон `deploy/tgbot.service.example`.

### Пуш с разработческого ПК

```bash
git add -A && git commit -m "..." && git push origin main
```

Для SSH-URL: `git@github.com:SiteCraftorCPP/TGBOTAImbp77.git`.
