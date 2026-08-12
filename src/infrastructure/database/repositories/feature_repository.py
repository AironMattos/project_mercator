from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from analytics.features import ContagemEventos as ContagemEventosDominio
from infrastructure.database.orm.contagem_eventos import (
    ContagemEventos as ContagemEventosORM,
)


def substituir_contagem_eventos(
    session: Session, contagens: list[ContagemEventosDominio]
) -> int:
    """Recalcula a feature do zero: apaga tudo e grava de novo. É seguro
    porque a tabela é 100% derivada de fato_evento_territorial - nada aqui
    é fonte de verdade.
    """
    session.execute(delete(ContagemEventosORM))
    if not contagens:
        return 0

    rows = [
        {
            "territorio_id": c.territorio_id,
            "categoria_id": c.categoria_id,
            "mes": c.mes,
            "event_type": c.event_type,
            "contagem": c.contagem,
        }
        for c in contagens
    ]
    session.execute(ContagemEventosORM.__table__.insert(), rows)
    return len(rows)
