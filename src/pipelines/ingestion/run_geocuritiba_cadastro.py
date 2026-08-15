"""Orquestra os conectores geocuritiba_cadastro (Lote Cadastral +
Zoneamento Lei 15.511/2019): fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_geocuritiba_cadastro
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.geocuritiba_cadastro import (
    LoteCadastralConnector,
    ZoneamentoConnector,
)
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.lote_cadastral_repository import upsert_lotes
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.repositories.zoneamento_repository import inserir_zoneamentos
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _territorio_id_por_slug() -> dict[str, str]:
    with get_session() as session:
        territorios = list_territorios(session, nivel="bairro")
    return {slugify(t.nome): t.territorio_id for t in territorios}


def _rodar_lote_cadastral(territorio_lookup: dict[str, str]) -> None:
    connector = LoteCadastralConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando Lote Cadastral do GeoCuritiba (~308 mil lotes)...")
        snapshot = connector.fetch()
        lidos = snapshot.conteudo["total"]
        logger.info("recebidos %d lotes (snapshot: %s)", lidos, snapshot.snapshot_ref)

        registros = connector.normalize(snapshot, territorio_id_por_slug=territorio_lookup)
        with get_session() as session:
            gravados = upsert_lotes(session, registros)

        falhas = lidos - gravados
        logger.info("gravados %d lotes no banco", gravados)
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector geocuritiba_lote_cadastral")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
        raise


def _rodar_zoneamento() -> None:
    connector = ZoneamentoConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando Zoneamento Lei 15.511/2019 do GeoCuritiba...")
        snapshot = connector.fetch()
        lidos = len(snapshot.conteudo)
        logger.info("recebidas %d feições (snapshot: %s)", lidos, snapshot.snapshot_ref)

        registros = connector.normalize(snapshot)
        falhas = lidos - len(registros)

        with get_session() as session:
            gravados = inserir_zoneamentos(session, registros)
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
        logger.info("gravados %d zoneamentos no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector geocuritiba_zoneamento")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
        raise


def main() -> None:
    territorio_lookup = _territorio_id_por_slug()
    _rodar_lote_cadastral(territorio_lookup)
    _rodar_zoneamento()


if __name__ == "__main__":
    main()
