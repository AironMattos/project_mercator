def test_construcao_agregado_por_bairro_separa_alvara_de_cvco(client):
    resp = client.get("/imoveis/construcao")
    assert resp.status_code == 200
    itens = {i["territorio_id"]: i for i in resp.json()}

    centro = itens["curitiba-bairro-centro"]
    assert centro["mes"] is None
    assert centro["alvaras_aprovados"] == 4
    assert centro["area_licenciada_m2"] == 650.5
    assert centro["cvcos_concluidos"] == 3
    assert centro["area_concluida_m2"] == 315.25
    # Mediana de [59, 73, 59] dias (Jan1->Mar1, Jan1->Mar15, Fev1->Abr1).
    assert centro["defasagem_mediana_dias"] == 59
    assert centro["pares_alvara_cvco"] == 3
    assert centro["motivo_indisponivel_defasagem"] is None


def test_construcao_agregado_piso_minimo_de_pares_para_defasagem(client):
    resp = client.get("/imoveis/construcao")
    itens = {i["territorio_id"]: i for i in resp.json()}

    batel = itens["curitiba-bairro-batel"]
    assert batel["pares_alvara_cvco"] == 1
    assert batel["defasagem_mediana_dias"] is None
    assert batel["motivo_indisponivel_defasagem"] == "historico_insuficiente"


def test_construcao_serie_mensal_por_bairro_sem_defasagem(client):
    resp = client.get("/imoveis/construcao", params={"territorio_id": "curitiba-bairro-centro"})
    assert resp.status_code == 200
    por_mes = {i["mes"]: i for i in resp.json()}

    assert por_mes["2026-01-01"]["alvaras_aprovados"] == 2
    assert por_mes["2026-01-01"]["area_licenciada_m2"] == 300.5
    assert por_mes["2026-01-01"]["cvcos_concluidos"] == 0
    assert por_mes["2026-03-01"]["cvcos_concluidos"] == 2
    assert por_mes["2026-03-01"]["area_concluida_m2"] == 270.25

    for linha in por_mes.values():
        assert linha["defasagem_mediana_dias"] is None
        assert linha["motivo_indisponivel_defasagem"] == "nao_aplicavel_no_modo_serie_mensal"


def test_valor_referencia_mediana_por_bairro_sem_variacao(client):
    resp = client.get("/imoveis/valor-referencia")
    assert resp.status_code == 200
    itens = {i["territorio_id"]: i for i in resp.json()}

    centro = itens["curitiba-bairro-centro"]
    assert centro["valor_m2_mediano"] == 1100.0
    assert centro["tipo_valor"] == "venal"
    assert centro["componente"] == "terreno"
    assert centro["quantidade_registros"] == 2
    assert centro["fonte_id"] == "ippuc_pgv"
    assert centro["vigencia_inicio"] == "2025-01-01"
    # Trava metodológica "PGV não é série temporal" - nunca uma
    # variação/tendência no corpo da resposta.
    assert "variacao_pct" not in resp.json()[0]
    assert "tendencia" not in resp.json()[0]
    # BATEL não tem PGV nesta seed - não aparece na resposta (nunca
    # inventado como zero).
    assert "curitiba-bairro-batel" not in itens


def test_valor_referencia_filtra_por_territorio(client):
    resp = client.get("/imoveis/valor-referencia", params={"territorio_id": "curitiba-bairro-centro"})
    itens = resp.json()
    assert len(itens) == 1
    assert itens[0]["territorio_id"] == "curitiba-bairro-centro"


def test_zoneamento_geojson_com_data_versao(client):
    resp = client.get("/imoveis/zoneamento")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    props = body["features"][0]["properties"]
    assert props["sg_zona"] == "ZR-1"
    assert props["data_versao"] == "2020-01"
    assert body["features"][0]["geometry"]["type"] == "MultiPolygon"


