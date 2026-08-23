"""Middleware for login attempt rate limiting."""

import json

from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse


from config.ratelimiter_config import LOGIN_BLOCK_SECONDS, LOGIN_MAX_ATTEMPTS_PER_DAY
from config.redis_config import redis_client
from core.utils.message_variable import ErrorMessage

LOGIN_PATH = "/v1/auth/login"
EXCLUDED_PATHS = {"/docs", "/openapi.json", "/redoc"}


class RateLimitingMiddleware:
    """ASGI middleware: 5 login attempts per username+user_type, then 24h block."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in EXCLUDED_PATHS or path != LOGIN_PATH:
            await self.app(scope, receive, send)
            return

        body = await self._read_body(receive)
        request = Request(scope, receive)
        blocked_response = await self._check_login_limit(request, body)
        if blocked_response is not None:
            await blocked_response(scope, self._disconnect_receive, send)
            return

        body_sent = False

        async def replay_receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _read_body(receive) -> bytes:
        chunks = []
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            more_body = message.get("more_body", False)
        return b"".join(chunks)

    @staticmethod
    async def _disconnect_receive():
        return {"type": "http.disconnect"}

    @staticmethod
    async def _check_login_limit(request: Request, body: bytes):
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        login_id = str(payload.get("username") or "").strip().lower()
        user_type = str(payload.get("user_type") or "").strip().lower()
        if not login_id:
            return None

        login_key = f"login_attempts:{user_type}:{login_id}"
        attempts = await redis_client.incr(login_key)
        if attempts == 1:
            await redis_client.expire(login_key, LOGIN_BLOCK_SECONDS)
        if attempts <= LOGIN_MAX_ATTEMPTS_PER_DAY:
            return None

        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "status": "fail",
                "data": None,
                "message": ErrorMessage.loginAttemptsExceeded,
            },
        )
        response.headers["Access-Control-Allow-Origin"] = request.headers.get(
            "Origin", "*"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, OPTIONS, PUT, DELETE"
        )
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return response
