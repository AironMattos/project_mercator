"""Orquestra o conector apolar_anuncios: fetch (lista de URLs de Curitiba,
via sitemap) -> normalize (rate-limited, uma renderização Playwright por
página de detalhe) -> grava entidade+observação.

Retomável por design (checkpoint 12d, mesmo padrão de
run_chavesnamao_anuncios): cada execução consulta quais identificadores já
têm observação para o `observado_em` do dia e pula essas URLs - rodar de
novo depois de uma execução parcial (ou interrompida) continua de onde
parou, sem re-renderizar nada. Escala real (checkpoint 12a): ~3.552 páginas
de detalhe de Curitiba (940 aluguel + 2.612 venda) - a 3s/req (achado
`connector.INTERVALO_MINIMO_S`), uma coleta completa leva ~3h; `--limite`
existe pra rodar em fatias menores mesmo assim.

Uso:
    python -m pipelines.ingestion.run_apolar_anuncios --limite 200
    python -m pipelines.ingestion.run_apolar_anuncios   # sem limite - roda até esgotar a lista
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from datetime import date, datetime, timezone

from infrastructure.connectors.apolar_anuncios import (
    ApolarAnunciosConnector,
    RegistroNormalizado,
    hash_identificador_anuncio,
)
from infrastructure.connectors.apolar_anuncios.parsing import parse_url_anuncio
from infrastructure.connectors.text import slugify
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.anuncio_repository import (
    insert_observacoes_anuncio,
    listar_identificadores_fonte_com_observacao,
)
from infrastructure.database.repositories.entidade_repository import upsert_entidades
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 200


def _territorio_id_por_slug() -> dict[str, str]:
    with get_session() as session:
        territorios = list_territorios(session, nivel="bairro")
    return {slugify(t.nome): t.territorio_id for t in territorios}


def _ja_coletados_hoje(fonte_id: str, observado_em: date) -> set[str]:
    """Ids de anúncio (não hash) já coletados hoje - calculado invertendo
    o hash pra cada URL candidata dentro do loop principal, não aqui: esta
    função só devolve os hashes já presentes."""
    with get_session() as session:
        return listar_identificadores_fonte_com_observacao(session, fonte_id, observado_em)


def _gravar_lote(lote: list[RegistroNormalizado]) -> tuple[int, int]:
    with get_session() as session:
        mapa = upsert_entidades(session, [r.entidade for r in lote])

        observacoes = []
        for r in lote:
            entidade_id_real = mapa[(r.entidade.tipo_entidade, r.entidade.identificador_fonte)]
            observacao = r.observacao
            if entidade_id_real != observacao.entidade_id:
                observacao = replace(observacao, entidade_id=entidade_id_real)
            observacoes.append(observacao)

        gravados = insert_observacoes_anuncio(session, observacoes)
    return len(lote), gravados


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None, help="máximo de páginas novas a renderizar")
    args = parser.parse_args()

    connector = ApolarAnunciosConnector()
    iniciado_em = datetime.now(timezone.utc)
    # Cadência semanal (não mensal como alvaras_smf) - observado_em é o
    # dia real da coleta, não o dia 1º do mês.
    observado_em = date.today()
    status = "sucesso"
    lidos = gravados = falhas = 0

    territorio_lookup = _territorio_id_por_slug()
    logger.info("%d territórios (bairro) carregados para resolução de bairro", len(territorio_lookup))

    identificadores_ja_coletados = _ja_coletados_hoje(connector.fonte_id, observado_em)
    logger.info(
        "%d identificadores já coletados para %s - serão pulados",
        len(identificadores_ja_coletados),
        observado_em,
    )

    try:
        snapshot = connector.fetch()
        logger.info("%d URLs de Curitiba encontradas no sitemap", len(snapshot.conteudo))

        # ja_coletados que o conector espera é um set de id_anuncio (chave
        # natural da URL), não de hash - traduz aqui, uma vez, pra não
        # recalcular hash por URL dentro do conector a cada chamada.
        ja_coletados_ids: set[str] = set()
        for url in snapshot.conteudo:
            campos = parse_url_anuncio(url)
            if campos is None:
                continue
            if hash_identificador_anuncio(connector.fonte_id, campos.id_anuncio) in identificadores_ja_coletados:
                ja_coletados_ids.add(campos.id_anuncio)

        lote: list[RegistroNormalizado] = []
        for registro in connector.normalize(
            snapshot,
            observado_em=observado_em,
            territorio_id_por_slug=territorio_lookup,
            ja_coletados=ja_coletados_ids,
            limite=args.limite,
        ):
            lote.append(registro)
            lidos += 1
            if len(lote) >= TAMANHO_LOTE:
                n_lidos, n_gravados = _gravar_lote(lote)
                gravados += n_gravados
                logger.info("lote gravado: %d lidos, %d gravados (total: %d)", n_lidos, n_gravados, lidos)
                lote = []

        if lote:
            n_lidos, n_gravados = _gravar_lote(lote)
            gravados += n_gravados
            logger.info("lote final gravado: %d lidos, %d gravados", n_lidos, n_gravados)

    except Exception:
        status = "falha"
        logger.exception("falha na ingestão")
        raise
    finally:
        finalizado_em = datetime.now(timezone.utc)
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=finalizado_em,
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )

    logger.info("concluído: %d lidos, %d gravados, status=%s", lidos, gravados, status)


if __name__ == "__main__":
    main()
