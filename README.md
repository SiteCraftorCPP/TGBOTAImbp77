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
3. Без токена пользователь видит подсказку; админ может выдать доступ: **`/grant_sub <user_id> <дней>`** (нужен `ADMIN_IDS`).

## Админ

- `/admin_stats` — счётчики и модель ответов.
- `/grant_sub <telegram_user_id> <дней>` — продление подписки.

## Модель и лимиты

См. [DeepSeek API](https://api-docs.deepseek.com). `DEEPSEEK_ANSWER_MAX_TOKENS` по умолчанию **2560** (см. `app/config.py`); верхняя граница в клиенте — `app/ai_client.py`.

## Сеть

Telegram: `TELEGRAM_PROXY_URL` или VPN. DeepSeek: `DEEPSEEK_PROXY_URL` / `HTTP_PROXY_URL`.

## Git и деплой на VPS

Репозиторий: [github.com/SiteCraftorCPP/TGBOTAImbp77](https://github.com/SiteCraftorCPP/TGBOTAImbp77).

**С ПК (первый пуш):** в каталоге проекта, после `git init` и коммита:

```bash
git remote add origin https://github.com/SiteCraftorCPP/TGBOTAImbp77.git
git branch -M main
git push -u origin main
```

Для входа по SSH замените URL на `git@github.com:SiteCraftorCPP/TGBOTAImbp77.git` (нужен ключ на машине, с которой пушите).

**На VPS:** клонируйте и поднимите окружение отдельно; **не коммитьте** `.env` и файлы БД — на сервере создайте `.env` из `.env.example`.

```bash
git clone https://github.com/SiteCraftorCPP/TGBOTAImbp77.git
cd TGBOTAImbp77
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # BOT_TOKEN, DEEPSEEK_API_KEYS, ...
python main.py
```

Обновление кода на VPS: `git pull` в каталоге репозитория, затем перезапуск процесса (systemd, screen, tmux и т.д.).
