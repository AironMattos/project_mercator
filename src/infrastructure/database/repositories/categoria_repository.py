from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from commerce.categories import Categoria
from infrastructure.database.orm.cnae_categoria_map import CnaeCategoriaMap
from infrastructure.database.orm.dim_categoria import DimCategoria


def upsert_categorias(session: Session, categorias: list[Categoria]) -> int:
    if not categorias:
        return 0

    rows = [{"categoria_id": c.categoria_id, "nome": c.nome} for c in categorias]
    stmt = insert(DimCategoria).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DimCategoria.categoria_id],
        set_={"nome": stmt.excluded.nome},
    )
    session.execute(stmt)
    return len(rows)


def upsert_cnae_categoria_map(
    session: Session, mapeamento: dict[str, str]
) -> int:
    """mapeamento: codigo_cnae -> categoria_id."""
    if not mapeamento:
        return 0

    rows = [
        {"codigo_cnae": codigo, "categoria_id": categoria_id}
        for codigo, categoria_id in mapeamento.items()
    ]
    stmt = insert(CnaeCategoriaMap).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["codigo_cnae", "categoria_id"]
    )
    session.execute(stmt)
    return len(rows)


def categoria_id_por_codigo_cnae(session: Session) -> dict[str, str]:
    """Carrega o mapeamento codigo_cnae -> categoria_id do banco, para uso
    em pipelines que precisam resolver a categoria de uma observação.
    """
    stmt = select(CnaeCategoriaMap.codigo_cnae, CnaeCategoriaMap.categoria_id)
    return {row.codigo_cnae: row.categoria_id for row in session.execute(stmt)}
