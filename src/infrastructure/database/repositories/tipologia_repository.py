from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.database.orm.dim_tipologia_imovel import DimTipologiaImovel


def upsert_tipologias(session: Session, tipologias: dict[str, str]) -> int:
    """Semeia canonical.dim_tipologia_imovel a partir do catálogo estático
    (domain.anuncio.TIPOLOGIAS_VALIDAS + rótulos legíveis) - mesmo padrão
    de categoria_repository.upsert_categorias (Radar de Comércio)."""
    if not tipologias:
        return 0

    rows = [{"tipologia_id": tid, "nome": nome} for tid, nome in tipologias.items()]
    stmt = insert(DimTipologiaImovel).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tipologia_id"], set_={"nome": stmt.excluded.nome}
    )
    resultado = session.execute(stmt)
    return resultado.rowcount or 0
