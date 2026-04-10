from __future__ import annotations

"""Клиент DeepSeek: ответ 1 аят + 1 хадис; keep-alive HTTP, умеренный max_tokens для скорости."""

import asyncio

import httpx

from app.advisor_prompt import ADVISOR_QURAN_REPLY_PROMPT

_HISTORY_MSG_MAX_CHARS = 2800
_FINAL_USER_MAX_CHARS = 3500

# Ответ короткий; меньший max_tokens ускоряет генерацию и снижает «простыни» от модели.
_MIN_OUTPUT_TOKENS = 1536
_MAX_OUTPUT_TOKENS_CAP = 4096

_REPLY_SUFFIX = (
    "Сейчас нужен ответ строго по шаблону: ровно один аят и один хадис, с переносами строк как в шаблоне; "
    "не несколько хадисов и не несколько аятов. Если нельзя надёжно — только дословная фраза отказа из правил. "
    "Не упоминай оплату в тексте."
)


class DeepSeekClient:
    """Round-robin по ключам, retry при 429. Один AsyncClient на весь процесс (keep-alive)."""

    def __init__(
        self,
        api_keys: list[str],
        base_url: str,
        model: str,
        proxy_url: str = "",
        *,
        answer_max_tokens: int = 2800,
        answer_timeout: float = 120.0,
    ):
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        self.base_url = base_url.rstrip("/")
        self.model = (model or "").strip() or "deepseek-chat"
        self._answer_max_tokens = max(512, int(answer_max_tokens))
        self.answer_timeout = float(answer_timeout)
        self.proxy_url = (proxy_url or "").strip()
        self._lock = asyncio.Lock()
        self._rr_index = 0
        self._http_client: httpx.AsyncClient | None = None
        self._http_lock = asyncio.Lock()

    @property
    def answer_max_tokens(self) -> int:
        return min(self._answer_max_tokens, _MAX_OUTPUT_TOKENS_CAP)

    def _effective_max_tokens(self) -> int:
        return min(
            max(self.answer_max_tokens, _MIN_OUTPUT_TOKENS),
            _MAX_OUTPUT_TOKENS_CAP,
        )

    async def warm_http(self) -> None:
        """Прогрев TCP/TLS до первого вопроса (ускоряет первый запрос)."""
        if self.api_keys:
            await self._ensure_http_client()

    async def _ensure_http_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        async with self._http_lock:
            if self._http_client is not None:
                return self._http_client
            kwargs: dict = {"limits": httpx.Limits(max_keepalive_connections=5, max_connections=10)}
            if self.proxy_url:
                kwargs["proxy"] = self.proxy_url
            self._http_client = httpx.AsyncClient(**kwargs)
            return self._http_client

    async def aclose(self) -> None:
        async with self._http_lock:
            if self._http_client is not None:
                await self._http_client.aclose()
                self._http_client = None

    async def _next_key_round_robin(self) -> str:
        async with self._lock:
            key = self.api_keys[self._rr_index % len(self.api_keys)]
            self._rr_index += 1
            return key

    async def _chat_messages(
        self,
        messages: list[dict],
        temperature: float = 0,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> str | None:
        if not self.api_keys or not messages:
            return None

        use_model = (model or "").strip() or self.model
        payload = {
            "model": use_model,
            "temperature": temperature,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        req_timeout = httpx.Timeout(timeout, connect=10.0)
        try:
            client = await self._ensure_http_client()
            for _ in range(len(self.api_keys)):
                key = await self._next_key_round_robin()
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=req_timeout,
                )
                if response.status_code == 429:
                    continue
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

        return None

    def _build_dialog_messages(
        self,
        system: str,
        dialog_messages: list[dict],
        final_user_content: str,
    ) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in dialog_messages:
            role = m.get("role", "")
            content = str(m.get("content", ""))[:_HISTORY_MSG_MAX_CHARS]
            if role not in ("user", "assistant") or not content.strip():
                continue
            out.append({"role": role, "content": content})
        out.append({"role": "user", "content": final_user_content[:_FINAL_USER_MAX_CHARS]})
        return out

    async def _compose(
        self,
        system: str,
        dialog_messages: list[dict],
        final_suffix: str,
        max_tokens: int,
    ) -> str | None:
        if not self.api_keys:
            return None
        if not dialog_messages or dialog_messages[-1].get("role") != "user":
            return None

        last_content = str(dialog_messages[-1].get("content", ""))[:_HISTORY_MSG_MAX_CHARS]
        history = dialog_messages[:-1]

        memory_hint = ""
        if history:
            memory_hint = (
                "Контекст: в истории чата сообщения по времени (сначала старые). Учитывай нить темы и смысл вопроса.\n\n"
            )

        final_user = f"{memory_hint}{final_suffix}\n\nТекущее сообщение пользователя:\n{last_content}"
        messages = self._build_dialog_messages(system, history, final_user)
        return await self._chat_messages(
            messages,
            temperature=0.1,
            model=self.model,
            max_tokens=max_tokens,
            timeout=self.answer_timeout,
        )

    async def compose_reply(self, dialog_messages: list[dict]) -> str | None:
        """Один формат ответа для всех пользователей (1 аят + 1 хадис)."""
        return await self._compose(
            ADVISOR_QURAN_REPLY_PROMPT,
            dialog_messages,
            _REPLY_SUFFIX,
            self._effective_max_tokens(),
        )
