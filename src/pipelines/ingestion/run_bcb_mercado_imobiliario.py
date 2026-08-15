"""Orquestra o conector bcb_mercado_imobiliario: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_bcb_mercado_imobiliario
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.bcb_mercado_imobiliario.connector import (
    BcbMercadoImobiliarioConnector,
)
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.contexto_bcb_repository import (
    inserir_indicadores_bcb,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    connector = BcbMercadoImobiliarioConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando MercadoImobiliario (BCB, uf=PR)...")
        snapshot = connector.fetch()
        lidos = len(snapshot.conteudo["leituras"])
        logger.info("recebidas %d leituras (snapshot: %s)", lidos, snapshot.snapshot_ref)

        indicadores = connector.normalize(snapshot)
        falhas = lidos - len(indicadores)

        with get_session() as session:
            gravados = inserir_indicadores_bcb(session, indicadores)
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

        logger.info("gravadas %d leituras de contexto imobiliário (PR) no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector bcb_mercado_imobiliario")
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
