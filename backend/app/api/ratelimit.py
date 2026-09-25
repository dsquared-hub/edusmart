"""Ограничение частоты запросов к API с одного IP (скользящее окно, 60 с).

Три группы: вход (защита от перебора кодов), создание объяснений (платные
запросы к Gemini) и всё остальное. Хранится в памяти процесса — этого
достаточно для одного экземпляра API; при нескольких нужен Redis.

IP берётся из request.client: за обратным прокси uvicorn запускается с
--proxy-headers, и туда попадает настоящий адрес из X-Forwarded-For.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WINDOW = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, auth: int, explain: int, api: int):
        super().__init__(app)
        self.limits = {"auth": auth, "explain": explain, "api": api}
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._last_cleanup = time.monotonic()

    @staticmethod
    def _group(request: Request) -> str | None:
        path = request.url.path
        if not path.startswith("/api/") or path == "/api/health":
            return None
        if path == "/api/auth/bot/poll":
            # Сайт опрашивает статус раз в пару секунд; токен угадать нельзя (192 бита)
            return "api"
        # Вход (в т.ч. SMS-коды и приглашения в семью) — строгий лимит против перебора
        if path.startswith(("/api/auth/", "/api/v1/auth/", "/api/v1/family/join")):
            return "auth"
        if request.method == "POST" and path.startswith("/api/explain"):
            return "explain"
        return "api"

    async def dispatch(self, request: Request, call_next):
        group = self._group(request)
        if group is None or self.limits[group] <= 0:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[(group, ip)]
        while hits and hits[0] <= now - WINDOW:
            hits.popleft()
        if len(hits) >= self.limits[group]:
            retry = max(1, int(WINDOW - (now - hits[0])))
            return JSONResponse(
                {"detail": {"code": "rate_limited"}},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)

        if now - self._last_cleanup > WINDOW:  # не копим пустые окна
            self._last_cleanup = now
            for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - WINDOW]:
                del self._hits[key]
        return await call_next(request)
