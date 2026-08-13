import uuid

import pytest
from shapely.geometry import Point

from domain.location import (
    LIMIAR_CONCORDANCIA_M,
    LIMIAR_DISCORDANCIA_GRAVE_M,
    avaliar_geocodebr,
    distancia_metros,
    montar_resultado_com_segunda_passagem,
    montar_resultado_sem_segunda_passagem,
    reconciliar,
)

# Ponto de referência dentro de Curitiba (Lindóia, mesma área dos pilotos) -
# usado como base pra deslocar coordenadas em metros conhecidos.
_REF = Point(-49.2788, -25.4799)
_METROS_POR_GRAU_LATITUDE = 111_320.0


def _deslocado_norte(ponto: Point, metros: float) -> Point:
    """Desloca só em latitude - evita ter que corrigir por cosseno,
    suficiente pros testes de distância aqui."""
    return Point(ponto.x, ponto.y + metros / _METROS_POR_GRAU_LATITUDE)


# --- Ramo 1: geocodebr número exato -> alta, sem segunda passagem ---


def test_geocodebr_numero_exato_dispensa_segunda_passagem():
    decisao = avaliar_geocodebr("numero")

    assert decisao.confianca == "alta"
    assert decisao.precisa_segunda_passagem is False


def test_montar_resultado_sem_segunda_passagem_usa_ponto_do_geocodebr():
    entidade_id = uuid.uuid4()
    resultado = montar_resultado_sem_segunda_passagem(entidade_id, _REF, "numero")

    assert resultado.ponto == _REF
    assert resultado.confianca == "alta"
    assert resultado.fonte_primaria == "geocodebr"
    assert resultado.fonte_secundaria is None
    assert resultado.precisao_geocodebr == "numero"
    assert resultado.distancia_desempate_m is None


# --- Ramo 2: geocodebr impreciso ou sem match -> baixa provisória, enfileira ---


@pytest.mark.parametrize(
    "precisao",
    ["numero_aproximado", "logradouro", "cep", "localidade", "municipio", None],
)
def test_geocodebr_impreciso_ou_sem_match_enfileira_para_segunda_passagem(precisao):
    decisao = avaliar_geocodebr(precisao)

    assert decisao.confianca == "baixa"
    assert decisao.precisa_segunda_passagem is True


# --- Ramo 3: segunda passagem, Nominatim também não resolve -> baixa, ponto None ---


def test_nenhuma_fonte_resolve_confianca_baixa_ponto_none():
    decisao = reconciliar(ponto_geocodebr=None, ponto_nominatim=None)

    assert decisao.ponto is None
    assert decisao.confianca == "baixa"
    assert decisao.distancia_desempate_m is None


def test_geocodebr_impreciso_e_nominatim_nao_resolve_mantem_ponto_do_geocodebr_baixa():
    decisao = reconciliar(ponto_geocodebr=_REF, ponto_nominatim=None)

    assert decisao.ponto == _REF
    assert decisao.confianca == "baixa"
    assert decisao.distancia_desempate_m is None


def test_geocodebr_sem_match_mas_nominatim_resolve_usa_nominatim_confianca_media():
    decisao = reconciliar(ponto_geocodebr=None, ponto_nominatim=_REF)

    assert decisao.ponto == _REF
    assert decisao.confianca == "media"
    assert decisao.distancia_desempate_m is None


# --- Ramo 4: os dois resolvem -> concordância/discordância por distância ---


def test_concordancia_ate_150m_confianca_alta_usa_ponto_nominatim():
    ponto_geocodebr = _REF
    ponto_nominatim = _deslocado_norte(_REF, 50)

    decisao = reconciliar(ponto_geocodebr, ponto_nominatim)

    assert decisao.ponto == ponto_nominatim
    assert decisao.confianca == "alta"
    assert decisao.distancia_desempate_m == pytest.approx(50, abs=1)


def test_discordancia_moderada_confianca_media_usa_ponto_nominatim():
    ponto_geocodebr = _REF
    ponto_nominatim = _deslocado_norte(_REF, 500)

    decisao = reconciliar(ponto_geocodebr, ponto_nominatim)

    assert decisao.ponto == ponto_nominatim
    assert decisao.confianca == "media"
    assert decisao.distancia_desempate_m == pytest.approx(500, abs=1)


def test_discordancia_grave_confianca_baixa_usa_ponto_nominatim_e_registra_distancia():
    ponto_geocodebr = _REF
    ponto_nominatim = _deslocado_norte(_REF, 2000)

    decisao = reconciliar(ponto_geocodebr, ponto_nominatim)

    assert decisao.ponto == ponto_nominatim
    assert decisao.confianca == "baixa"
    assert decisao.distancia_desempate_m == pytest.approx(2000, abs=1)


def test_limiar_de_concordancia_e_inclusive():
    ponto_nominatim = _deslocado_norte(_REF, LIMIAR_CONCORDANCIA_M)

    decisao = reconciliar(_REF, ponto_nominatim)

    assert decisao.confianca == "alta"


def test_limiar_de_discordancia_grave_e_inclusive_na_faixa_media():
    ponto_nominatim = _deslocado_norte(_REF, LIMIAR_DISCORDANCIA_GRAVE_M)

    decisao = reconciliar(_REF, ponto_nominatim)

    assert decisao.confianca == "media"


def test_montar_resultado_com_segunda_passagem_registra_as_duas_fontes():
    entidade_id = uuid.uuid4()
    ponto_nominatim = _deslocado_norte(_REF, 50)

    resultado = montar_resultado_com_segunda_passagem(
        entidade_id, _REF, "numero_aproximado", ponto_nominatim
    )

    assert resultado.entidade_id == entidade_id
    assert resultado.ponto == ponto_nominatim
    assert resultado.confianca == "alta"
    assert resultado.fonte_primaria == "geocodebr"
    assert resultado.fonte_secundaria == "nominatim"
    assert resultado.precisao_geocodebr == "numero_aproximado"
    assert resultado.distancia_desempate_m == pytest.approx(50, abs=1)


def test_distancia_metros_zero_para_mesmo_ponto():
    assert distancia_metros(_REF, _REF) == 0.0
