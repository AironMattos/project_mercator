from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.entity import Entidade
from infrastructure.database.orm.entidade import Entidade as EntidadeORM


def upsert_entidades(
    session: Session, entidades: list[Entidade]
) -> dict[tuple[str, str], uuid.UUID]:
    """Resolve o entidade_id de cada entidade pela chave de negócio
    (tipo_entidade, identificador_fonte), criando quando ainda não existe.

    Se a entidade já existia, o id retornado é o já existente - o
    entidade_id candidato gerado no domínio só "vence" quando é de fato uma
    entidade nova.
    """
    if not entidades:
        return {}

    # dedup por chave de negócio dentro do lote: um único INSERT com
    # ON CONFLICT não pode atualizar a mesma linha duas vezes.
    por_chave: dict[tuple[str, str], Entidade] = {}
    for e in entidades:
        por_chave[(e.tipo_entidade, e.identificador_fonte)] = e

    rows = [
        {
            "entidade_id": e.entidade_id,
            "tipo_entidade": e.tipo_entidade,
            "identificador_fonte": e.identificador_fonte,
        }
        for e in por_chave.values()
    ]

    stmt = insert(EntidadeORM).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tipo_entidade", "identificador_fonte"],
        set_={"atualizado_em": func.now()},
    ).returning(
        EntidadeORM.tipo_entidade,
        EntidadeORM.identificador_fonte,
        EntidadeORM.entidade_id,
    )

    resultado = session.execute(stmt)
    return {
        (row.tipo_entidade, row.identificador_fonte): row.entidade_id
        for row in resultado
    }
