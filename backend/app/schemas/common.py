from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

# Money in requests: Decimal, non-negative, at most 2 places (serialised as strings, e.g. "999.00")
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Request successful"
    data: T | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    errors: dict = {}


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), sort: str | None = Query(None, max_length=50)):
        self.page, self.page_size, self.sort = page, page_size, sort

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
