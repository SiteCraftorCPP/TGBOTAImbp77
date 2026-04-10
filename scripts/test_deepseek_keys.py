"""Проверка окружения: статистика SQLite и один вызов API (как в боте)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ai_client import DeepSeekClient
from app.config import load_settings
from app.database import Database


async def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка БД и DeepSeek API.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="только статистика БД, без запроса к модели",
    )
    args = parser.parse_args()

    settings = load_settings()
    db = Database(settings.database_path)
    db.initialize()
    print("STATS", db.get_stats())

    if args.no_llm:
        return

    keys = settings.deepseek_api_keys
    if not keys:
        print("SKIP LLM: нет DEEPSEEK_API_KEYS")
        return

    client = DeepSeekClient(
        api_keys=keys,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_answer_model,
        proxy_url=settings.deepseek_proxy_url,
        answer_max_tokens=min(settings.deepseek_answer_max_tokens, 4500),
        answer_timeout=min(settings.deepseek_answer_timeout, 90.0),
    )
    try:
        dialog = [{"role": "user", "content": "Кратко: что такое сабр в исламе?"}]
        out = await client.compose_reply(dialog)
        print("COMPOSE_OK", bool(out), (out or "")[:200])
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
