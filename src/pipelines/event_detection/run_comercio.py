"""Detecta eventos comparando dois snapshots de alvaras_smf já ingeridos.

Lê as observações em cursor server-side, agrupadas por entidade - nunca
carrega os ~500 mil registros de cada snapshot inteiros em memória.

Uso:
    python -m pipelines.event_detection.run_comercio 2026-07-01 2026-08-01
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from datetime import date, datetime, timezone

from domain.event import Evento, detectar_desaparecimento, detectar_eventos_par
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.evento_repository import insert_eventos
from infrastructure.database.repositories.observacao_repository import (
    iter_grupos_por_entidade,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FONTE_ID = "alvaras_smf"
ENTITY_TYPE = "comercio"
TAMANHO_LOTE = 5000


def _gravar_lote(lote: list[Evento]) -> int:
    with get_session() as session:
        return insert_eventos(session, lote)


def _detectar_eventos_da_entidade(
    observacoes: list, data_anterior: date, data_atual: date
) -> list[Evento]:
    obs_anterior = next((o for o in observacoes if o.observado_em == data_anterior), None)
    obs_atual = next((o for o in observacoes if o.observado_em == data_atual), None)

    if obs_atual is not None:
        return detectar_eventos_par(obs_anterior, obs_atual, ENTITY_TYPE)
    return [detectar_desaparecimento(obs_anterior, ENTITY_TYPE, data_atual)]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "uso: python -m pipelines.event_detection.run_comercio "
            "AAAA-MM-DD(anterior) AAAA-MM-DD(atual)"
        )
    data_anterior = date.fromisoformat(sys.argv[1])
    data_atual = date.fromisoformat(sys.argv[2])

    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    contagem: Counter[str] = Counter()
    lote: list[Evento] = []
    total_entidades = 0
    total_eventos = 0

    try:
        with get_session() as session:
            for _entidade_id, observacoes in iter_grupos_por_entidade(
                session, FONTE_ID, data_anterior, data_atual
            ):
                total_entidades += 1
                eventos = _detectar_eventos_da_entidade(
                    observacoes, data_anterior, data_atual
                )
                for evento in eventos:
                    contagem[evento.event_type] += 1
                lote.extend(eventos)

                if len(lote) >= TAMANHO_LOTE:
                    total_eventos += _gravar_lote(lote)
                    lote = []
        if lote:
            total_eventos += _gravar_lote(lote)

        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id="event_detection_comercio",
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=total_entidades,
                    registros_gravados=total_eventos,
                    registros_com_falha=0,
                )
            )

        logger.info("entidades processadas: %d", total_entidades)
        logger.info("eventos gravados: %d", total_eventos)
        for tipo, n in contagem.most_common():
            logger.info("  %s: %d", tipo, n)
    except Exception:
        status = "falha"
        logger.exception("falha na detecção de evento")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id="event_detection_comercio",
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=total_entidades,
                    registros_gravados=total_eventos,
                    registros_com_falha=0,
                )
            )
        raise


if __name__ == "__main__":
    main()
