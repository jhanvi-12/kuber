# """Middleware for request rate limiting across APIs."""

# import json
# import time

# from fastapi import status
# from fastapi_limiter.depends import RateLimiter
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.requests import Request
# from starlette.responses import JSONResponse, Response

# from config.ratelimiter_config import (
#     LOGIN_BLOCK_SECONDS,
#     LOGIN_MAX_ATTEMPTS_PER_DAY,
#     RATE_LIMITER_SECONDS,
#     RATE_LIMITER_TIME,
#     UNAUTH_RATE_LIMIT_SECONDS,
#     UNAUTH_RATE_LIMIT_TIMES,
# )
# from config.redis_config import redis_client
# from core.utils.token_authentication import JWTOAuth2


# class RateLimitingMiddleware(BaseHTTPMiddleware):
#     """Class for rate limiting middleware."""

#     async def dispatch(self, request: Request, call_next):
#         excluded_paths = ["/docs", "/openapi.json", "/redoc"]
#         if request.url.path in excluded_paths:
#             return await call_next(request)

#         # Login-specific daily limiter:
#         # count every login attempt (success/failure) for 24 hours.
#         if request.url.path == "/v1/auth/login":
#             body = await request.body()
#             self._reset_request_body(request, body)

#             try:
#                 payload = json.loads(body.decode("utf-8")) if body else {}
#             except Exception:
#                 payload = {}

#             login_id = str(payload.get("email") or "").strip().lower()
#             user_type = str(payload.get("user_type") or "").strip().lower()
#             today = time.strftime("%Y-%m-%d")
#             login_key = f"login_attempts:{user_type}:{login_id}:{today}"

#             attempts = await redis_client.get(login_key)
#             attempts = int(attempts) if attempts else 0
#             if attempts >= LOGIN_MAX_ATTEMPTS_PER_DAY:
#                 return self._cors_response(
#                     request,
#                     JSONResponse(
#                         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                         content={
#                             "status": "fail",
#                             "data": None,
#                             "message": "Too many login attempts. Try again after 24 hours.",
#                         },
#                     ),
#                 )

#             await redis_client.incr(login_key)
#             await redis_client.expire(login_key, LOGIN_BLOCK_SECONDS)

#         auth_header = request.headers.get("Authorization")
#         if auth_header and auth_header.startswith("Bearer "):
#             token = auth_header.split(" ")[1]
#             try:
#                 user_data = JWTOAuth2().verify_access_token(token)
#                 user_id = user_data.get("user_id")
#             except Exception:
#                 user_id = "anonymous"
#             request.state.view_rate_limit_key = f"user:{user_id}"
#             limiter = RateLimiter(
#                 times=RATE_LIMITER_TIME,
#                 seconds=RATE_LIMITER_SECONDS,
#                 identifier=self._request_identifier,
#             )
#         else:
#             limiter = RateLimiter(
#                 times=UNAUTH_RATE_LIMIT_TIMES,
#                 seconds=UNAUTH_RATE_LIMIT_SECONDS,
#             )

#         dummy_response = Response()
#         try:
#             await limiter(request, dummy_response)
#         except Exception:
#             return self._cors_response(
#                 request,
#                 JSONResponse(
#                     status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#                     content={
#                         "status": "fail",
#                         "data": None,
#                         "message": "Too many request send!",
#                     },
#                 ),
#             )

#         response = await call_next(request)
#         return response

#     @staticmethod
#     async def _request_identifier(request: Request):
#         return getattr(request.state, "view_rate_limit_key", "anonymous")

#     @staticmethod
#     def _reset_request_body(request: Request, body: bytes):
#         """Restore consumed request body for downstream handlers."""

#         async def receive():
#             return {"type": "http.request", "body": body, "more_body": False}

#         request._receive = receive

#     @staticmethod
#     def _cors_response(request: Request, response: Response):
#         response.headers["Access-Control-Allow-Origin"] = request.headers.get(
#             "Origin", "*"
#         )
#         response.headers["Access-Control-Allow-Credentials"] = "true"
#         response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
#         response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
#         return response
