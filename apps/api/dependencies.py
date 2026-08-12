from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from infrastructure.database.session import get_session


def get_db() -> Iterator[Session]:
    with get_session() as session:
        yield session
