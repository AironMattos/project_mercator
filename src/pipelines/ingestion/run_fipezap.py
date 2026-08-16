"""Orquestra o conector fipezap: fetch (resolve o mês mais recente
publicado) -> normalize (extrai KPIs de cidade + bairros representativos
de Curitiba, venda e locação) -> grava no banco.

**Uso estritamente interno** - ver domain.contexto.models,
docstring de IndicadorFipezapCidade/IndicadorFipezapBairro. Nunca ligar
este dado a uma rota de API pública.

Uso:
    python -m pipelines.ingestion.run_fipezap
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from domain.contexto import IndicadorFipezapBairro, IndicadorFipezapCidade
from infrastructure.connectors.fipezap.connector import FipezapConnector
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.contexto_fipezap_repository import (
    inserir_indicadores_bairro,
    inserir_indicadores_cidade,
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
    connector = FipezapConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info("buscando informe FipeZAP mais recente...")
        snapshot = connector.fetch()
        logger.info(
            "informe de %s encontrado (snapshot: %s)",
            snapshot.conteudo.periodo_referencia,
            snapshot.snapshot_ref,
        )

        territorio_lookup = _territorio_id_por_slug()
        indicadores = connector.normalize(snapshot, territorio_id_por_slug=territorio_lookup)
        lidos = len(indicadores)

        indicadores_cidade = [i for i in indicadores if isinstance(i, IndicadorFipezapCidade)]
        indicadores_bairro = [i for i in indicadores if isinstance(i, IndicadorFipezapBairro)]
        logger.info(
            "%d indicadores de cidade, %d de bairro extraídos",
            len(indicadores_cidade),
            len(indicadores_bairro),
        )

        with get_session() as session:
            gravados = inserir_indicadores_cidade(session, indicadores_cidade)
            gravados += inserir_indicadores_bairro(session, indicadores_bairro)
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

        resolvidos = sum(1 for i in indicadores_bairro if i.territorio_id is not None)
        logger.info(
            "gravados %d registros (%d/%d bairros com território resolvido)",
            gravados,
            resolvidos,
            len(indicadores_bairro),
        )
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector fipezap")
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
