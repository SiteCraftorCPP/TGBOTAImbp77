"""Ограничения Telegram Bot API на длину одного текстового сообщения."""

from __future__ import annotations

# Документация: до 4096 символов; берём запас на возможные отличия подсчёта.
TELEGRAM_MESSAGE_SAFE_LIMIT = 4000


def split_telegram_message(text: str, max_len: int = TELEGRAM_MESSAGE_SAFE_LIMIT) -> list[str]:
    """Разбивает текст на части, каждая не длиннее max_len (по символам Python str)."""
    if not text:
        return []
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    i = 0
    n = len(text)
    min_break = max_len // 3

    while i < n:
        j = min(i + max_len, n)
        if j >= n:
            tail = text[i:n].strip()
            if tail:
                chunks.append(tail)
            break

        window = text[i:j]
        break_at = -1
        for sep in ("\n\n", "\n"):
            pos = window.rfind(sep)
            if pos >= min_break:
                break_at = pos + len(sep)
                break
        if break_at < 0:
            sp = window.rfind(" ")
            if sp >= min_break:
                break_at = sp + 1
        if break_at <= 0:
            break_at = max_len

        piece = text[i : i + break_at].strip()
        if piece:
            chunks.append(piece)
        i = i + break_at
        while i < n and text[i] in " \n\r\t":
            i += 1

    return chunks
