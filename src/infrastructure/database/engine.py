from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine


def _load_database_url() -> str:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Copie .env.example para .env e ajuste, "
            "ou exporte a variável de ambiente diretamente."
        )
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(_load_database_url(), future=True)
