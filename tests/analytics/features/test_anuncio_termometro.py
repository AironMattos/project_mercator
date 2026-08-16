import pytest

from analytics.features.anuncio_termometro import (
    AJUSTANDO,
    AQUECENDO,
    DESACELERANDO_QUADRANTE,
    OTIMISMO_NAO_VALIDADO,
    PISO_MINIMO_AMOSTRA,
    amostra_e_suficiente,
    calcular_estatistica_preco,
    calcular_novos_por_mil_domicilios,
    calcular_permanencia_mediana,
    calcular_pressao_preco,
    calcular_renovacao,
    calcular_rotacao_oferta,
    classificar_quadrante_aquecimento,
    contar_novos_anuncios,
)


def test_amostra_e_suficiente():
    assert amostra_e_suficiente(PISO_MINIMO_AMOSTRA) is True
    assert amostra_e_suficiente(PISO_MINIMO_AMOSTRA - 1) is False


def test_contar_novos_anuncios_soma_publicado_e_reanuncio():
    tipos = ["ANUNCIO_PUBLICADO", "REANUNCIO", "ANUNCIO_PUBLICADO", "PRECO_ALTERADO", "ANUNCIO_ENCERRADO"]
    assert contar_novos_anuncios(tipos) == 3


def test_contar_novos_anuncios_lista_vazia():
    assert contar_novos_anuncios([]) == 0


def test_novos_por_mil_domicilios():
    assert calcular_novos_por_mil_domicilios(20, 10000) == pytest.approx(2.0)


def test_novos_por_mil_domicilios_sem_domicilios_fica_none():
    assert calcular_novos_por_mil_domicilios(20, None) is None
    assert calcular_novos_por_mil_domicilios(20, 0) is None


def test_rotacao_oferta():
    assert calcular_rotacao_oferta(encerrados_no_mes=10, estoque_inicio_mes=100) == pytest.approx(0.1)


def test_rotacao_oferta_sem_estoque_inicial_fica_none():
    assert calcular_rotacao_oferta(10, None) is None
    assert calcular_rotacao_oferta(10, 0) is None


def test_renovacao():
    assert calcular_renovacao(novos_anuncios=5, encerrados_no_mes=5, estoque_medio=100) == pytest.approx(0.1)


def test_renovacao_sem_estoque_medio_fica_none():
    assert calcular_renovacao(5, 5, None) is None
    assert calcular_renovacao(5, 5, 0) is None


def test_permanencia_mediana():
    assert calcular_permanencia_mediana([10, 20, 30]) == 20


def test_permanencia_mediana_lista_vazia_fica_none():
    assert calcular_permanencia_mediana([]) is None


def test_pressao_preco_amostra_suficiente():
    variacoes = [0.05] * 20 + [-0.03] * 10 + [0.0] * 5  # 35 no total
    resultado = calcular_pressao_preco(variacoes)
    assert resultado.motivo_indisponivel is None
    assert resultado.n == 35
    assert resultado.pct_subiu == pytest.approx(20 / 35)
    assert resultado.pct_desceu == pytest.approx(10 / 35)
    assert resultado.variacao_mediana_pct is not None


def test_pressao_preco_amostra_insuficiente():
    resultado = calcular_pressao_preco([0.05] * (PISO_MINIMO_AMOSTRA - 1))
    assert resultado.motivo_indisponivel == "amostra_insuficiente"
    assert resultado.pct_subiu is None
    assert resultado.pct_desceu is None
    assert resultado.variacao_mediana_pct is None


def test_estatistica_preco_amostra_suficiente():
    precos = list(range(1, PISO_MINIMO_AMOSTRA + 1))  # 1..30
    resultado = calcular_estatistica_preco([float(p) for p in precos])
    assert resultado.motivo_indisponivel is None
    assert resultado.n == PISO_MINIMO_AMOSTRA
    assert resultado.mediana == pytest.approx(15.5)
    assert resultado.p25 < resultado.mediana < resultado.p75


def test_estatistica_preco_amostra_insuficiente():
    resultado = calcular_estatistica_preco([100.0, 200.0])
    assert resultado.motivo_indisponivel == "amostra_insuficiente"
    assert resultado.mediana is None
    assert resultado.p25 is None
    assert resultado.p75 is None
    assert resultado.n == 2


def test_quadrante_aquecendo_preco_sobe_permanencia_cai():
    assert classificar_quadrante_aquecimento(0.05, -0.10) == AQUECENDO


def test_quadrante_otimismo_nao_validado_preco_sobe_permanencia_sobe():
    assert classificar_quadrante_aquecimento(0.05, 0.10) == OTIMISMO_NAO_VALIDADO


def test_quadrante_ajustando_preco_cai_permanencia_cai():
    assert classificar_quadrante_aquecimento(-0.05, -0.10) == AJUSTANDO


def test_quadrante_desacelerando_preco_cai_permanencia_sobe():
    assert classificar_quadrante_aquecimento(-0.05, 0.10) == DESACELERANDO_QUADRANTE


def test_quadrante_sem_preco_fica_none():
    assert classificar_quadrante_aquecimento(None, 0.10) is None


def test_quadrante_sem_permanencia_fica_none():
    assert classificar_quadrante_aquecimento(0.05, None) is None


def test_quadrante_sem_nenhum_dos_dois_fica_none():
    assert classificar_quadrante_aquecimento(None, None) is None
