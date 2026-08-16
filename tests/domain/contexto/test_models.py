from datetime import date

import pytest

from domain.contexto import (
    IndicadorAluguelMercado,
    IndicadorCensitarioSetor,
    IndicadorFipezapBairro,
    IndicadorFipezapCidade,
)


def _base_kwargs_aluguel():
    return dict(
        cidade="Curitiba",
        periodo_referencia=date(2026, 7, 1),
        segmento="cidade_toda",
        aluguel_m2=45.9,
        fonte_id="quintoandar_indice_aluguel",
        snapshot_ref="teste",
    )


def test_indicador_aluguel_valido_e_aceito():
    i = IndicadorAluguelMercado(**_base_kwargs_aluguel())
    assert i.segmento == "cidade_toda"
    assert i.variacao_mensal is None
    assert i.variacao_12m is None


def test_indicador_aluguel_segmento_invalido_rejeitado():
    kwargs = _base_kwargs_aluguel()
    kwargs["segmento"] = "penthouse"
    with pytest.raises(ValueError):
        IndicadorAluguelMercado(**kwargs)


def test_indicador_aluguel_negativo_rejeitado():
    kwargs = _base_kwargs_aluguel()
    kwargs["aluguel_m2"] = -1.0
    with pytest.raises(ValueError):
        IndicadorAluguelMercado(**kwargs)


def test_indicador_aluguel_cidade_vazia_rejeitada():
    kwargs = _base_kwargs_aluguel()
    kwargs["cidade"] = ""
    with pytest.raises(ValueError):
        IndicadorAluguelMercado(**kwargs)


@pytest.mark.parametrize(
    "segmento", ["cidade_toda", "1_dormitorio", "2_dormitorios", "3_dormitorios"]
)
def test_indicador_aluguel_todos_os_segmentos_validos_sao_aceitos(segmento):
    kwargs = _base_kwargs_aluguel()
    kwargs["segmento"] = segmento
    i = IndicadorAluguelMercado(**kwargs)
    assert i.segmento == segmento


def _base_kwargs_censo():
    return dict(
        setor_censitario="410690205010001",
        municipio_codigo="4106902",
        area_km2=0.07,
        populacao_total=496,
        domicilios_total=361,
        domicilios_particulares_ocupados=242,
        domicilios_particulares_vagos=86,
        ano_referencia=2022,
        fonte_id="ibge_censo_setor",
        snapshot_ref="teste",
    )


def test_indicador_censitario_valido_e_aceito():
    i = IndicadorCensitarioSetor(**_base_kwargs_censo())
    assert i.territorio_id is None


def test_indicador_censitario_populacao_negativa_rejeitada():
    kwargs = _base_kwargs_censo()
    kwargs["populacao_total"] = -1
    with pytest.raises(ValueError):
        IndicadorCensitarioSetor(**kwargs)


def test_indicador_censitario_setor_vazio_rejeitado():
    kwargs = _base_kwargs_censo()
    kwargs["setor_censitario"] = ""
    with pytest.raises(ValueError):
        IndicadorCensitarioSetor(**kwargs)


def test_indicador_censitario_ano_referencia_invalido_rejeitado():
    kwargs = _base_kwargs_censo()
    kwargs["ano_referencia"] = 0
    with pytest.raises(ValueError):
        IndicadorCensitarioSetor(**kwargs)


def _base_kwargs_fipezap_cidade():
    return dict(
        cidade="Curitiba",
        operacao="venda",
        periodo_referencia=date(2026, 7, 1),
        preco_medio_m2=11761.0,
        fonte_id="fipezap",
        snapshot_ref="teste",
    )


def test_indicador_fipezap_cidade_valido_e_aceito():
    i = IndicadorFipezapCidade(**_base_kwargs_fipezap_cidade())
    assert i.variacao_mensal is None
    assert i.variacao_acumulada_ano is None
    assert i.variacao_12m is None


def test_indicador_fipezap_cidade_operacao_invalida_rejeitada():
    kwargs = _base_kwargs_fipezap_cidade()
    kwargs["operacao"] = "aluguel"  # é 'locacao' aqui, não 'aluguel' (domain.anuncio)
    with pytest.raises(ValueError):
        IndicadorFipezapCidade(**kwargs)


def test_indicador_fipezap_cidade_locacao_e_aceita():
    kwargs = _base_kwargs_fipezap_cidade()
    kwargs["operacao"] = "locacao"
    kwargs["preco_medio_m2"] = 48.91
    i = IndicadorFipezapCidade(**kwargs)
    assert i.operacao == "locacao"


def test_indicador_fipezap_cidade_preco_negativo_rejeitado():
    kwargs = _base_kwargs_fipezap_cidade()
    kwargs["preco_medio_m2"] = -1.0
    with pytest.raises(ValueError):
        IndicadorFipezapCidade(**kwargs)


def test_indicador_fipezap_cidade_vazia_rejeitada():
    kwargs = _base_kwargs_fipezap_cidade()
    kwargs["cidade"] = ""
    with pytest.raises(ValueError):
        IndicadorFipezapCidade(**kwargs)


def _base_kwargs_fipezap_bairro():
    return dict(
        cidade="Curitiba",
        operacao="venda",
        periodo_referencia=date(2026, 7, 1),
        bairro_nome="BATEL",
        preco_medio_m2=17525.0,
        fonte_id="fipezap",
        snapshot_ref="teste",
    )


def test_indicador_fipezap_bairro_valido_e_aceito():
    i = IndicadorFipezapBairro(**_base_kwargs_fipezap_bairro())
    assert i.territorio_id is None
    assert i.variacao_12m is None


def test_indicador_fipezap_bairro_nome_vazio_rejeitado():
    kwargs = _base_kwargs_fipezap_bairro()
    kwargs["bairro_nome"] = ""
    with pytest.raises(ValueError):
        IndicadorFipezapBairro(**kwargs)


def test_indicador_fipezap_bairro_operacao_invalida_rejeitada():
    kwargs = _base_kwargs_fipezap_bairro()
    kwargs["operacao"] = "compra"
    with pytest.raises(ValueError):
        IndicadorFipezapBairro(**kwargs)


def test_indicador_fipezap_bairro_nome_truncado_e_aceito():
    # achado real do checkpoint 12b: a Fipe as vezes trunca nome de bairro
    # longo com "…" no relatorio - o dataclass aceita o texto como veio,
    # resolucao de territorio_id fica a cargo do parsing (melhor esforco).
    kwargs = _base_kwargs_fipezap_bairro()
    kwargs["bairro_nome"] = "CIDADE INDUSTRIAL DE…"
    i = IndicadorFipezapBairro(**kwargs)
    assert i.bairro_nome == "CIDADE INDUSTRIAL DE…"
    assert i.territorio_id is None
