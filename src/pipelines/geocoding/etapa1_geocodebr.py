"""Pipeline de geocodificação, Etapa 1 (geocodebr) - Checkpoint 9b.

Geocodifica todas as entidades tipo_entidade='comercio' que ainda não têm
linha em canonical.geolocalizacao_entidade, usando geocodebr (subprocesso
R, offline/CNEFE - ver src/infrastructure/geocoding/geocodebr_subprocess.py).

Retomável: cada lote de TAMANHO_LOTE entidades é commitado antes do
próximo começar, e a query de origem (entidades_comercio_pendentes) já
exclui quem tem linha - rodar de novo depois de uma queda no meio do
caminho continua de onde parou, sem parâmetro extra.

Uso:
    python -m pipelines.geocoding.etapa1_geocodebr [limite_teste]
"""
from __future__ import annotations

import logging
import sys
import time

from domain.location import ResultadoGeolocalizacao, avaliar_geocodebr, montar_resultado_sem_segunda_passagem
from infrastructure.database.repositories.geolocalizacao_repository import (
    contar_por_confianca,
    entidades_comercio_pendentes,
    upsert_geolocalizacao,
)
from infrastructure.database.session import get_session
from infrastructure.geocoding.geocodebr_subprocess import EnderecoParaGeocodificar, geocodificar_lote
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 5000

# O subprocesso R (via callr, dentro de geocodebr::geocode) pode falhar de
# forma transitória (visto na prática: "could not start R, exited with
# non-zero status, has crashed or was killed" depois de dezenas de lotes
# bem-sucedidos, sem sinal de exaustão de disco/memória) - poucas
# retentativas com um pequeno intervalo evitam que um hiccup pontual
# derrube um pipeline de ~100 lotes inteiro.
TENTATIVAS_POR_LOTE = 3
SEGUNDOS_ENTRE_TENTATIVAS = 5.0


def _geocodificar_lote_com_retentativa(lote: list[EnderecoParaGeocodificar]):
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_POR_LOTE + 1):
        try:
            return geocodificar_lote(lote)
        except RuntimeError as e:
            ultimo_erro = e
            logger.warning(
                "tentativa %d/%d do lote falhou (%s) - tentando de novo em %.0fs",
                tentativa,
                TENTATIVAS_POR_LOTE,
                e,
                SEGUNDOS_ENTRE_TENTATIVAS,
            )
            time.sleep(SEGUNDOS_ENTRE_TENTATIVAS)
    raise ultimo_erro


def _processar_lote(lote: list[EnderecoParaGeocodificar]) -> tuple[int, int]:
    """Roda geocodebr sobre o lote, aplica a regra de avaliação (Etapa 1
    da regra de reconciliação) e grava. Retorna (n_alta, n_enfileirado)."""
    resultados_geocodebr = _geocodificar_lote_com_retentativa(lote)
    por_entidade = {r.entidade_id: r for r in resultados_geocodebr}

    n_alta = n_enfileirado = 0
    resultados_finais: list[ResultadoGeolocalizacao] = []
    for endereco in lote:
        r = por_entidade.get(endereco.entidade_id)
        precisao = r.precisao if r else None
        ponto = Point(r.lon, r.lat) if r and r.lat is not None and r.lon is not None else None

        decisao = avaliar_geocodebr(precisao)
        if not decisao.precisa_segunda_passagem:
            n_alta += 1
            resultados_finais.append(
                montar_resultado_sem_segunda_passagem(endereco.entidade_id, ponto, precisao)
            )
        else:
            n_enfileirado += 1
            resultados_finais.append(
                ResultadoGeolocalizacao(
                    entidade_id=endereco.entidade_id,
                    ponto=ponto,
                    confianca="baixa",
                    fonte_primaria="geocodebr",
                    fonte_secundaria=None,
                    precisao_geocodebr=precisao,
                    distancia_desempate_m=None,
                )
            )

    with get_session() as session:
        upsert_geolocalizacao(session, resultados_finais)

    return n_alta, n_enfileirado


def main() -> None:
    limite_teste = int(sys.argv[1]) if len(sys.argv) > 1 else None

    with get_session() as session:
        pendentes = entidades_comercio_pendentes(session, limit=limite_teste)
    logger.info("%d entidades comercio pendentes de geocodificação", len(pendentes))

    total_alta = total_enfileirado = 0
    for inicio in range(0, len(pendentes), TAMANHO_LOTE):
        lote = pendentes[inicio : inicio + TAMANHO_LOTE]
        n_alta, n_enfileirado = _processar_lote(lote)
        total_alta += n_alta
        total_enfileirado += n_enfileirado
        logger.info(
            "lote %d-%d: %d processadas (alta=%d enfileirado=%d) | total: alta=%d enfileirado=%d",
            inicio,
            inicio + len(lote),
            len(lote),
            n_alta,
            n_enfileirado,
            total_alta,
            total_enfileirado,
        )

    with get_session() as session:
        distribuicao = contar_por_confianca(session)
    logger.info("concluído. distribuição de confiança acumulada: %s", distribuicao)


if __name__ == "__main__":
    main()
