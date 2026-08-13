"""Pipeline de geocodificação, Etapa 2 (Nominatim, resíduo) - Checkpoint 9c.

Roda só sobre as entidades que a Etapa 1 deixou com confianca='baixa'
provisória (fonte_secundaria IS NULL - ver
geolocalizacao_repository.entidades_pendentes_segunda_passagem). Antes de
gastar tempo de verdade, estima o tempo total a 1 req/s e para pra
reportar se ultrapassar LIMIAR_HORAS_PARA_PARAR - nesse volume, vale
considerar hospedar uma instância própria do Nominatim (só Brasil, ver
https://nominatim.org/release-docs/latest/admin/Installation/) em vez de
rodar contra o serviço público por tanto tempo.

Uso:
    python -m pipelines.geocoding.etapa2_nominatim [--forcar] [limite_teste]
"""
from __future__ import annotations

import logging
import sys
import time

import requests

from domain.location import montar_resultado_com_segunda_passagem
from infrastructure.database.repositories.geolocalizacao_repository import (
    casos_discordancia_grave,
    contar_por_confianca,
    entidades_pendentes_segunda_passagem,
    upsert_geolocalizacao,
)
from infrastructure.database.session import get_session
from infrastructure.geocoding.nominatim import (
    INTERVALO_MINIMO_ENTRE_CHAMADAS_S,
    geocodificar,
    montar_endereco,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 500

# Média observada no Piloto 1 (1s de sleep + latência real de rede) -
# mais realista que o limite teórico de 1.0s puro pra extrapolar tempo.
SEGUNDOS_POR_REQUISICAO_OBSERVADO = 1.36

LIMIAR_HORAS_PARA_PARAR = 7.0


def _estimar_horas(n: int) -> float:
    return (n * SEGUNDOS_POR_REQUISICAO_OBSERVADO) / 3600


def main() -> None:
    args = sys.argv[1:]
    forcar = "--forcar" in args
    args = [a for a in args if a != "--forcar"]
    limite_teste = int(args[0]) if args else None

    with get_session() as session:
        pendentes = entidades_pendentes_segunda_passagem(session, limit=limite_teste)

    n = len(pendentes)
    horas_estimadas = _estimar_horas(n)
    logger.info(
        "%d entidades com confianca='baixa' provisória, aguardando 2ª passagem "
        "(estimativa a 1 req/s: %.1fh)",
        n,
        horas_estimadas,
    )

    if n == 0:
        logger.info("nada pendente - Etapa 1 já resolveu tudo, ou Etapa 2 já rodou.")
        return

    if horas_estimadas > LIMIAR_HORAS_PARA_PARAR and not forcar:
        logger.warning(
            "estimativa de %.1fh ultrapassa o limiar de %.1fh - parando antes de "
            "rodar contra o Nominatim público. Nesse volume, considere hospedar uma "
            "instância própria do Nominatim (só Brasil) em vez de rodar dias contra "
            "o serviço público - ver https://nominatim.org/release-docs/latest/admin/Installation/. "
            "Se decidir prosseguir mesmo assim, rode de novo com --forcar.",
            horas_estimadas,
            LIMIAR_HORAS_PARA_PARAR,
        )
        return

    http = requests.Session()
    total_processado = 0
    for inicio in range(0, n, TAMANHO_LOTE):
        lote = pendentes[inicio : inicio + TAMANHO_LOTE]
        resultados = []
        for pendente in lote:
            endereco = montar_endereco(pendente.logradouro, pendente.numero, pendente.bairro, pendente.cep)
            try:
                resultado_nominatim = geocodificar(endereco, http)
                ponto_nominatim = resultado_nominatim.ponto
            except requests.RequestException as e:
                logger.warning("erro de rede pra entidade %s: %s - tratando como falha", pendente.entidade_id, e)
                ponto_nominatim = None
            time.sleep(INTERVALO_MINIMO_ENTRE_CHAMADAS_S)

            resultados.append(
                montar_resultado_com_segunda_passagem(
                    pendente.entidade_id,
                    pendente.ponto_geocodebr,
                    pendente.precisao_geocodebr,
                    ponto_nominatim,
                )
            )

        with get_session() as session:
            upsert_geolocalizacao(session, resultados)
        total_processado += len(lote)
        logger.info("%d/%d processadas", total_processado, n)

    with get_session() as session:
        distribuicao = contar_por_confianca(session)
        discordancias_graves = casos_discordancia_grave(session)

    logger.info("concluído. distribuição de confiança final: %s", distribuicao)
    logger.info(
        "%d casos de discordância grave (> 1km) entre geocodebr e Nominatim",
        len(discordancias_graves),
    )
    for entidade_id, distancia in sorted(discordancias_graves, key=lambda x: -x[1])[:20]:
        logger.info("  discordância grave: entidade_id=%s distancia_m=%.0f", entidade_id, distancia)


if __name__ == "__main__":
    main()
