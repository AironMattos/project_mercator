"""Orquestra o conector ibge_censo_setor: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_ibge_censo_setor
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.ibge_censo_setor.connector import IbgeCensoSetorConnector
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.contexto_censo_repository import (
    upsert_setores_censitarios,
)
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _territorio_id_por_slug() -> dict[str, str]:
    with get_session() as session:
        territorios = list_territorios(session, nivel="bairro")
    return {slugify(t.nome): t.territorio_id for t in territorios}


def main() -> None:
    connector = IbgeCensoSetorConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando agregados por setor censitário (Censo 2022, IBGE)...")
        snapshot = connector.fetch()
        logger.info("arquivo pronto: %s", snapshot.snapshot_ref)

        territorio_lookup = _territorio_id_por_slug()
        setores = connector.normalize(snapshot, territorio_id_por_slug=territorio_lookup)
        lidos = len(setores)
        resolvidos = sum(1 for s in setores if s.territorio_id)
        logger.info(
            "%d setores de Curitiba normalizados, %d com bairro resolvido (%.1f%%)",
            lidos,
            resolvidos,
            100 * resolvidos / lidos if lidos else 0,
        )

        with get_session() as session:
            gravados = upsert_setores_censitarios(session, setores)
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

        logger.info("gravados %d setores censitários no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector ibge_censo_setor")
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
