from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Кнопки (лимит Telegram ~64 символа)
BUTTON_ASK_QUESTION = "💬 Задать вопрос"
BUTTON_ADMIN_PANEL = "🛠 Админ-панель"
BUTTON_SUB_MONTH = "💳 100 ₽ — месяц"
BUTTON_SUB_YEAR = "💳 600 ₽ — год"


def subscription_pay_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Две инлайн-кнопки оплаты: месяц и год (после пробного, при блокировке, в уведомлениях)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BUTTON_SUB_MONTH, callback_data="sub_month"),
                InlineKeyboardButton(text=BUTTON_SUB_YEAR, callback_data="sub_year"),
            ],
        ]
    )


def subscription_renewal_keyboard() -> InlineKeyboardMarkup:
    """Продление — те же два тарифа."""
    return subscription_pay_tariffs_keyboard()


START_TEXT = (
    "📖 <b>Quran Sunnah AI</b>\n\n"
    "🕌 Этот бот отвечает на вопросы, опираясь только на <b>Коран</b>, <b>достоверную Сунну</b> "
    "и понимание <b>праведных предшественников</b>.\n\n"
    "📜 <b>В ответах приводятся:</b>\n"
    " • аяты Корана — с арабским текстом, транскрипцией и переводом;\n"
    " • достоверные хадисы — с указанием источника;\n"
    " • слова признанных учёных: Абу Ханифа, Малик, аш-Шафии, Ахмад, ан-Навави, Ибн Таймия и других.\n\n"
    "⚖️ Если среди учёных есть разногласия — они разъясняются спокойно и с доводами, "
    "с указанием более сильного мнения.\n\n"
    "🛡️ Бот <b>не говорит от себя</b> и не приводит неподтверждённых мнений.\n\n"
    "🎯 <b>Цель</b> — разъяснение религии на основе доказательств и приближение к истине.\n\n"
    "───────────────\n"
    "💎 <b>Подписка</b>\n"
    " • <b>1 месяц</b> — <b>100 ₽</b>\n"
    " • <b>1 год</b> — <b>600 ₽</b>\n"
    "───────────────\n\n"
    "✨ <b>Как это работает</b>\n"
    " • 🎁 без подписки — <b>один</b> бесплатный ответ на ваш вопрос;\n"
    " • 💎 с подпиской — сколько угодно вопросов за оплаченный период;\n"
    " • 📅 <code>/sub_status</code> — срок подписки.\n\n"
    "✍️ <b>Примеры вопросов</b> (на русском):\n"
    " • «Что в Исламе сказано о родителях?»\n"
    " • «Как относиться к обиде?»\n"
    " • «Что делать, если тревожно?»\n"
    " • «Что Коран и Сунна говорят о намазе?»\n"
    " • «Как Ислам относится к честности в торговле?»\n\n"
    "👇 Нажмите кнопку ниже и напишите вопрос в чат."
)

ASSISTANT_UNAVAILABLE_TEXT = (
    "⚠️ Не удалось получить ответ от модели. Проверьте DEEPSEEK_API_KEYS в .env, баланс API и сеть "
    "(при блокировке — прокси DEEPSEEK_PROXY_URL)."
)

EMPTY_QUERY_TEXT = "✍️ Напишите вопрос текстом на русском языке."

ASK_QUESTION_INLINE_HINT = "💬 Напишите вопрос одним сообщением на русском языке."

NEXT_QUESTION_HINT = "💬 Задайте следующий вопрос:"

SUBSCRIPTION_OFFER_AFTER_FREE = (
    "✅ Ответ отправлен."
)

SUBSCRIPTION_REQUIRED_TEXT = (
    "🔒 Бесплатный лимит вопросов исчерпан (5/5).\n\n"
    "💳 Дальше доступ по подписке: <b>100 ₽ / месяц</b> или <b>600 ₽ / год</b>."
)

SUBSCRIPTION_PAYMENT_MANUAL_TEXT = (
    "💳 Оплата через Telegram пока не подключена.\n\n"
    "Когда подключите — тарифы: <b>100 ₽ / месяц</b> и <b>600 ₽ / год</b>."
)

SUBSCRIPTION_THANK_YOU_MONTH = (
    "🎉 Подписка активна на <b>30 дней</b> (тариф <b>100 ₽ / месяц</b>)!\n\n"
    "💎 Ответы в стиле учёного с доводами из Корана и Сунны.\n"
    "♾️ Вопросов в период подписки — без лимита.\n"
    "📜 История вопросов: <code>/my_questions</code>\n\n"
    "📅 Срок: <code>/sub_status</code>"
)

SUBSCRIPTION_THANK_YOU_YEAR = (
    "🎉 Подписка активна на <b>365 дней</b> (тариф <b>600 ₽ / год</b>)!\n\n"
    "💎 Ответы в стиле учёного с доводами из Корана и Сунны.\n"
    "♾️ Вопросов в период подписки — без лимита.\n"
    "📜 История вопросов: <code>/my_questions</code>\n\n"
    "📅 Срок: <code>/sub_status</code>"
)

SUBSCRIPTION_EXPIRED_NOTICE = (
    "🔔 <b>Подписка завершилась</b> (окончание: {end}).\n\n"
    "💎 Продлите: <b>100 ₽ / месяц</b> или <b>600 ₽ / год</b> — кнопки ниже 👇"
)

SUBSCRIPTION_EXPIRING_SOON_NOTICE = (
    "⏳ <b>Подписка скоро закончится</b>: {end} (примерно <b>{days}</b> дн.).\n\n"
    "💳 Продлите заранее — кнопки ниже 👇"
)

SUBSCRIPTION_INVOICE_TITLE = "📚 Подписка Quran Sunnah AI"
SUBSCRIPTION_INVOICE_DESC_MONTH = (
    "30 дней безлимита вопросов. Ответы с доводами из Корана и достоверной Сунны."
)
SUBSCRIPTION_INVOICE_DESC_YEAR = (
    "365 дней безлимита вопросов. Ответы с доводами из Корана и достоверной Сунны."
)

INVOICE_PAYLOAD_SUB_MONTH = "sub_month_100rub_v1"
INVOICE_PAYLOAD_SUB_YEAR = "sub_year_600rub_v1"
