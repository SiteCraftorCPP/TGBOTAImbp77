from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction, ContentType, ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from app.advisor_prompt import NO_RELIABLE_VERSE_HADITH_REPLY
from app.ai_client import DeepSeekClient
from app.config import load_settings
from app.database import Database, UTC, utc_now
from app.subscription_notify import subscription_notification_loop
from app.tg_text import split_telegram_message
from app.texts import (
    ASK_QUESTION_INLINE_HINT,
    ASSISTANT_UNAVAILABLE_TEXT,
    BUTTON_ASK_QUESTION,
    EMPTY_QUERY_TEXT,
    INVOICE_PAYLOAD_SUB_MONTH,
    INVOICE_PAYLOAD_SUB_YEAR,
    NEXT_QUESTION_HINT,
    START_TEXT,
    SUBSCRIPTION_INVOICE_DESC_MONTH,
    SUBSCRIPTION_INVOICE_DESC_YEAR,
    SUBSCRIPTION_INVOICE_TITLE,
    SUBSCRIPTION_OFFER_AFTER_FREE,
    SUBSCRIPTION_PAYMENT_MANUAL_TEXT,
    SUBSCRIPTION_REQUIRED_TEXT,
    SUBSCRIPTION_THANK_YOU_MONTH,
    SUBSCRIPTION_THANK_YOU_YEAR,
    subscription_pay_tariffs_keyboard,
)


def _parse_command_limit(message_text: str | None, default: int, max_limit: int) -> int:
    parts = (message_text or "").split()
    if len(parts) < 2:
        return default
    try:
        return min(max_limit, max(1, int(parts[1])))
    except ValueError:
        return default

SUB_WATCH_INTERVAL_SEC = 3600


def _fmt_sub_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime("%d.%m.%Y %H:%M UTC")

DIALOG_MESSAGES_FOR_MODEL = 14

_TYPING_REFRESH_SEC = 4.5


def _normalize_for_refusal_compare(text: str) -> str:
    """Схлопываем пробелы и варианты апострофа — модель может выдать другой символ в «а'лям»."""
    t = text.strip()
    for ch in ("\u2019", "\u2018", "\u0060", "\u02bc", "\u02b9"):
        t = t.replace(ch, "'")
    return " ".join(t.split())


def _is_refusal_reply(body: str) -> bool:
    return _normalize_for_refusal_compare(body) == _normalize_for_refusal_compare(
        NO_RELIABLE_VERSE_HADITH_REPLY
    )


async def _typing_keepalive(bot: Bot, chat_id: int) -> None:
    try:
        while True:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
            await asyncio.sleep(_TYPING_REFRESH_SEC)
    except asyncio.CancelledError:
        raise


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BUTTON_ASK_QUESTION, callback_data="ask_question")],
        ]
    )


def subscription_cta_keyboard() -> InlineKeyboardMarkup:
    """Только две кнопки оплаты по тарифам (месяц / год)."""
    return subscription_pay_tariffs_keyboard()


