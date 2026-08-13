from __future__ import annotations

import math
import uuid

from shapely.geometry import Point

from domain.location.models import (
    LIMIAR_CONCORDANCIA_M,
    LIMIAR_DISCORDANCIA_GRAVE_M,
    PRECISOES_QUE_DISPENSAM_SEGUNDA_PASSAGEM,
    DecisaoFinal,
    DecisaoInicial,
    ResultadoGeolocalizacao,
)

_METROS_POR_GRAU_LATITUDE = 111_320.0


def avaliar_geocodebr(precisao_geocodebr: str | None) -> DecisaoInicial:
    """Etapa 1 (regra pura, sem I/O): dado o nível de precisão que o
    geocodebr retornou pra uma entidade, decide a confiança provisória e
    se a entidade precisa da segunda passagem (Nominatim).

    precisao_geocodebr=None cobre tanto "geocodebr não encontrou nada"
    quanto qualquer valor fora do vocabulário esperado - tratado como
    "não resolvido", nunca como sucesso silencioso.
    """
    if precisao_geocodebr in PRECISOES_QUE_DISPENSAM_SEGUNDA_PASSAGEM:
        return DecisaoInicial(confianca="alta", precisa_segunda_passagem=False)
    return DecisaoInicial(confianca="baixa", precisa_segunda_passagem=True)


def distancia_metros(p1: Point, p2: Point) -> float:
    """Aproximação plana (equirretangular, com correção de cosseno da
    latitude) - suficiente para as distâncias em jogo aqui (dezenas de
    metros a poucos quilômetros dentro de Curitiba); mesma técnica usada
    no Piloto 1 pra triagem de ambiguidade. Não é para uso em distâncias
    continentais.
    """
    lon1, lat1 = p1.x, p1.y
    lon2, lat2 = p2.x, p2.y
    dlat = (lat2 - lat1) * _METROS_POR_GRAU_LATITUDE
    dlon = (lon2 - lon1) * _METROS_POR_GRAU_LATITUDE * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


def reconciliar(ponto_geocodebr: Point | None, ponto_nominatim: Point | None) -> DecisaoFinal:
    """Etapa 2 (regra pura, sem I/O): só chamada para entidades que a
    Etapa 1 marcou precisa_segunda_passagem=True. Decide o ponto final e a
    confiança a partir do que as duas fontes retornaram.

    Quatro ramos do prompt de referência, na ordem:
    1. (tratado em avaliar_geocodebr, não aqui) geocodebr número exato.
    2. (tratado em avaliar_geocodebr) impreciso/nada -> fila.
    3. Nominatim também não resolve -> baixa, ponto None.
    4. os dois resolvem -> concordância/discordância por distância.

    Dois ramos adicionais, não descritos explicitamente no prompt mas
    necessários pra cobrir os casos reais que aparecem numa fila que
    inclui tanto "geocodebr impreciso" quanto "geocodebr não achou nada":
    - geocodebr não achou nada, mas Nominatim resolve: fica com o ponto do
      Nominatim, mas confianca='media', não 'alta' - não há segunda fonte
      pra confirmar por distância, então não ganha o nível mais alto.
    - geocodebr achou algo (impreciso) mas Nominatim não resolve nem
      contesta: fica com o ponto do geocodebr, confianca continua 'baixa'
      (não regride pra None - ainda é a única informação que temos).
    """
    if ponto_geocodebr is None and ponto_nominatim is None:
        return DecisaoFinal(ponto=None, confianca="baixa", distancia_desempate_m=None)

    if ponto_geocodebr is None:
        return DecisaoFinal(ponto=ponto_nominatim, confianca="media", distancia_desempate_m=None)

    if ponto_nominatim is None:
        return DecisaoFinal(ponto=ponto_geocodebr, confianca="baixa", distancia_desempate_m=None)

    distancia = distancia_metros(ponto_geocodebr, ponto_nominatim)
    if distancia <= LIMIAR_CONCORDANCIA_M:
        confianca = "alta"
    elif distancia <= LIMIAR_DISCORDANCIA_GRAVE_M:
        confianca = "media"
    else:
        confianca = "baixa"
    return DecisaoFinal(ponto=ponto_nominatim, confianca=confianca, distancia_desempate_m=distancia)


def montar_resultado_sem_segunda_passagem(
    entidade_id: uuid.UUID,
    ponto_geocodebr: Point,
    precisao_geocodebr: str,
) -> ResultadoGeolocalizacao:
    """Monta o resultado final para o ramo 1 (numero exato, sem fila)."""
    return ResultadoGeolocalizacao(
        entidade_id=entidade_id,
        ponto=ponto_geocodebr,
        confianca="alta",
        fonte_primaria="geocodebr",
        fonte_secundaria=None,
        precisao_geocodebr=precisao_geocodebr,
        distancia_desempate_m=None,
    )


def montar_resultado_com_segunda_passagem(
    entidade_id: uuid.UUID,
    ponto_geocodebr: Point | None,
    precisao_geocodebr: str | None,
    ponto_nominatim: Point | None,
) -> ResultadoGeolocalizacao:
    """Monta o resultado final para entidades que passaram pela Etapa 2."""
    decisao = reconciliar(ponto_geocodebr, ponto_nominatim)
    return ResultadoGeolocalizacao(
        entidade_id=entidade_id,
        ponto=decisao.ponto,
        confianca=decisao.confianca,
        fonte_primaria="geocodebr",
        fonte_secundaria="nominatim",
        precisao_geocodebr=precisao_geocodebr,
        distancia_desempate_m=decisao.distancia_desempate_m,
    )
