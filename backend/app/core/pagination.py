from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.schemas.common import Page, PageParams


def paginate(db: Session, stmt, params: PageParams, schema, sorts: dict | None = None, default_sort: str | None = None) -> Page:
    """Count + page + optional whitelisted sort (`?sort=field` or `?sort=-field`). Unknown sort keys are ignored."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    key = params.sort or default_sort
    if sorts and key:
        col = sorts.get(key.lstrip("-"))
        if col is not None:
            stmt = stmt.order_by(col.asc() if key.startswith("-") else col.desc())
    rows = db.scalars(stmt.offset(params.page).limit(params.page_size)).unique().all()
    return Page(items=[schema.model_validate(r) for r in rows], total=total, page=params.page, page_size=params.page_size)
