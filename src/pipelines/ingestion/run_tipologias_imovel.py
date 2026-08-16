"""Semeia canonical.dim_tipologia_imovel a partir do catálogo estático em
domain.anuncio (lista pequena e explícita, não uma fonte externa) - mesmo
padrão de pipelines.ingestion.run_categorias (Radar de Comércio).

Uso:
    python -m pipelines.ingestion.run_tipologias_imovel
"""
from __future__ import annotations

import logging

from domain.anuncio import NOMES_TIPOLOGIA
from infrastructure.database.repositories.tipologia_repository import upsert_tipologias
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    with get_session() as session:
        n = upsert_tipologias(session, NOMES_TIPOLOGIA)
    logger.info("tipologias gravadas: %d", n)


if __name__ == "__main__":
    main()
