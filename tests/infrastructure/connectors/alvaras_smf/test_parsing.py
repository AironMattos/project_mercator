from datetime import date

from infrastructure.connectors.alvaras_smf.parsing import (
    parse_data_br,
    parse_referencia_arquivo,
    valor_ou_none,
)


def test_valor_ou_none_com_marcador_ausente():
    assert valor_ou_none("***") is None


def test_valor_ou_none_com_none():
    assert valor_ou_none(None) is None


def test_valor_ou_none_com_nan_float():
    assert valor_ou_none(float("nan")) is None


def test_valor_ou_none_com_espacos():
    assert valor_ou_none("   ") is None


def test_valor_ou_none_com_valor_normal():
    assert valor_ou_none("TATUQUARA") == "TATUQUARA"


def test_valor_ou_none_faz_strip():
    assert valor_ou_none("  CENTRO  ") == "CENTRO"


def test_parse_data_br_valida():
    assert parse_data_br("29/05/2013") == "2013-05-29"


def test_parse_data_br_ausente():
    assert parse_data_br("***") is None


def test_parse_data_br_invalida():
    assert parse_data_br("32/13/2013") is None


def test_parse_referencia_arquivo():
    nome = "2026-08-01_Alvaras_-_Base_de_Dados.csv"
    assert parse_referencia_arquivo(nome) == date(2026, 8, 1)
