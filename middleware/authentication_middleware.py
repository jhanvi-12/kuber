"""
This module defines middleware for authenticating users via JWT token  provided
in the Authorization header.

Middleware:
    AuthenticateMiddleware: Middleware to validate and authenticate token 
    for each incoming request.

Functions:
    authenticate(token_data): Validates the token 
    and returns the associated user data.
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from apps.v1.api.pagination_service import oauth2
from core.utils.token_authentication import JWTOAuth2


class AuthenticateMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authenticating requests using token data.

    This middleware checks the `Authorization` header for a token,
    validates it against the database, and attaches the associated user ID
    to the request state for downstream usage.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Processes each incoming request to validate the token.

        Args:
            request (Request): The incoming HTTP request.
            call_next (Callable): The next middleware or route handler.

        Returns:
            Response: The HTTP response after authentication.

        Raises:
            JSONResponse: If the `Authorization` header is missing or the token is invalid.
        """
        # Exclude speicified paths like /docs, /redoc from authentication.
        excluded_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/v1/auth/register",
            "/v1/auth/login",
            "/v1/auth/admin/login",
            "/v1/auth/clear_session",
            "/v1/auth/otp_request",
            "/v1/auth/otp_verify",
            "/v1/auth/forgot_password",
            "/v1/auth/reset_password",
            "/v1/driver/check/plan_expiry",
            "/v1/user/ride",
            "/v1/user/ride/update_status",
            "/v1/user/ride/track_driver"
            
        ]
        if request.url.path in excluded_paths:
            return await call_next(request)

        # Extract the session_id from the Authorization header
        jwt_token = request.headers.get("Authorization")
        if not jwt_token:
            return JSONResponse(
                {"detail": "Authorization header missing"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Authenticate the user
        try:
            user_data = await authenticate(jwt_token)
            request.state.user_data = user_data
        except Exception as exc:
            return JSONResponse(
                {"detail": str(exc)},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Proceed with the next middleware or route handler
        response = await call_next(request)
        return response



async def authenticate(
    authorize: HTTPAuthorizationCredentials = Depends(oauth2)
):
    """This method is used to authenticate the user using JWT token."""
    token_data = JWTOAuth2().verify_access_token(
        authorize.split(" ")[1]
    )  # This will raise an exception if the token is missing or invalid
    return token_data

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit the maximum size of the request body.

    This middleware checks the `Content-Length` header of incoming requests and
    returns a 413 Payload Too Large response if the body exceeds the specified limit.
    """
    def __init__(self, app, max_body_size: int):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        """Checks the Content-Length header and limits the request body size."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "File too large. Maximum allowed size is 10MB."},
            )
        return await call_next(request)
