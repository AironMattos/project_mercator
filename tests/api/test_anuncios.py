import pytest


def test_termometro_exige_operacao(client):
    resp = client.get("/anuncios/termometro")
    assert resp.status_code == 422


def test_termometro_operacao_invalida_e_422(client):
    resp = client.get("/anuncios/termometro", params={"operacao": "trocar"})
    assert resp.status_code == 422


def test_termometro_aluguel_traz_batel_com_mediana(client):
    resp = client.get("/anuncios/termometro", params={"operacao": "aluguel"})
    assert resp.status_code == 200
    linhas = resp.json()
    batel = next(l for l in linhas if l["territorio_id"] == "curitiba-bairro-batel")
    assert batel["estoque"] == 30
    assert batel["preco_mediano"] == pytest.approx(1145.0)
    assert batel["preco_p25"] is not None
    assert batel["preco_p75"] is not None
    # amostra de 30 == piso mínimo (seção 2.2) - mediana calculada
    assert batel["amostra_preco_suficiente"] is True


def test_termometro_quadrante_e_none_com_motivo(client):
    resp = client.get("/anuncios/termometro", params={"operacao": "aluguel"})
    linhas = resp.json()
    batel = next(l for l in linhas if l["territorio_id"] == "curitiba-bairro-batel")
    assert batel["quadrante"] is None
    assert batel["motivo_indisponivel_quadrante"] == "historico_insuficiente"


def test_termometro_venda_traz_centro_com_amostra_insuficiente(client):
    resp = client.get("/anuncios/termometro", params={"operacao": "venda"})
    linhas = resp.json()
    centro = next(l for l in linhas if l["territorio_id"] == "curitiba-bairro-centro")
    assert centro["estoque"] == 2
    # 2 anúncios < piso mínimo de 30 (seção 2.2) - mediana fica None,
    # nunca um número frágil sobre amostra tão pequena
    assert centro["preco_mediano"] is None
    assert centro["amostra_preco_suficiente"] is False


def test_termometro_filtra_por_tipologia(client):
    resp = client.get(
        "/anuncios/termometro", params={"operacao": "aluguel", "tipologia": "nao_classificado"}
    )
    linhas = resp.json()
    assert all(l["territorio_id"] != "curitiba-bairro-batel" for l in linhas)


def test_bairro_resumo_traz_estoque_e_contexto_imobiliario(client):
    resp = client.get(
        "/anuncios/bairros/curitiba-bairro-batel/resumo", params={"operacao": "aluguel"}
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["estoque"] == 30
    assert corpo["preco_mediano"] == pytest.approx(1145.0)
    assert corpo["variacao_preco_12m_pct"] is None
    assert corpo["motivo_indisponivel_variacao"] == "historico_insuficiente"
    assert corpo["quadrante"] is None


def test_bairro_resumo_bairro_sem_estoque_devolve_zero_nao_erro(client):
    resp = client.get(
        "/anuncios/bairros/curitiba-bairro-centro/resumo", params={"operacao": "aluguel"}
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["estoque"] == 0
    assert corpo["preco_mediano"] is None


def test_procedencia_traz_as_duas_fontes_separadas(client):
    resp = client.get("/anuncios/procedencia")
    assert resp.status_code == 200
    corpo = resp.json()
    fontes = {item["fonte_id"] for item in corpo}
    assert fontes == {"apolar_anuncios", "chavesnamao_anuncios"}

    apolar = next(item for item in corpo if item["fonte_id"] == "apolar_anuncios")
    assert apolar["total_observado_no_periodo"] == 30
    assert apolar["taxa_classificacao_tipologia"] == pytest.approx(1.0)
    assert apolar["taxa_resolucao_bairro"] == pytest.approx(1.0)
    assert apolar["cadencia"] == "semanal"
    assert apolar["ultima_atualizacao"] is not None
