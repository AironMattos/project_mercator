"""Resolução entre fontes do Radar de Anúncios (seção 8.1 do prompt de
referência, docs/prompt-referencia-radar-anuncios.md): agrupa entidades de
anúncio (de uma ou mais fontes) em `canonical.imovel_resolvido` por
`impressao_digital` coincidente dentro de uma janela de tempo - o mesmo
imóvel físico anunciado nas duas fontes ao mesmo tempo não pode contar
duas vezes em estoque/novos anúncios.

A lógica de agrupamento (domain.anuncio.resolucao.resolver_imoveis) é pura
e já tinha testes desde o checkpoint 12c - o que faltava era este pipeline,
que lê os candidatos pendentes do banco e grava os clusters. Roda depois
de qualquer ingestão nova (mesmo espírito operacional de
run_contagem_eventos.py: precisa ser rodado de novo manualmente por
enquanto, não é automático).

Idempotente por construção: candidatos já atribuídos a um cluster nunca
reaparecem em listar_candidatos_resolucao_pendentes (LEFT JOIN ... IS
NULL), e uma entidade nunca migra de cluster depois de gravada (ON
CONFLICT DO NOTHING na PK de imovel_resolvido_membro).

Uso:
    python -m pipelines.resolucao.run_imovel_resolvido
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from domain.anuncio.resolucao import resolver_imoveis
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.imovel_resolvido_repository import (
    gravar_clusters,
    listar_candidatos_resolucao_pendentes,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONECTOR_ID = "resolucao_imovel_anuncio"


def main() -> None:
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    total_candidatos = total_clusters = total_multi_fonte = 0

    try:
        with get_session() as session:
            candidatos = listar_candidatos_resolucao_pendentes(session)
            total_candidatos = len(candidatos)
            logger.info("%d candidatos pendentes de resolução", total_candidatos)

            clusters = resolver_imoveis(candidatos)
            total_clusters = len(clusters)
            total_multi_fonte = sum(1 for c in clusters if c.multiplas_fontes)

            gravar_clusters(session, clusters)

        logger.info(
            "%d clusters gravados (%d com mais de uma fonte)",
            total_clusters,
            total_multi_fonte,
        )
    except Exception:
        status = "falha"
        logger.exception("falha na resolução de imóveis entre fontes")
        raise
    finally:
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=CONECTOR_ID,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=total_candidatos,
                    registros_gravados=total_clusters,
                    registros_com_falha=0,
                )
            )


if __name__ == "__main__":
    main()
