"""This is the common pagination service implementation."""

from typing import Generic, TypeVar

from fastapi import Query
from fastapi.security import HTTPBearer
from fastapi_pagination.default import Page as BasePage
from fastapi_pagination.default import Params as BaseParams

# Auth object used to authenticate.
oauth2 = HTTPBearer()
T = TypeVar("T")


class Params(BaseParams):
    """This class provides parameters for creating page."""

    page: int = Query(1, ge=0, description="Page number")
    per_page: int = Query(0, ge=0, le=100, description="Page size")


class Page(BasePage[T], Generic[T]):
    """This class provides page of generic."""

    __params_type__ = Params
