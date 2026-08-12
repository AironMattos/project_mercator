"""Orquestra o conector alvaras_smf: fetch -> normalize -> grava no banco.

Lê e grava em lotes (streaming) porque o arquivo de origem tem centenas de
MB e não deve ser carregado inteiro em memória.

Uso:
    python -m pipelines.ingestion.run_alvaras_smf
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

from infrastructure.connectors.alvaras_smf import AlvarasSmfConnector, RegistroNormalizado
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.entidade_repository import upsert_entidades
from infrastructure.database.repositories.observacao_repository import insert_observacoes
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 5000


def _territorio_id_por_slug() -> dict[str, str]:
    with get_session() as session:
        territorios = list_territorios(session, nivel="bairro")
    return {slugify(t.nome): t.territorio_id for t in territorios}


def _gravar_lote(lote: list[RegistroNormalizado]) -> tuple[int, int]:
    with get_session() as session:
        mapa = upsert_entidades(session, [r.entidade for r in lote])

        observacoes = []
        for r in lote:
            entidade_id_real = mapa[
                (r.entidade.tipo_entidade, r.entidade.identificador_fonte)
            ]
            observacao = r.observacao
            if entidade_id_real != observacao.entidade_id:
                observacao = replace(observacao, entidade_id=entidade_id_real)
            observacoes.append(observacao)

        gravados = insert_observacoes(session, observacoes)
    return len(lote), gravados


def main() -> None:
    connector = AlvarasSmfConnector()
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    territorio_lookup = _territorio_id_por_slug()
    logger.info(
        "%d territórios (bairro) carregados para resolução de BAIRRO",
        len(territorio_lookup),
    )

    try:
        snapshot = connector.fetch()

        lote: list[RegistroNormalizado] = []
        for registro in connector.normalize(snapshot, territorio_lookup):
            lote.append(registro)
            if len(lote) >= TAMANHO_LOTE:
                l, g = _gravar_lote(lote)
                lidos += l
                gravados += g
                logger.info("progresso: %d lidos, %d gravados", lidos, gravados)
                lote = []
        if lote:
            l, g = _gravar_lote(lote)
            lidos += l
            gravados += g

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
        logger.info("concluído: %d lidos, %d gravados", lidos, gravados)
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector alvaras_smf")
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
