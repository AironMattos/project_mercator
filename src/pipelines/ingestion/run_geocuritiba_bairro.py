"""Orquestra o conector geocuritiba_bairro: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_geocuritiba_bairro
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.geocuritiba_bairro import GeoCuritibaBairroConnector
from infrastructure.database.repositories.territorio_repository import (
    upsert_territorios,
)
from infrastructure.database.session import get_session
from infrastructure.database.orm.pipeline_run import PipelineRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    connector = GeoCuritibaBairroConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando camada Bairro do GeoCuritiba...")
        snapshot = connector.fetch()
        lidos = len(snapshot.conteudo)
        logger.info("recebidas %d features (snapshot: %s)", lidos, snapshot.snapshot_ref)

        territorios = connector.normalize(snapshot)
        falhas = lidos - len(territorios)

        with get_session() as session:
            gravados = upsert_territorios(session, territorios)
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

        logger.info("gravados %d territórios (bairro) no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector geocuritiba_bairro")
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


if __name__ == "__main__":
    main()