async def build_dispatcher() -> tuple[Dispatcher, DeepSeekClient, Database]:
    settings = load_settings()
    payment_configured = bool(settings.payment_provider_token)
    database = Database(settings.database_path)
    database.initialize()

    ai_client = DeepSeekClient(
        api_keys=settings.deepseek_api_keys,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_answer_model,
        proxy_url=settings.deepseek_proxy_url,
        answer_max_tokens=settings.deepseek_answer_max_tokens,
        answer_timeout=settings.deepseek_answer_timeout,
    )
    if settings.deepseek_api_keys:
        await ai_client.warm_http()

    dispatcher = Dispatcher()

    async def reply_long_text(msg: Message, body: str) -> None:
        for part in split_telegram_message(body):
            await msg.answer(part)

    async def reply_admin_plain(msg: Message, body: str) -> None:
        for part in split_telegram_message(body):
            await msg.answer(part)

    def _is_admin(uid: int | None) -> bool:
        return uid is not None and uid in settings.admin_ids

    @dispatcher.message(Command("admin"))
    async def admin_panel_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user or not _is_admin(message.from_user.id):
            return
        await reply_admin_plain(
            message,
            "\n".join(
                [
                    "🔧 Админ-панель",
                    "",
                    "/admin_payments [N] — последние оплаты Telegram (N по умолч. 15, макс. 100)",
                    "/admin_subscriptions [N] — активные подписки (N по умолч. 30, макс. 150)",
                    "/admin_stats — счётчики",
                    "/grant_sub <user_id> <дней> — выдать/продлить подписку",
                ]
            ),
        )

    @dispatcher.message(Command("admin_payments"))
    async def admin_payments_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user or not _is_admin(message.from_user.id):
            return
        n = _parse_command_limit(message.text, 15, 100)
        rows = database.list_recent_payments(limit=n)
        if not rows:
            await message.answer("💳 Записей об оплатах пока нет.")
            return
        lines = [f"💳 Последние оплаты (до {n}):", ""]
        for row in rows:
            uid = int(row["user_id"])
            un = row["username"] or "—"
            amt = int(row["total_amount"])
            cur = str(row["currency"])
            if cur == "RUB":
                price_shown = f"{amt / 100:.2f} ₽"
            else:
                price_shown = f"{amt} {cur} (minor units)"
            paid = str(row["paid_at"])[:19].replace("T", " ")
            tg_ch = str(row["telegram_payment_charge_id"])
            if len(tg_ch) > 36:
                tg_ch = tg_ch[:36] + "…"
            lines.append(
                f"#{row['id']} user {uid} @{un} | {price_shown} | {paid} UTC\n"
                f"   payload: {row['invoice_payload']}\n"
                f"   tg_charge: {tg_ch}"
            )
        await reply_admin_plain(message, "\n".join(lines))

    @dispatcher.message(Command("admin_subscriptions"))
    async def admin_subscriptions_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user or not _is_admin(message.from_user.id):
            return
        n = _parse_command_limit(message.text, 30, 150)
        rows = database.list_active_subscription_rows(limit=n)
        if not rows:
            await message.answer("📭 Активных подписок нет.")
            return
        lines = [f"💎 Активные подписки (до {n}):", ""]
        for row in rows:
            uid = int(row["user_id"])
            un = row["username"] or "—"
            name = (row["full_name"] or "")[:40]
            until = database.parse_iso_datetime(str(row["subscription_until"]))
            started = database.parse_iso_datetime(str(row["subscription_period_start"]))
            lines.append(
                f"• {uid} @{un} — {name}\n"
                f"  до: {_fmt_sub_dt(until)} | период с: {_fmt_sub_dt(started)}"
            )
        await reply_admin_plain(message, "\n".join(lines))

    @dispatcher.message(Command("sub_status"))
    async def sub_status_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user:
            return
        uid = message.from_user.id
        if database.has_active_subscription(uid):
            until = database.get_subscription_until(uid)
            started = database.get_subscription_period_start(uid)
            await message.answer(
                "💎 <b>Подписка активна</b>\n\n"
                f"📅 Начало текущего периода: <b>{_fmt_sub_dt(started)}</b>\n"
                f"📅 Окончание: <b>{_fmt_sub_dt(until)}</b>\n"
                "💰 При продлении: <b>100 ₽ / месяц</b> или <b>600 ₽ / год</b>.\n\n"
                "Ответы с доводами из Корана и Сунны; вопросов в период подписки — без лимита.",
                parse_mode=ParseMode.HTML,
            )
        else:
            until = database.get_subscription_until(uid)
            extra = ""
            if until is not None and until <= utc_now():
                extra = f"\n\nПоследнее окончание: {_fmt_sub_dt(until)}"
            await message.answer(
                "📭 Активной подписки нет.\n\n"
                "💳 Оформите доступ: <b>100 ₽ / месяц</b> или <b>600 ₽ / год</b> — кнопки ниже или /start."
                + extra,
                reply_markup=subscription_cta_keyboard(),
                parse_mode=ParseMode.HTML,
            )

    @dispatcher.message(Command("my_questions"))
    async def my_questions_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user:
            return
        qs = database.get_recent_questions(message.from_user.id, limit=15)
        if not qs:
            await message.answer("📜 Сохранённых вопросов пока нет.")
            return
        lines = ["📜 Последние вопросы (новые сверху):\n"]
        for i, q in enumerate(qs, start=1):
            short = q if len(q) <= 200 else q[:197] + "…"
            lines.append(f"{i}. {short}")
        await message.answer("\n".join(lines))

    @dispatcher.message(Command("start"))
    async def start_handler(message: Message) -> None:
        await ensure_user(message)
        if message.from_user:
            database.reset_user_dialog_and_queue(message.from_user.id)
        await message.answer(
            START_TEXT,
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    @dispatcher.message(Command("admin_stats"))
    async def admin_stats_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user or not _is_admin(message.from_user.id):
            return
        stats = database.get_stats()
        await message.answer(
            "\n".join(
                [
                    "📊 Статистика",
                    f"👥 Пользователи: {stats['users']}",
                    f"❓ Вопросы: {stats['questions']}",
                    f"💬 Сообщения в диалогах: {stats['messages']}",
                    f"💳 Оплат в журнале: {stats['payments']}",
                    "",
                    f"🤖 Модель ответов: {settings.deepseek_answer_model}",
                    "",
                    "Панель: /admin",
                ]
            )
        )

    @dispatcher.message(Command("grant_sub"))
    async def grant_sub_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user or not _is_admin(message.from_user.id):
            return
        parts = (message.text or "").split()
        if len(parts) < 3:
            await message.answer("📋 Формат: /grant_sub <user_id> <дней>")
            return
        try:
            target_id = int(parts[1])
            days = int(parts[2])
        except ValueError:
            await message.answer("user_id и дней должны быть числами.")
            return
        if days < 1 or days > 3650:
            await message.answer("Количество дней от 1 до 3650.")
            return
        database.ensure_minimal_user(target_id)
        database.extend_subscription_days(target_id, days)
        u_until = database.get_subscription_until(target_id)
        u_start = database.get_subscription_period_start(target_id)
        await message.answer(
            "✅ Подписка для <code>{uid}</code> продлена на {days} дн.\n"
            "📅 Начало периода: {start}\n📅 Окончание: {end}".format(
                uid=target_id,
                days=days,
                start=_fmt_sub_dt(u_start),
                end=_fmt_sub_dt(u_until),
            ),
            parse_mode=ParseMode.HTML,
        )

    @dispatcher.callback_query(F.data == "ask_question")
    async def ask_question_callback(callback: CallbackQuery) -> None:
        if callback.message:
            await callback.message.answer(ASK_QUESTION_INLINE_HINT)
        await callback.answer()

    @dispatcher.callback_query(F.data.in_({"sub_month", "sub_year", "subscribe"}))
    async def subscribe_pay_callback(callback: CallbackQuery) -> None:
        await callback.answer()
        if not callback.message or not callback.from_user:
            return
        chat_id = callback.message.chat.id
        if not settings.payment_provider_token:
            await callback.message.answer(SUBSCRIPTION_PAYMENT_MANUAL_TEXT, parse_mode=ParseMode.HTML)
            return
        # «subscribe» — старые клавиатуры; считаем как месяц.
        is_year = callback.data == "sub_year"
        if is_year:
            payload = INVOICE_PAYLOAD_SUB_YEAR
            amount = settings.subscription_year_price_kopecks
            description = SUBSCRIPTION_INVOICE_DESC_YEAR
            price_label = "📆 365 дней"
        else:
            payload = INVOICE_PAYLOAD_SUB_MONTH
            amount = settings.subscription_price_kopecks
            description = SUBSCRIPTION_INVOICE_DESC_MONTH
            price_label = "📅 30 дней"
        await callback.bot.send_invoice(
            chat_id=chat_id,
            title=SUBSCRIPTION_INVOICE_TITLE,
            description=description,
            payload=payload,
            currency="RUB",
            prices=[LabeledPrice(label=price_label, amount=amount)],
            provider_token=settings.payment_provider_token,
        )

    @dispatcher.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
        q = pre_checkout_query
        if q.currency != "RUB":
            await bot.answer_pre_checkout_query(q.id, ok=False, error_message="Поддерживается только RUB.")
            return
        if q.invoice_payload == INVOICE_PAYLOAD_SUB_MONTH:
            expected = settings.subscription_price_kopecks
        elif q.invoice_payload == INVOICE_PAYLOAD_SUB_YEAR:
            expected = settings.subscription_year_price_kopecks
        else:
            await bot.answer_pre_checkout_query(q.id, ok=False, error_message="Неизвестный счёт.")
            return
        if q.total_amount != expected:
            await bot.answer_pre_checkout_query(q.id, ok=False, error_message="Сумма не совпадает.")
            return
        await bot.answer_pre_checkout_query(q.id, ok=True)

    @dispatcher.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
    async def successful_payment_handler(message: Message) -> None:
        if not message.from_user or not message.successful_payment:
            return
        pay = message.successful_payment
        payload = str(pay.invoice_payload or "")
        if payload == INVOICE_PAYLOAD_SUB_MONTH:
            days = 30
            thank = SUBSCRIPTION_THANK_YOU_MONTH
        elif payload == INVOICE_PAYLOAD_SUB_YEAR:
            days = 365
            thank = SUBSCRIPTION_THANK_YOU_YEAR
        else:
            return
        u = message.from_user
        database.upsert_user(
            user_id=u.id,
            username=u.username,
            full_name=u.full_name or "—",
            is_admin=u.id in settings.admin_ids,
        )
        prov = getattr(pay, "provider_payment_charge_id", None)
        database.record_payment(
            user_id=u.id,
            currency=str(pay.currency or "RUB"),
            total_amount=int(pay.total_amount),
            invoice_payload=payload,
            telegram_payment_charge_id=str(pay.telegram_payment_charge_id),
            provider_payment_charge_id=str(prov) if prov else None,
        )
        database.extend_subscription_days(message.from_user.id, days)
        await message.answer(
            thank,
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )

    @dispatcher.message(F.text)
    async def question_handler(message: Message) -> None:
        await ensure_user(message)
        if not message.from_user:
            return

        user_id = message.from_user.id
        text = (message.text or "").strip()
        if not text:
            await message.answer(EMPTY_QUERY_TEXT)
            return
        if text.startswith("/"):
            return
        if len(text) > 700:
            await message.answer("📏 Запрос слишком длинный. Сформулируйте вопрос короче.")
            return

        subscribed = database.has_active_subscription(user_id)
        free_ok = not database.get_free_bundle_used(user_id)

        if not subscribed and not free_ok:
            await message.answer(
                SUBSCRIPTION_REQUIRED_TEXT,
                reply_markup=subscription_cta_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if not settings.deepseek_api_keys:
            await message.answer(ASSISTANT_UNAVAILABLE_TEXT)
            return

        database.append_chat_message(user_id, "user", text)
        database.save_question(user_id, text)

        dialog = database.get_dialog_messages(user_id, limit=DIALOG_MESSAGES_FOR_MODEL)

        typing_task = asyncio.create_task(_typing_keepalive(message.bot, message.chat.id))
        try:
            reply = await ai_client.compose_reply(dialog)
        finally:
            typing_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await typing_task

        if not reply or not reply.strip():
            await message.answer(ASSISTANT_UNAVAILABLE_TEXT)
            await message.answer(NEXT_QUESTION_HINT, reply_markup=main_menu_keyboard())
            return

        reply_body = reply.strip()
        await reply_long_text(message, reply_body)
        database.append_chat_message(user_id, "assistant", reply_body)

        if not subscribed and free_ok:
            if not _is_refusal_reply(reply_body):
                database.set_free_bundle_used(user_id, True)
                await message.answer(
                    SUBSCRIPTION_OFFER_AFTER_FREE,
                    reply_markup=subscription_cta_keyboard(),
                    parse_mode=ParseMode.HTML,
                )
            else:
                await message.answer(NEXT_QUESTION_HINT, reply_markup=main_menu_keyboard())
        else:
            await message.answer(NEXT_QUESTION_HINT, reply_markup=main_menu_keyboard())

    async def ensure_user(message: Message) -> None:
        user = message.from_user
        if not user:
            return
        database.upsert_user(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name or "—",
            is_admin=user.id in settings.admin_ids,
        )

    return dispatcher, ai_client, database


async def run() -> None:
    settings = load_settings()
    proxy = settings.telegram_proxy_url
    if proxy:
        session = AiohttpSession(proxy=proxy)
        bot = Bot(token=settings.bot_token, session=session)
        print("Telegram: запросы через прокси (TELEGRAM_PROXY_URL или HTTP_PROXY_URL).")
    else:
        bot = Bot(token=settings.bot_token)
        print(
            "Telegram: прямое подключение без прокси. "
            "Если видите «Server disconnected» — задайте TELEGRAM_PROXY_URL или HTTP_PROXY_URL в .env либо VPN."
        )

    dispatcher, deepseek_client, database = await build_dispatcher()
    notify_task = asyncio.create_task(
        subscription_notification_loop(bot, database, interval_sec=SUB_WATCH_INTERVAL_SEC)
    )
    try:
        me = await bot.get_me()
    except TelegramNetworkError as exc:
        print(
            "\n---\n"
            "Не удалось достучаться до api.telegram.org (сеть, блокировка или неверный прокси).\n"
            "Что сделать:\n"
            "  • Укажите в .env TELEGRAM_PROXY_URL=socks5://user:pass@host:port (часто нужен SOCKS5).\n"
            "  • Или задайте HTTP_PROXY_URL — он же подставится для Telegram, если TELEGRAM_PROXY_URL пуст.\n"
            "  • Либо включите системный VPN и оставьте прокси пустым.\n"
            f"Ошибка: {exc!r}\n---\n"
        )
        raise SystemExit(2) from exc

    print(f"Ок: @{me.username} (id={me.id}), запуск long polling…")
    if not settings.deepseek_api_keys:
        print(
            "Внимание: DEEPSEEK_API_KEYS пуст — ответы ИИ недоступны, пользователи увидят сообщение об ошибке."
        )
    try:
        await dispatcher.start_polling(bot)
    finally:
        notify_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await notify_task
        await deepseek_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
