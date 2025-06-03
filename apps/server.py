"""
FastAPI Application Module

This module sets up a FastAPI application with middleware for CORS, request logging,
rate limiting, and authentication. It also includes custom exception handling.

Functions:
- init_routers: Includes authentication and client routers.
- init_listeners: Sets up custom exception handlers.
- make_middleware: Returns a list of middleware.
- create_app: Configures and creates the FastAPI application instance.
"""

import logging
import asyncio
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from apps.v1.cron.driver_expiry_check import setup_driver_expiry_cron

from apps.v1.api.auth.view import authrouter
from apps.v1.api.driver.view import driverrouter
from config import project_path
from core.utils import constant_variable
from middleware import S3PathMiddleware
from middleware.authentication_middleware import AuthenticateMiddleware


def init_routers(app_: FastAPI) -> None:
    """
    Initialize and include routers for the FastAPI application.

    Args:
        app_ (FastAPI): The FastAPI application instance to which the routers will be added.
    """
    app_.include_router(
        authrouter, prefix=f"{constant_variable.API_V1}/auth", tags=["Authentication"]
    )
    app_.include_router(
        driverrouter, prefix=f"{constant_variable.API_V1}/driver", tags=["Driver"]
    )


def make_middleware() -> list[Middleware]:
    """
    Create and return a list of middleware to be used in the FastAPI application.

    Returns:
        list[Middleware]: A list of middleware instances to be added to the FastAPI application.
    """
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=constant_variable.STATUS_TRUE,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(
            S3PathMiddleware, config_path=f"{project_path.S3_ROOT}/s3_paths_config.json"
        ),
        Middleware(AuthenticateMiddleware)
    ]
    return middleware


# TODO: Redis Cache Implement


def create_app() -> FastAPI:
    """
    Create and configure a new FastAPI application instance.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """
    app_ = FastAPI(
        title="Kuber Cab",
        description="FastAPI",
        version="1.0.0",
        # docs_url=None if config.ENV == "production" else "/docs",
        # redoc_url=None if config.ENV == "production" else "/redoc",
        middleware=make_middleware(),
    )
    init_routers(app_=app_)
    return app_


app = create_app()
# Setup the driver expiry cron job
asyncio.run(setup_driver_expiry_cron())
logger = logging.getLogger(__name__)
