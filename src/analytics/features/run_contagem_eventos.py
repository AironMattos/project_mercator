"""Calcula e grava analytics.contagem_eventos a partir de
events.fato_evento_territorial, e imprime um resumo para conferência
visual de que a métrica conta uma história coerente.

Uso:
    python -m analytics.features.run_contagem_eventos
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from analytics.features import calcular_contagem_por_bairro_categoria_mes
from infrastructure.database.orm.dim_categoria import DimCategoria
from infrastructure.database.repositories.evento_repository import iter_eventos
from infrastructure.database.repositories.feature_repository import (
    substituir_contagem_eventos,
)
from infrastructure.database.repositories.territorio_repository import list_territorios
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _nomes_territorio(session) -> dict[str, str]:
    return {t.territorio_id: t.nome for t in list_territorios(session)}


def _nomes_categoria(session) -> dict[str, str]:
    return {
        row.categoria_id: row.nome
        for row in session.execute(select(DimCategoria)).scalars()
    }


def _imprimir_resumo(contagens, nome_territorio, nome_categoria) -> None:
    for tipo in ("PRIMEIRA_OBSERVACAO", "DESAPARECIMENTO"):
        do_tipo = [c for c in contagens if c.event_type == tipo]
        total = sum(c.contagem for c in do_tipo)
        print(f"\n=== {tipo} (total: {total}) ===")

        por_bairro: dict[str, int] = {}
        for c in do_tipo:
            chave = nome_territorio.get(c.territorio_id, "(sem bairro)")
            por_bairro[chave] = por_bairro.get(chave, 0) + c.contagem
        print("Top 10 bairros:")
        for bairro, n in sorted(por_bairro.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {bairro:30s} {n:5d}")

        por_categoria: dict[str, int] = {}
        for c in do_tipo:
            chave = nome_categoria.get(c.categoria_id, "(sem categoria)")
            por_categoria[chave] = por_categoria.get(chave, 0) + c.contagem
        print("Top 10 categorias:")
        for categoria, n in sorted(por_categoria.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {categoria:40s} {n:5d}")


def main() -> None:
    with get_session() as session:
        eventos = list(iter_eventos(session))
        nome_territorio = _nomes_territorio(session)
        nome_categoria = _nomes_categoria(session)

    logger.info("%d eventos carregados", len(eventos))

    contagens = calcular_contagem_por_bairro_categoria_mes(eventos)
    logger.info("%d linhas de contagem calculadas", len(contagens))

    with get_session() as session:
        gravadas = substituir_contagem_eventos(session, contagens)
    logger.info("%d linhas gravadas em analytics.contagem_eventos", gravadas)

    _imprimir_resumo(contagens, nome_territorio, nome_categoria)


if __name__ == "__main__":
    main()
