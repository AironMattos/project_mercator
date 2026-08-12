"""Orquestra o conector ibge_cnae: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_ibge_cnae
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.ibge_cnae import IbgeCnaeConnector
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.cnae_repository import upsert_cnaes
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    connector = IbgeCnaeConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = 0

    try:
        logger.info("buscando tabela de referência de CNAE (IBGE)...")
        snapshot = connector.fetch()
        cnaes = connector.normalize(snapshot)
        lidos = len(cnaes)
        logger.info("recebidas %d subclasses CNAE", lidos)

        with get_session() as session:
            gravados = upsert_cnaes(session, cnaes)
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=0,
                )
            )
        logger.info("gravadas %d subclasses CNAE no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector ibge_cnae")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=0,
                )
            )
        raise


if __name__ == "__main__":
    main()
