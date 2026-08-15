"""Detecta eventos de obra (ALVARA_APROVADO/OBRA_CONCLUIDA) lendo as
observações já ingeridas de volta do banco - mesmo padrão de separação
de event_detection/run_comercio.py (nunca deriva evento de um objeto de
domínio recém-criado em memória, só do que está de fato persistido).

Uso:
    python -m pipelines.event_detection.run_obra
"""
from __future__ import annotations

import logging

from domain.event import Evento, detectar_evento_obra
from infrastructure.database.repositories.evento_repository import insert_eventos
from infrastructure.database.repositories.observacao_repository import (
    iter_observacoes_por_fonte,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 5000
# (fonte_id, event_type) - a mesma correspondência que o pipeline de
# ingestão usa para nomear o conector.
FONTES_E_EVENTOS = (
    ("smu_alvara_construcao", "ALVARA_APROVADO"),
    ("smu_cvco", "OBRA_CONCLUIDA"),
)


def _gravar_lote(lote: list[Evento]) -> int:
    with get_session() as session:
        return insert_eventos(session, lote)


def main() -> None:
    for fonte_id, event_type in FONTES_E_EVENTOS:
        lidas = gravados = sem_data = 0
        lote: list[Evento] = []

        with get_session() as session:
            observacoes = list(iter_observacoes_por_fonte(session, fonte_id))

        for observacao in observacoes:
            lidas += 1
            evento = detectar_evento_obra(observacao, event_type)
            if evento is None:
                sem_data += 1
                continue
            lote.append(evento)
            if len(lote) >= TAMANHO_LOTE:
                gravados += _gravar_lote(lote)
                lote = []
        if lote:
            gravados += _gravar_lote(lote)

        logger.info(
            "%s -> %s: %d observações lidas, %d eventos gravados, %d sem data relevante",
            fonte_id,
            event_type,
            lidas,
            gravados,
            sem_data,
        )


if __name__ == "__main__":
    main()
