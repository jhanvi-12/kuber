"""
This module defines middleware for authenticating users via session IDs provided
in the Authorization header.

Middleware:
    AuthenticateMiddleware: Middleware to validate and authenticate session 
    IDs for each incoming request.

Functions:
    authenticate_user(session_id, db_session): Validates the session ID 
    and returns the associated user ID.
"""

from datetime import datetime

from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from apps.v1.api.auth.models.model import Session
from config.db_config import get_db

oauth2_scheme = HTTPBearer()


class AuthenticateMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authenticating requests using session IDs.

    This middleware checks the `Authorization` header for a session ID,
    validates it against the database, and attaches the associated user ID
    to the request state for downstream usage.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Processes each incoming request to validate the session ID.

        Args:
            request (Request): The incoming HTTP request.
            call_next (Callable): The next middleware or route handler.

        Returns:
            Response: The HTTP response after authentication.

        Raises:
            JSONResponse: If the `Authorization` header is missing or the session ID is invalid.
        """
        # Exclude speicified paths like /docs, /redoc from authentication.
        excluded_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/v1/auth/create/admin",
            "/v1/auth/login",
        ]
        if request.url.path in excluded_paths:
            return await call_next(request)

        # Extract the session_id from the Authorization header
        session_id = request.headers.get("Authorization")
        if not session_id:
            return JSONResponse(
                {"detail": "Authorization header missing"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Authenticate the user
        try:
            async for db_session in get_db():
                user_id = await authenticate(session_id, db_session)
                request.state.user_id = user_id
        except Exception as exc:
            return JSONResponse(
                {"detail": str(exc)},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Proceed with the next middleware or route handler
        response = await call_next(request)
        return response


# async def authenticate_user(session_id: str, db: AsyncSession) -> int:
#     """
#     Authenticate a user based on the session_id.

#     Args:
#         session_id (str): The session ID from the request header.
#         db (AsyncSession): The database session.

#     Returns:
#         int: The authenticated user ID.

#     Raises:
#         HTTPException: If the session is invalid or expired.
#     """
#     result = await db.execute(
#         select(Session)
#         .options(selectinload(Session.user))
#         .filter_by(session_id=session_id)
#     )
#     session = result.scalars().first()

#     if not session or (session.expires_at.date() <= datetime.utcnow().date()):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired session",
#         )

#     if session.user:
#         return session.user.id
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
#         )


async def authenticate(
    authorize: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(getdb),
):

    # TODO: Modify middleware as per requirement
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message_variable.INVALID_AUTH_TOKEN,
    )

    token_required_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message_variable.TOKEN_REQUIRED,
    )
    # try:

    token_data = JWTOAuth2().verify_access_token(
        authorize.credentials
    )  # This will raise an exception if the token is missing or invalid
    sub = token_data.get("sub")
    user_id = sub["id"]
    return user_id