def test_contexto_bcb_pega_mes_mais_recente_com_uf_declarada(client):
    resp = client.get("/imoveis/contexto")
    assert resp.status_code == 200
    bcb = resp.json()["bcb"]

    assert bcb["granularidade"] == "uf"
    assert bcb["uf"] == "PR"
    assert bcb["periodo_referencia"] == "2026-07-01"
    indicadores = {i["indicador"]: i for i in bcb["indicadores"]}
    assert set(indicadores) == {"imoveis_valor_avaliacao", "imoveis_valor_compra", "imoveis_dormitorio_2"}
    assert indicadores["imoveis_valor_avaliacao"]["leitura"] == 300000.0
    assert indicadores["imoveis_valor_avaliacao"]["tipo_valor"] == "avaliacao"


def test_contexto_bcb_valor_compra_vira_tipo_valor_transacao(client):
    resp = client.get("/imoveis/contexto")
    indicadores = {i["indicador"]: i for i in resp.json()["bcb"]["indicadores"]}
    assert indicadores["imoveis_valor_compra"]["tipo_valor"] == "transacao"


def test_contexto_bcb_contagem_nao_carrega_tipo_valor(client):
    resp = client.get("/imoveis/contexto")
    indicadores = {i["indicador"]: i for i in resp.json()["bcb"]["indicadores"]}
    assert indicadores["imoveis_dormitorio_2"]["categoria"] == "contagem"
    assert indicadores["imoveis_dormitorio_2"]["tipo_valor"] is None


def test_contexto_quintoandar_granularidade_cidade(client):
    resp = client.get("/imoveis/contexto")
    quintoandar = resp.json()["quintoandar"]

    assert quintoandar["granularidade"] == "cidade"
    assert quintoandar["cidade"] == "Curitiba"
    assert quintoandar["periodo_referencia"] == "2026-07-01"
    assert len(quintoandar["segmentos"]) == 1
    assert quintoandar["segmentos"][0]["aluguel_m2"] == 42.0


def test_contexto_censo_agrega_setores_por_bairro(client):
    resp = client.get("/imoveis/contexto")
    censo = resp.json()["censo"]

    assert censo["granularidade"] == "setor_censitario_agregado_por_bairro"
    assert censo["ano_referencia"] == 2022
    bairros = {b["territorio_id"]: b for b in censo["bairros"]}
    centro = bairros["curitiba-bairro-centro"]
    assert centro["populacao_total"] == 1800
    assert centro["domicilios_total"] == 700
    assert centro["setores_agregados"] == 2
    assert centro["densidade_domicilios_km2"] == 700.0
    # BATEL não tem setor censitário seedado.
    assert "curitiba-bairro-batel" not in bairros


def test_qualidade_dados_conta_resolucao_de_territorio_e_fontes(client):
    resp = client.get("/imoveis/qualidade-dados")
    assert resp.status_code == 200
    body = resp.json()

    assert body["alvaras"]["total"] == 5
    assert body["alvaras"]["com_territorio_resolvido"] == 5
    assert body["alvaras"]["pct_territorio_resolvido"] == 100.0
    assert body["cvcos"]["total"] == 4
    assert body["lote_cadastral"] == {"total": 2, "sem_geometria": 1, "sem_territorio": 1}
    assert body["pgv_vigencia_inicio"] == "2025-01-01"
    assert body["pgv_bairros_cobertos"] == 1
    assert body["pgv_total_registros"] == 2
    assert set(body["ultima_atualizacao_por_fonte"]) == {
        "smu_alvara_construcao",
        "smu_cvco",
        "ippuc_pgv",
        "geocuritiba_lote_cadastral",
        "geocuritiba_zoneamento",
        "bcb_mercado_imobiliario",
        "quintoandar_indice_aluguel",
        "ibge_censo_setor",
    }
    # Nenhum pipeline_run foi seedado - nenhuma fonte tem "última
    # atualização" ainda, nunca inventada.
    assert all(v is None for v in body["ultima_atualizacao_por_fonte"].values())
