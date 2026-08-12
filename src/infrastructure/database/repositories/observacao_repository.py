from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.observation import ObservacaoEntidade
from infrastructure.database.orm.observacao_entidade import (
    ObservacaoEntidade as ObservacaoEntidadeORM,
)


def insert_observacoes(session: Session, observacoes: list[ObservacaoEntidade]) -> int:
    """Grava observações. Nunca atualiza uma observação existente - se o
    mesmo snapshot (entidade + fonte + observado_em) já foi gravado antes,
    o registro repetido é ignorado (idempotência de reprocessamento), não
    sobrescrito.
    """
    if not observacoes:
        return 0

    rows = [
        {
            "observacao_id": o.observacao_id,
            "entidade_id": o.entidade_id,
            "observado_em": o.observado_em,
            "atributos": o.atributos,
            "fonte_id": o.fonte_id,
            "snapshot_ref": o.snapshot_ref,
        }
        for o in observacoes
    ]

    stmt = insert(ObservacaoEntidadeORM).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["entidade_id", "fonte_id", "observado_em"]
    )
    resultado = session.execute(stmt)
    return resultado.rowcount or 0
