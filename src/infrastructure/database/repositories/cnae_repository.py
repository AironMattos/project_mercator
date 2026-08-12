from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from commerce.cnae import Cnae
from infrastructure.database.orm.dim_cnae import DimCnae


def upsert_cnaes(session: Session, cnaes: list[Cnae]) -> int:
    """Grava a tabela de referência de CNAE. Idempotente - reprocessar a
    mesma fonte não deve falhar nem duplicar.
    """
    if not cnaes:
        return 0

    rows = [
        {
            "codigo_cnae": c.codigo_cnae,
            "descricao": c.descricao,
            "secao": c.secao,
            "divisao": c.divisao,
            "grupo": c.grupo,
            "classe": c.classe,
            "subclasse": c.subclasse,
        }
        for c in cnaes
    ]

    stmt = insert(DimCnae).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DimCnae.codigo_cnae],
        set_={
            "descricao": stmt.excluded.descricao,
            "secao": stmt.excluded.secao,
            "divisao": stmt.excluded.divisao,
            "grupo": stmt.excluded.grupo,
            "classe": stmt.excluded.classe,
            "subclasse": stmt.excluded.subclasse,
        },
    )
    session.execute(stmt)
    return len(rows)
