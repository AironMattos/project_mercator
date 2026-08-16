import pytest

from analytics.features.pressao_especulativa import (
    MOTIVO_AMOSTRA_INSUFICIENTE,
    MOTIVO_SEM_DADO,
    avaliar_preco_sem_contrapartida_fisica,
    calcular_concentracao_ofertante,
    calcular_descolamento_pedido_contratado,
    calcular_oferta_por_domicilio_vago,
    calcular_taxa_reanuncio,
)


def test_taxa_reanuncio_calcula_taxa_e_mediana_so_dos_incrementos_positivos():
    resultado = calcular_taxa_reanuncio(
        n_reanuncios=10, n_encerrados=40, variacoes_incremento_pct=[0.05, 0.10, -0.02, 0.20]
    )
    assert resultado.taxa == pytest.approx(0.25)
    assert resultado.mediana_incremento_pct == pytest.approx(0.10)
    assert resultado.motivo_indisponivel is None


def test_taxa_reanuncio_sem_encerrados_fica_none():
    resultado = calcular_taxa_reanuncio(n_reanuncios=0, n_encerrados=0, variacoes_incremento_pct=[])
    assert resultado.taxa is None
    assert resultado.mediana_incremento_pct is None
    assert resultado.motivo_indisponivel == MOTIVO_SEM_DADO


def test_taxa_reanuncio_sem_incremento_positivo_mediana_fica_none():
    resultado = calcular_taxa_reanuncio(
        n_reanuncios=5, n_encerrados=20, variacoes_incremento_pct=[-0.05, -0.10]
    )
    assert resultado.taxa == pytest.approx(0.25)
    assert resultado.mediana_incremento_pct is None


def test_oferta_por_domicilio_vago():
    resultado = calcular_oferta_por_domicilio_vago(estoque_anuncios=50, domicilios_vagos=200)
    assert resultado.razao == pytest.approx(0.25)
    assert resultado.motivo_indisponivel is None


def test_oferta_por_domicilio_vago_sem_domicilios_fica_none():
    resultado = calcular_oferta_por_domicilio_vago(estoque_anuncios=50, domicilios_vagos=None)
    assert resultado.razao is None
    assert resultado.motivo_indisponivel == MOTIVO_SEM_DADO
    resultado_zero = calcular_oferta_por_domicilio_vago(estoque_anuncios=50, domicilios_vagos=0)
    assert resultado_zero.razao is None


def test_concentracao_ofertante_amostra_suficiente():
    contagens = [20, 10, 5, 5, 5, 5]  # total 50, top5 = 45
    resultado = calcular_concentracao_ofertante(contagens)
    assert resultado.motivo_indisponivel is None
    assert resultado.pct_top5_ofertantes == pytest.approx(45 / 50)
    assert resultado.n_ofertantes_distintos == 6
    assert resultado.n_anuncios_com_ofertante_conhecido == 50


def test_concentracao_ofertante_amostra_insuficiente():
    resultado = calcular_concentracao_ofertante([5, 3])
    assert resultado.motivo_indisponivel == MOTIVO_AMOSTRA_INSUFICIENTE
    assert resultado.pct_top5_ofertantes is None


def test_concentracao_ofertante_lista_vazia():
    resultado = calcular_concentracao_ofertante([])
    assert resultado.motivo_indisponivel == MOTIVO_AMOSTRA_INSUFICIENTE
    assert resultado.n_ofertantes_distintos == 0


def test_descolamento_pedido_contratado():
    resultado = calcular_descolamento_pedido_contratado(
        preco_pedido_mediano_m2=60.0, indice_contratado_m2=50.0
    )
    assert resultado.razao == pytest.approx(1.2)
    assert resultado.motivo_indisponivel is None


def test_descolamento_pedido_contratado_sem_indice_fica_none():
    resultado = calcular_descolamento_pedido_contratado(60.0, None)
    assert resultado.razao is None
    assert resultado.motivo_indisponivel == MOTIVO_SEM_DADO


def test_descolamento_pedido_contratado_sem_preco_pedido_fica_none():
    resultado = calcular_descolamento_pedido_contratado(None, 50.0)
    assert resultado.razao is None


def test_preco_sem_contrapartida_sobe_e_sem_alvara():
    resultado = avaliar_preco_sem_contrapartida_fisica(
        variacao_preco_pct=0.10, houve_contrapartida=False
    )
    assert resultado.preco_subiu_sem_contrapartida is True
    assert resultado.motivo_indisponivel is None


def test_preco_sem_contrapartida_sobe_mas_com_alvara():
    resultado = avaliar_preco_sem_contrapartida_fisica(
        variacao_preco_pct=0.10, houve_contrapartida=True
    )
    assert resultado.preco_subiu_sem_contrapartida is False


def test_preco_sem_contrapartida_nao_sobe():
    resultado = avaliar_preco_sem_contrapartida_fisica(
        variacao_preco_pct=-0.05, houve_contrapartida=False
    )
    assert resultado.preco_subiu_sem_contrapartida is False


def test_preco_sem_contrapartida_sem_variacao_fica_indisponivel():
    resultado = avaliar_preco_sem_contrapartida_fisica(
        variacao_preco_pct=None, houve_contrapartida=False
    )
    assert resultado.preco_subiu_sem_contrapartida is None
    assert resultado.motivo_indisponivel == MOTIVO_AMOSTRA_INSUFICIENTE
