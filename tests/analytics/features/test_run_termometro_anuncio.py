from datetime import date

from analytics.features.run_termometro_anuncio import _montar_linhas

MES = date(2026, 8, 1)


def test_montar_linhas_estoque_e_novos_da_mesma_celula():
    estoque_rows = [
        {
            "territorio_id": "curitiba-bairro-batel",
            "tipologia": "apartamento",
            "operacao": "aluguel",
            "preco": 3000.0,
            "area_util_m2": 60.0,
        }
    ]
    eventos = {
        ("curitiba-bairro-batel", "apartamento", "aluguel", MES): ["ANUNCIO_PUBLICADO"],
    }
    linhas = _montar_linhas(estoque_rows, eventos, {}, MES)

    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["territorio_id"] == "curitiba-bairro-batel"
    assert linha["estoque"] == 1
    assert linha["novos_anuncios"] == 1
    assert linha["encerrados"] == 0


def test_montar_linhas_celula_so_com_evento_sem_estoque_ativo():
    # o unico anuncio da celula foi encerrado no mes - estoque = 0, mas a
    # celula ainda existe (o encerramento e um fato real que precisa
    # aparecer, nao pode sumir por falta de estoque atual)
    eventos = {
        ("curitiba-bairro-centro", "casa", "venda", MES): ["ANUNCIO_ENCERRADO"],
    }
    linhas = _montar_linhas([], eventos, {}, MES)

    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["estoque"] == 0
    assert linha["novos_anuncios"] == 0
    assert linha["encerrados"] == 1


def test_montar_linhas_reanuncio_conta_como_novo():
    eventos = {
        ("curitiba-bairro-agua-verde", "apartamento", "venda", MES): ["REANUNCIO"],
    }
    linhas = _montar_linhas([], eventos, {}, MES)
    assert linhas[0]["novos_anuncios"] == 1


def test_montar_linhas_amostra_insuficiente_sem_mediana():
    estoque_rows = [
        {
            "territorio_id": "curitiba-bairro-batel",
            "tipologia": "apartamento",
            "operacao": "aluguel",
            "preco": 3000.0,
            "area_util_m2": 60.0,
        }
    ]  # só 1 anúncio, bem abaixo do piso de 30
    linhas = _montar_linhas(estoque_rows, {}, {}, MES)

    linha = linhas[0]
    assert linha["amostra_preco_suficiente"] is False
    assert linha["preco_mediano"] is None
    assert linha["preco_p25"] is None


def test_montar_linhas_amostra_suficiente_calcula_mediana():
    estoque_rows = [
        {
            "territorio_id": "curitiba-bairro-batel",
            "tipologia": "apartamento",
            "operacao": "aluguel",
            "preco": float(1000 + i * 10),
            "area_util_m2": 50.0,
        }
        for i in range(30)
    ]
    linhas = _montar_linhas(estoque_rows, {}, {}, MES)

    linha = linhas[0]
    assert linha["amostra_preco_suficiente"] is True
    assert linha["preco_mediano"] is not None
    assert linha["preco_m2_mediano"] is not None


def test_montar_linhas_novos_por_mil_domicilios_usa_lookup():
    eventos = {
        ("curitiba-bairro-batel", "apartamento", "aluguel", MES): ["ANUNCIO_PUBLICADO"] * 5,
    }
    domicilios = {"curitiba-bairro-batel": 5000}
    linhas = _montar_linhas([], eventos, domicilios, MES)

    linha = linhas[0]
    assert linha["novos_por_mil_domicilios"] == 1.0


def test_montar_linhas_sem_domicilios_fica_none():
    eventos = {
        ("curitiba-bairro-batel", "apartamento", "aluguel", MES): ["ANUNCIO_PUBLICADO"],
    }
    linhas = _montar_linhas([], eventos, {}, MES)
    assert linhas[0]["novos_por_mil_domicilios"] is None


def test_montar_linhas_metricas_historicas_ficam_null():
    estoque_rows = [
        {
            "territorio_id": "curitiba-bairro-batel",
            "tipologia": "apartamento",
            "operacao": "aluguel",
            "preco": 3000.0,
            "area_util_m2": 60.0,
        }
    ]
    linhas = _montar_linhas(estoque_rows, {}, {}, MES)
    linha = linhas[0]
    assert linha["rotacao_oferta"] is None
    assert linha["renovacao"] is None
    assert linha["permanencia_mediana_dias"] is None
    assert linha["pressao_preco_pct_subiu"] is None
    assert linha["quadrante"] is None


def test_montar_linhas_ignora_eventos_de_outros_meses():
    outro_mes = date(2026, 7, 1)
    eventos = {
        ("curitiba-bairro-batel", "apartamento", "aluguel", outro_mes): ["ANUNCIO_PUBLICADO"],
    }
    linhas = _montar_linhas([], eventos, {}, MES)
    assert linhas == []


def test_montar_linhas_territorio_none_nao_quebra():
    estoque_rows = [
        {
            "territorio_id": None,
            "tipologia": "apartamento",
            "operacao": "aluguel",
            "preco": 3000.0,
            "area_util_m2": 60.0,
        }
    ]
    linhas = _montar_linhas(estoque_rows, {}, {}, MES)
    assert linhas[0]["territorio_id"] is None
    assert linhas[0]["novos_por_mil_domicilios"] is None
