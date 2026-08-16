"""Detecta eventos de anúncio (ANUNCIO_PUBLICADO, PRECO_ALTERADO,
ANUNCIO_ENCERRADO) comparando dois snapshots já ingeridos de uma fonte de
anúncio (apolar_anuncios ou chavesnamao_anuncios).

REANUNCIO não é detectado aqui - depende de cruzar um anúncio novo contra
o histórico recente de ANUNCIO_ENCERRADO por impressao_digital (seção 8.1
do prompt de referência do Radar de Anúncios), uma consulta própria que
ainda não tem repositório dedicado. Reservado pro checkpoint 12e, mesmo
padrão de FECHAMENTO_CONFIRMADO (Radar de Comércio) e
TRANSACAO/LANCAMENTO (Radar Imobiliário): o tipo de evento já é válido no
catálogo (domain/event/models.py), só não tem regra que o emita ainda.

Uso:
    python -m pipelines.event_detection.run_anuncio chavesnamao_anuncios 2026-08-08 2026-08-15
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from datetime import date, datetime, timezone

from domain.anuncio.regras import detectar_anuncio_encerrado, detectar_eventos_anuncio_par
from domain.event import Evento
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.anuncio_repository import (
    iter_grupos_por_entidade_anuncio,
)
from infrastructure.database.repositories.evento_repository import insert_eventos
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 5000


def _gravar_lote(lote: list[Evento]) -> int:
    with get_session() as session:
        return insert_eventos(session, lote)


def _detectar_eventos_do_anuncio(
    observacoes: list,
    data_anterior: date,
    data_atual: date,
) -> list[Evento]:
    obs_anterior = next((o for o in observacoes if o.observado_em == data_anterior), None)
    obs_atual = next((o for o in observacoes if o.observado_em == data_atual), None)

    if obs_atual is not None:
        return detectar_eventos_anuncio_par(obs_anterior, obs_atual)
    return [detectar_anuncio_encerrado(obs_anterior, data_atual)]


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "uso: python -m pipelines.event_detection.run_anuncio "
            "<fonte_id> AAAA-MM-DD(anterior) AAAA-MM-DD(atual)"
        )
    fonte_id = sys.argv[1]
    data_anterior = date.fromisoformat(sys.argv[2])
    data_atual = date.fromisoformat(sys.argv[3])

    conector_id = f"event_detection_anuncio_{fonte_id}"
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    contagem: Counter[str] = Counter()
    lote: list[Evento] = []
    total_entidades = 0
    total_eventos = 0

    try:
        with get_session() as session:
            for _entidade_id, observacoes in iter_grupos_por_entidade_anuncio(
                session, fonte_id, data_anterior, data_atual
            ):
                total_entidades += 1
                eventos = _detectar_eventos_do_anuncio(observacoes, data_anterior, data_atual)
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
                    conector_id=conector_id,
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
        logger.exception("falha na detecção de evento de anúncio")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=conector_id,
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
