"""Orquestra o conector ippuc_pgv: fetch -> normalize -> grava no banco.

Uso:
    python -m pipelines.ingestion.run_ippuc_pgv
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from infrastructure.connectors.ippuc_pgv.connector import IppucPgvConnector
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.repositories.valor_referencia_repository import (
    inserir_valores_referencia,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _territorio_id_por_slug() -> dict[str, str]:
    with get_session() as session:
        territorios = list_territorios(session, nivel="bairro")
    return {slugify(t.nome): t.territorio_id for t in territorios}


def main() -> None:
    connector = IppucPgvConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando Planta Genérica de Valores (IPPUC)...")
        snapshot = connector.fetch()
        lidos = len(snapshot.conteudo["features"])
        logger.info("recebidas %d features (snapshot: %s)", lidos, snapshot.snapshot_ref)

        territorio_lookup = _territorio_id_por_slug()
        valores = connector.normalize(snapshot, territorio_id_por_slug=territorio_lookup)
        falhas = lidos - len(valores)
        resolvidos = sum(1 for v in valores if v.territorio_id)
        logger.info(
            "%d valores normalizados, %d com território resolvido (%.1f%%)",
            len(valores),
            resolvidos,
            100 * resolvidos / len(valores) if valores else 0,
        )

        with get_session() as session:
            gravados = inserir_valores_referencia(session, valores)
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

        logger.info("gravados %d valores de referência (venal/terreno) no banco", gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector ippuc_pgv")
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
