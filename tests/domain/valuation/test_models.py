from datetime import date

import pytest
from shapely.geometry import Point, Polygon

from domain.valuation import ValorMonetario, ValorReferenciaTerritorial


def _base_kwargs():
    return dict(valor_m2=1500.0, tipo_valor="venal", componente="terreno", fonte_id="ippuc_pgv")


def test_valor_monetario_valido_e_aceito():
    v = ValorMonetario(**_base_kwargs())
    assert v.tipo_valor == "venal"
    assert v.componente == "terreno"


def test_tipo_valor_invalido_rejeitado():
    kwargs = _base_kwargs()
    kwargs["tipo_valor"] = "preco"
    with pytest.raises(ValueError):
        ValorMonetario(**kwargs)


def test_componente_invalido_rejeitado():
    kwargs = _base_kwargs()
    kwargs["componente"] = "aluguel"
    with pytest.raises(ValueError):
        ValorMonetario(**kwargs)


def test_fonte_id_vazia_rejeitada():
    kwargs = _base_kwargs()
    kwargs["fonte_id"] = ""
    with pytest.raises(ValueError):
        ValorMonetario(**kwargs)


def test_valor_m2_negativo_rejeitado():
    kwargs = _base_kwargs()
    kwargs["valor_m2"] = -1.0
    with pytest.raises(ValueError):
        ValorMonetario(**kwargs)


@pytest.mark.parametrize("tipo_valor", ["venal", "avaliacao", "anuncio", "transacao"])
def test_todos_os_quatro_tipos_de_valor_sao_aceitos(tipo_valor):
    kwargs = _base_kwargs()
    kwargs["tipo_valor"] = tipo_valor
    v = ValorMonetario(**kwargs)
    assert v.tipo_valor == tipo_valor


@pytest.mark.parametrize("componente", ["terreno", "construcao", "total"])
def test_todos_os_tres_componentes_sao_aceitos(componente):
    kwargs = _base_kwargs()
    kwargs["componente"] = componente
    v = ValorMonetario(**kwargs)
    assert v.componente == componente


def _base_kwargs_territorial():
    return dict(
        geometria=Point(0, 0),
        tipo_valor="venal",
        componente="terreno",
        valor_m2=1500.0,
        moeda_data=date(2025, 1, 1),
        fonte_id="ippuc_pgv",
        vigencia_inicio=date(2025, 1, 1),
        snapshot_ref="teste",
    )


def test_valor_referencia_territorial_valido_e_aceito():
    v = ValorReferenciaTerritorial(**_base_kwargs_territorial())
    assert v.territorio_id is None
    assert v.vigencia_fim is None
    assert v.valor_id is not None


def test_valor_referencia_territorial_tipo_valor_invalido_rejeitado():
    kwargs = _base_kwargs_territorial()
    kwargs["tipo_valor"] = "preco"
    with pytest.raises(ValueError):
        ValorReferenciaTerritorial(**kwargs)


def test_valor_referencia_territorial_geometria_vazia_rejeitada():
    kwargs = _base_kwargs_territorial()
    kwargs["geometria"] = Polygon()
    with pytest.raises(ValueError):
        ValorReferenciaTerritorial(**kwargs)
