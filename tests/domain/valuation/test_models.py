from datetime import date

import pytest
from shapely.geometry import Point, Polygon

from domain.valuation import (
    IndicadorMercadoImobiliarioUf,
    ValorMonetario,
    ValorReferenciaTerritorial,
)


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


def _base_kwargs_indicador_bcb():
    return dict(
        uf="PR",
        periodo_referencia=date(2026, 4, 1),
        indicador="imoveis_valor_avaliacao",
        categoria="valor",
        tipo_valor="avaliacao",
        unidade="R$",
        leitura=300000.0,
        fonte_id="bcb_mercado_imobiliario",
        snapshot_ref="teste",
    )


def test_indicador_bcb_categoria_valor_com_tipo_valor_e_aceito():
    i = IndicadorMercadoImobiliarioUf(**_base_kwargs_indicador_bcb())
    assert i.tipo_valor == "avaliacao"


def test_indicador_bcb_categoria_valor_sem_tipo_valor_rejeitado():
    kwargs = _base_kwargs_indicador_bcb()
    kwargs["tipo_valor"] = None
    with pytest.raises(ValueError):
        IndicadorMercadoImobiliarioUf(**kwargs)


def test_indicador_bcb_categoria_contagem_com_tipo_valor_rejeitado():
    kwargs = _base_kwargs_indicador_bcb()
    kwargs["categoria"] = "contagem"
    kwargs["unidade"] = "imóveis"
    # tipo_valor continua setado (herdado do base kwargs) - deve ser
    # rejeitado porque só categoria='valor' pode carregar tipo_valor.
    with pytest.raises(ValueError):
        IndicadorMercadoImobiliarioUf(**kwargs)


def test_indicador_bcb_categoria_contagem_sem_tipo_valor_e_aceito():
    kwargs = _base_kwargs_indicador_bcb()
    kwargs["categoria"] = "contagem"
    kwargs["unidade"] = "imóveis"
    kwargs["tipo_valor"] = None
    i = IndicadorMercadoImobiliarioUf(**kwargs)
    assert i.tipo_valor is None


def test_indicador_bcb_categoria_invalida_rejeitada():
    kwargs = _base_kwargs_indicador_bcb()
    kwargs["categoria"] = "preco"
    with pytest.raises(ValueError):
        IndicadorMercadoImobiliarioUf(**kwargs)


def test_indicador_bcb_uf_vazia_rejeitada():
    kwargs = _base_kwargs_indicador_bcb()
    kwargs["uf"] = ""
    with pytest.raises(ValueError):
        IndicadorMercadoImobiliarioUf(**kwargs)
