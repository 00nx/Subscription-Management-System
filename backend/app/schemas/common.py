from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


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
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page, self.page_size = page, page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
