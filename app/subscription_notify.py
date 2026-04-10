"""Фоновые уведомления: окончание подписки и напоминание перед окончанием."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.database import Database, UTC, utc_now
from app.texts import (
    SUBSCRIPTION_EXPIRED_NOTICE,
    SUBSCRIPTION_EXPIRING_SOON_NOTICE,
    subscription_renewal_keyboard,
)


def _fmt_until(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime("%d.%m.%Y %H:%M UTC")


async def _safe_send(bot: Bot, user_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(user_id, text, **kwargs)
        return True
    except (TelegramForbiddenError, TelegramBadRequest):
        return False


async def process_subscription_notifications(bot: Bot, database: Database) -> None:
    now = utc_now()
    soon = now + timedelta(days=3)

    # Истекла, ещё не уведомляли
    rows = database.list_users_for_expiry_notification()
    for user_id, until_raw in rows:
        until = Database.parse_iso_datetime(until_raw)
        if until is None or until >= now:
            continue
        ok = await _safe_send(
            bot,
            user_id,
            SUBSCRIPTION_EXPIRED_NOTICE.format(end=_fmt_until(until)),
            reply_markup=subscription_renewal_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        if ok:
            database.set_subscription_expiry_notified(user_id, True)

    # Скоро истечёт (≤3 дней), активна, ещё не предупреждали
    rows2 = database.list_users_for_expiring_soon_check()
    for user_id, until_raw in rows2:
        until = Database.parse_iso_datetime(until_raw)
        if until is None or until <= now or until > soon:
            continue
        days_left = max(0, (until - now).days)
        if days_left == 0:
            days_left = 1
        ok = await _safe_send(
            bot,
            user_id,
            SUBSCRIPTION_EXPIRING_SOON_NOTICE.format(end=_fmt_until(until), days=days_left),
            reply_markup=subscription_renewal_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        if ok:
            database.set_subscription_expiring_soon_notified(user_id, True)


async def subscription_notification_loop(bot: Bot, database: Database, interval_sec: int = 3600) -> None:
    try:
        await asyncio.sleep(15)
        with contextlib.suppress(Exception):
            await process_subscription_notifications(bot, database)
        while True:
            await asyncio.sleep(interval_sec)
            with contextlib.suppress(Exception):
                await process_subscription_notifications(bot, database)
    except asyncio.CancelledError:
        raise
