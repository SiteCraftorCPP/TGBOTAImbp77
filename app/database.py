from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    next_reply_is_hadith INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    normalized_question TEXT NOT NULL,
                    asked_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    invoice_payload TEXT NOT NULL,
                    telegram_payment_charge_id TEXT NOT NULL,
                    provider_payment_charge_id TEXT,
                    paid_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    UNIQUE(telegram_payment_charge_id)
                );
                """
            )
            self._migrate_user_reply_phase(connection)
            self._migrate_subscription_fields(connection)
            self._migrate_subscription_period_and_notifications(connection)
            connection.commit()

    @staticmethod
    def _migrate_user_reply_phase(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "next_reply_is_hadith" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN next_reply_is_hadith INTEGER NOT NULL DEFAULT 0"
            )

    @staticmethod
    def _migrate_subscription_fields(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "free_bundle_used" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN free_bundle_used INTEGER NOT NULL DEFAULT 0"
            )
        if "subscription_until" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN subscription_until TEXT")

    @staticmethod
    def _migrate_subscription_period_and_notifications(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "subscription_period_start" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN subscription_period_start TEXT")
        if "subscription_expiry_notified" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN subscription_expiry_notified INTEGER NOT NULL DEFAULT 0"
            )
        if "subscription_expiring_soon_notified" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN subscription_expiring_soon_notified INTEGER NOT NULL DEFAULT 0"
            )

    @staticmethod
    def parse_iso_datetime(raw: str | None) -> datetime | None:
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            return None

    def ensure_minimal_user(self, user_id: int) -> None:
        """Создаёт строку users, если её ещё нет (для /grant_sub до первого /start)."""
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO users(user_id, username, full_name, is_admin, created_at, updated_at)
                VALUES(?, NULL, ?, 0, ?, ?)
                """,
                (user_id, "— (ещё не заходил в бота)", now, now),
            )
            connection.commit()

    def upsert_user(self, user_id: int, username: str | None, full_name: str, is_admin: bool) -> None:
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO users(user_id, username, full_name, is_admin, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    is_admin=excluded.is_admin,
                    updated_at=excluded.updated_at
                """,
                (user_id, username, full_name, int(is_admin), now, now),
            )
            connection.commit()

    def save_question(self, user_id: int, question: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO questions(user_id, question, normalized_question, asked_at)
                VALUES(?, ?, ?, ?)
                """,
                (user_id, question, normalize_text(question), utc_now().isoformat()),
            )
            connection.commit()

    def append_chat_message(self, user_id: int, role: str, content: str) -> None:
        role = role.strip().lower()
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO chat_messages(user_id, role, content, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (user_id, role, content[:12000], now),
            )
            connection.commit()

    def get_dialog_messages(self, user_id: int, limit: int = 40) -> list[dict[str, str]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        chronological = list(reversed(rows))
        return [{"role": row["role"], "content": row["content"]} for row in chronological]

    def reset_user_dialog_and_queue(self, user_id: int) -> None:
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
            connection.execute(
                """
                UPDATE users SET next_reply_is_hadith = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (now, user_id),
            )
            connection.commit()

    def get_free_bundle_used(self, user_id: int) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT free_bundle_used FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return False
        return bool(row["free_bundle_used"])

    def set_free_bundle_used(self, user_id: int, value: bool = True) -> None:
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE users SET free_bundle_used = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (int(value), now, user_id),
            )
            connection.commit()

    def get_subscription_until(self, user_id: int) -> datetime | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT subscription_until FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self.parse_iso_datetime(row["subscription_until"])

    def get_subscription_period_start(self, user_id: int) -> datetime | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT subscription_period_start FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self.parse_iso_datetime(row["subscription_period_start"])

    def set_subscription_until(self, user_id: int, until: datetime | None) -> None:
        now = utc_now().isoformat()
        val = until.isoformat() if until else None
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE users SET subscription_until = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (val, now, user_id),
            )
            connection.commit()

    def has_active_subscription(self, user_id: int) -> bool:
        until = self.get_subscription_until(user_id)
        if until is None:
            return False
        return until > utc_now()

    def extend_subscription_days(self, user_id: int, days: int = 30) -> None:
        """Продлевает подписку; при новом периоде после паузы фиксирует дату начала."""
        current = self.get_subscription_until(user_id)
        now = utc_now()
        now_iso = now.isoformat()
        with closing(self._connect()) as connection:
            if current and current > now:
                new_until = current + timedelta(days=days)
                connection.execute(
                    """
                    UPDATE users SET
                        subscription_until = ?,
                        subscription_expiry_notified = 0,
                        subscription_expiring_soon_notified = 0,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_until.isoformat(), now_iso, user_id),
                )
            else:
                new_until = now + timedelta(days=days)
                connection.execute(
                    """
                    UPDATE users SET
                        subscription_until = ?,
                        subscription_period_start = ?,
                        subscription_expiry_notified = 0,
                        subscription_expiring_soon_notified = 0,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (new_until.isoformat(), now_iso, now_iso, user_id),
                )
            connection.commit()

    def list_users_for_expiry_notification(self) -> list[tuple[int, str]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT user_id, subscription_until FROM users
                WHERE subscription_expiry_notified = 0
                  AND subscription_until IS NOT NULL
                  AND TRIM(subscription_until) != ''
                """
            ).fetchall()
        return [(int(row["user_id"]), str(row["subscription_until"])) for row in rows]

    def list_users_for_expiring_soon_check(self) -> list[tuple[int, str]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT user_id, subscription_until FROM users
                WHERE subscription_expiring_soon_notified = 0
                  AND subscription_until IS NOT NULL
                  AND TRIM(subscription_until) != ''
                """
            ).fetchall()
        return [(int(row["user_id"]), str(row["subscription_until"])) for row in rows]

    def set_subscription_expiry_notified(self, user_id: int, value: bool) -> None:
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE users SET subscription_expiry_notified = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (int(value), now, user_id),
            )
            connection.commit()

    def set_subscription_expiring_soon_notified(self, user_id: int, value: bool) -> None:
        now = utc_now().isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE users SET subscription_expiring_soon_notified = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (int(value), now, user_id),
            )
            connection.commit()

    def get_recent_questions(self, user_id: int, limit: int = 15) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT question FROM questions
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [str(row["question"]) for row in rows]

    def get_stats(self) -> dict[str, int]:
        with closing(self._connect()) as connection:
            users = connection.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            questions = connection.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
            messages = connection.execute("SELECT COUNT(*) AS c FROM chat_messages").fetchone()["c"]
            try:
                payments = connection.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
            except sqlite3.OperationalError:
                payments = 0
        return {"users": users, "questions": questions, "messages": messages, "payments": payments}

    def record_payment(
        self,
        user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> bool:
        """Логирует успешную оплату Telegram. Повтор с тем же telegram_payment_charge_id — игнор."""
        now = utc_now().isoformat()
        cur: sqlite3.Cursor
        with closing(self._connect()) as connection:
            cur = connection.execute(
                """
                INSERT OR IGNORE INTO payments(
                    user_id, currency, total_amount, invoice_payload,
                    telegram_payment_charge_id, provider_payment_charge_id, paid_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    currency.strip().upper(),
                    int(total_amount),
                    invoice_payload[:512],
                    telegram_payment_charge_id[:256],
                    (provider_payment_charge_id or "")[:256] or None,
                    now,
                ),
            )
            connection.commit()
        return cur.rowcount > 0

    def list_recent_payments(self, limit: int = 20) -> list[sqlite3.Row]:
        limit = max(1, min(100, int(limit)))
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT p.id, p.user_id, u.username, p.currency, p.total_amount, p.invoice_payload,
                       p.telegram_payment_charge_id, p.provider_payment_charge_id, p.paid_at
                FROM payments p
                LEFT JOIN users u ON u.user_id = p.user_id
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def count_payments(self) -> int:
        with closing(self._connect()) as connection:
            try:
                return int(connection.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"])
            except sqlite3.OperationalError:
                return 0

    def list_payments_page(self, limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
        limit = max(1, min(100, int(limit)))
        offset = max(0, int(offset))
        with closing(self._connect()) as connection:
            return connection.execute(
                """
                SELECT p.id, p.user_id, u.username, p.currency, p.total_amount, p.paid_at
                FROM payments p
                LEFT JOIN users u ON u.user_id = p.user_id
                ORDER BY p.id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

    def list_active_subscription_rows(self, limit: int = 40) -> list[sqlite3.Row]:
        """Пользователи с непустым subscription_until; активность отфильтровать по времени в коде."""
        limit = max(1, min(150, int(limit)))
        now = utc_now()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT user_id, username, full_name, subscription_until, subscription_period_start
                FROM users
                WHERE subscription_until IS NOT NULL AND TRIM(subscription_until) != ''
                ORDER BY subscription_until DESC
                LIMIT 400
                """
            ).fetchall()
        active: list[sqlite3.Row] = []
        for row in rows:
            until = self.parse_iso_datetime(str(row["subscription_until"]))
            if until is not None and until > now:
                active.append(row)
                if len(active) >= limit:
                    break
        return active
