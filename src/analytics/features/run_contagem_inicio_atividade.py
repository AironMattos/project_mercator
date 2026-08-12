"""Calcula e grava analytics.contagem_inicio_atividade a partir de
canonical.observacao_entidade.atributos->>'inicio_atividade' - a fonte
usada pelo indicador de aberturas (baseline/tendência/ranking, ver
checkpoint 8b em CLAUDE.md), que precisa de profundidade real de meses
mesmo com poucos snapshots de evento processados.

A query de origem (DISTINCT ON pra deduplicar por entidade, sobre todas
as observações) é cara - por isso vira uma tabela materializada em vez de
rodar ao vivo a cada request da API (achado medindo o tempo de resposta
real de /ranking/comercio e /bairros/{id}/resumo depois do checkpoint 8d
ir ao ar: 10-12s por request). Precisa ser rodado de novo sempre que um
novo snapshot de alvarás for processado - mesmo padrão operacional de
run_contagem_eventos.py.

Uso:
    python -m analytics.features.run_contagem_inicio_atividade
"""
from __future__ import annotations

import logging

from sqlalchemy import Date, func, select

from commerce.cnae import normalizar_codigo_cnae
from infrastructure.database.orm.dim_categoria import DimCategoria
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade
from infrastructure.database.repositories.categoria_repository import (
    categoria_id_por_codigo_cnae,
)
from infrastructure.database.repositories.indicador_repository import (
    substituir_contagem_inicio_atividade,
)
from infrastructure.database.repositories.territorio_repository import (
    list_territorios,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FONTE_ID = "alvaras_smf"


def _contar_por_territorio_mes_cnae(session) -> list[tuple[str, object, str | None, int]]:
    """Uma linha por (territorio_id, mes, cnae_principal) - a query cara,
    deduplicada por entidade (o mesmo alvará aparece em mais de um
    snapshot com o mesmo INICIO_ATIVIDADE, contá-lo mais de uma vez infla
    a contagem).
    """
    tabela = ObservacaoEntidade
    territorio_expr = tabela.atributos["territorio_id"].astext
    inicio_expr = tabela.atributos["inicio_atividade"].astext
    cnae_expr = tabela.atributos["cnae_principal"].astext

    ultima_observacao = (
        select(
            tabela.entidade_id,
            territorio_expr.label("territorio_id"),
            inicio_expr.label("inicio_atividade"),
            cnae_expr.label("cnae_principal"),
        )
        .distinct(tabela.entidade_id)
        .where(tabela.fonte_id == FONTE_ID, inicio_expr.isnot(None))
        .order_by(tabela.entidade_id, tabela.observado_em.desc())
        .subquery()
    )

    mes_expr = func.date_trunc("month", ultima_observacao.c.inicio_atividade.cast(Date))
    stmt = (
        select(
            ultima_observacao.c.territorio_id,
            mes_expr.label("mes"),
            ultima_observacao.c.cnae_principal,
            func.count().label("contagem"),
        )
        .where(ultima_observacao.c.territorio_id.isnot(None))
        .group_by(ultima_observacao.c.territorio_id, mes_expr, ultima_observacao.c.cnae_principal)
    )
    return list(session.execute(stmt))


def _agrupar_por_categoria(
    linhas_brutas, categoria_por_codigo: dict[str, str]
) -> list[tuple[str, str | None, object, int]]:
    """Resolve cnae_principal -> categoria_id e soma contagens que caem na
    mesma categoria (vários CNAEs podem mapear pra uma só). categoria_id
    None agrupa CNAEs não resolvidos, não é descartado.
    """
    agregados: dict[tuple[str, str | None, object], int] = {}
    for territorio_id, mes, cnae_principal, contagem in linhas_brutas:
        codigo = normalizar_codigo_cnae(cnae_principal)
        categoria_id = categoria_por_codigo.get(codigo)
        mes_normalizado = mes.date() if hasattr(mes, "date") else mes
        chave = (territorio_id, categoria_id, mes_normalizado)
        agregados[chave] = agregados.get(chave, 0) + contagem

    return [(t, c, m, n) for (t, c, m), n in agregados.items()]


def _imprimir_resumo(linhas, nome_territorio, nome_categoria) -> None:
    total = sum(n for _, _, _, n in linhas)
    print(f"\n=== INICIO_ATIVIDADE materializado (total: {total}) ===")

    por_bairro: dict[str, int] = {}
    for t, _c, _m, n in linhas:
        chave = nome_territorio.get(t, "(sem bairro)")
        por_bairro[chave] = por_bairro.get(chave, 0) + n
    print("Top 10 bairros:")
    for bairro, n in sorted(por_bairro.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {bairro:30s} {n:6d}")

    por_categoria: dict[str, int] = {}
    for _t, c, _m, n in linhas:
        chave = nome_categoria.get(c, "(sem categoria)")
        por_categoria[chave] = por_categoria.get(chave, 0) + n
    print("Top 10 categorias:")
    for categoria, n in sorted(por_categoria.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {categoria:40s} {n:6d}")


def main() -> None:
    with get_session() as session:
        logger.info("consultando INICIO_ATIVIDADE deduplicado por entidade (pode levar alguns segundos)...")
        linhas_brutas = _contar_por_territorio_mes_cnae(session)
        logger.info("%d linhas brutas (territorio x mes x cnae)", len(linhas_brutas))

        categoria_por_codigo = categoria_id_por_codigo_cnae(session)
        nome_territorio = {t.territorio_id: t.nome for t in list_territorios(session)}
        nome_categoria = {
            row.categoria_id: row.nome for row in session.execute(select(DimCategoria)).scalars()
        }

    linhas = _agrupar_por_categoria(linhas_brutas, categoria_por_codigo)
    logger.info("%d linhas agregadas (territorio x categoria x mes)", len(linhas))

    with get_session() as session:
        gravadas = substituir_contagem_inicio_atividade(session, linhas)
    logger.info("%d linhas gravadas em analytics.contagem_inicio_atividade", gravadas)

    _imprimir_resumo(linhas, nome_territorio, nome_categoria)


if __name__ == "__main__":
    main()
