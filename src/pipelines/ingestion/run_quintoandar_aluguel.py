"""Orquestra o conector quintoandar_aluguel: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_quintoandar_aluguel
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone

from infrastructure.connectors.quintoandar_aluguel.connector import (
    QuintoandarAluguelConnector,
)
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.contexto_quintoandar_repository import (
    inserir_indicadores_aluguel,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    connector = QuintoandarAluguelConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando Índice QuintoAndar/Imovelweb de aluguel...")
        snapshot = connector.fetch()
        lidos = sum(1 for _ in csv.DictReader(snapshot.conteudo.splitlines()))
        logger.info("recebidas %d linhas no CSV (snapshot: %s)", lidos, snapshot.snapshot_ref)

        indicadores = connector.normalize(snapshot)
        logger.info("%d leituras de Curitiba normalizadas", len(indicadores))

        with get_session() as session:
            gravados = inserir_indicadores_aluguel(session, indicadores)
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

        logger.info("gravadas %d leituras de aluguel (Curitiba) no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector quintoandar_aluguel")
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
