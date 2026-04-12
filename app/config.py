from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    deepseek_api_keys: list[str]
    deepseek_base_url: str
    deepseek_answer_model: str
    deepseek_answer_max_tokens: int
    deepseek_answer_timeout: float
    deepseek_proxy_url: str
    telegram_proxy_url: str
    database_path: Path
    payment_provider_token: str
    subscription_price_kopecks: int
    subscription_year_price_kopecks: int


def _parse_admin_ids(raw_value: str) -> set[int]:
    """Одна строка `ADMIN_IDS`: id через запятую; пустые куски и запятая в конце игнорируются."""
    values = set()
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if chunk:
            values.add(int(chunk))
    return values


def _parse_api_keys(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    return Settings(
        bot_token=bot_token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        deepseek_api_keys=_parse_api_keys(os.getenv("DEEPSEEK_API_KEYS", "")),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        deepseek_answer_model=os.getenv("DEEPSEEK_ANSWER_MODEL", "").strip()
        or os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip(),
        deepseek_answer_max_tokens=int(os.getenv("DEEPSEEK_ANSWER_MAX_TOKENS", "1400")),
        deepseek_answer_timeout=float(os.getenv("DEEPSEEK_ANSWER_TIMEOUT", "75")),
        deepseek_proxy_url=os.getenv("DEEPSEEK_PROXY_URL", os.getenv("HTTP_PROXY_URL", "")).strip(),
        telegram_proxy_url=(
            os.getenv("TELEGRAM_PROXY_URL", "").strip()
            or os.getenv("HTTP_PROXY_URL", "").strip()
        ),
        database_path=ROOT_DIR / os.getenv("DATABASE_PATH", "bot.db"),
        payment_provider_token=os.getenv("PAYMENT_PROVIDER_TOKEN", "").strip(),
        subscription_price_kopecks=int(os.getenv("SUBSCRIPTION_PRICE_KOPECKS", "10000")),
        subscription_year_price_kopecks=int(os.getenv("SUBSCRIPTION_YEAR_PRICE_KOPECKS", "50000")),
    )
