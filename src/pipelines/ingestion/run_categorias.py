"""Semeia canonical.dim_categoria e canonical.cnae_categoria_map a partir do
mapeamento estático em commerce.categories (lista pequena e explícita,
não uma fonte externa).

Pré-requisito: canonical.dim_cnae precisa estar populada antes (rodar
pipelines.ingestion.run_ibge_cnae primeiro) - cnae_categoria_map tem FK
para dim_cnae.

Uso:
    python -m pipelines.ingestion.run_categorias
"""
from __future__ import annotations

import logging

from commerce.categories import CATEGORIAS, MAPEAMENTO_CNAE_CATEGORIA, Categoria
from infrastructure.database.repositories.categoria_repository import (
    upsert_categorias,
    upsert_cnae_categoria_map,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    categorias = [Categoria(categoria_id=cid, nome=nome) for cid, nome in CATEGORIAS.items()]

    with get_session() as session:
        n_categorias = upsert_categorias(session, categorias)
        n_mapeamentos = upsert_cnae_categoria_map(session, MAPEAMENTO_CNAE_CATEGORIA)

    logger.info("categorias gravadas: %d", n_categorias)
    logger.info("mapeamentos cnae->categoria gravados: %d", n_mapeamentos)


if __name__ == "__main__":
    main()
