from __future__ import annotations


def test_territorios_devolve_geojson_com_os_dois_bairros_semeados(client):
    resp = client.get("/territorios")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    ids = {f["properties"]["territorio_id"] for f in body["features"]}
    assert ids == {"curitiba-bairro-centro", "curitiba-bairro-batel"}
    for feature in body["features"]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "MultiPolygon"
        assert "nome" in feature["properties"]


def test_categorias_devolve_as_duas_categorias_semeadas(client):
    resp = client.get("/categorias")
    assert resp.status_code == 200
    body = resp.json()
    assert {c["categoria_id"] for c in body} == {"bares_restaurantes", "saude_clinicas"}
    por_id = {c["categoria_id"]: c["nome"] for c in body}
    assert por_id["bares_restaurantes"] == "Bares, restaurantes e lanchonetes"


def test_metricas_sem_filtro_agrega_por_bairro_para_o_mapa(client):
    resp = client.get("/metricas/comercio")
    assert resp.status_code == 200
    body = resp.json()
    por_bairro = {item["territorio_id"]: item for item in body}

    centro = por_bairro["curitiba-bairro-centro"]
    assert centro["mes"] is None
    assert centro["categoria_id"] is None
    assert centro["aberturas"] == 5 + 3 + 1
    assert centro["desaparecimentos"] == 2 + 4
    assert centro["saldo"] == centro["aberturas"] - centro["desaparecimentos"]

    batel = por_bairro["curitiba-bairro-batel"]
    assert batel["aberturas"] == 2
    assert batel["desaparecimentos"] == 1
    assert batel["saldo"] == 1


def test_metricas_com_territorio_id_devolve_serie_temporal_por_mes(client):
    resp = client.get("/metricas/comercio", params={"territorio_id": "curitiba-bairro-centro"})
    assert resp.status_code == 200
    body = resp.json()
    por_mes = {item["mes"]: item for item in body}

    assert por_mes["2026-07-01"]["aberturas"] == 5
    assert por_mes["2026-07-01"]["desaparecimentos"] == 2
    assert por_mes["2026-08-01"]["aberturas"] == 3 + 1
    assert por_mes["2026-08-01"]["desaparecimentos"] == 4


def test_metricas_filtra_por_categoria(client):
    resp = client.get(
        "/metricas/comercio",
        params={"territorio_id": "curitiba-bairro-centro", "categoria_id": "saude_clinicas"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["mes"] == "2026-08-01"
    assert body[0]["categoria_id"] == "saude_clinicas"
    assert body[0]["aberturas"] == 1
    assert body[0]["desaparecimentos"] == 0


def test_metricas_filtra_por_intervalo_de_datas(client):
    resp = client.get(
        "/metricas/comercio",
        params={
            "territorio_id": "curitiba-bairro-centro",
            "data_inicio": "2026-08-01",
            "data_fim": "2026-08-31",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["mes"] == "2026-08-01"


def test_metricas_bairro_sem_dado_devolve_lista_vazia(client):
    resp = client.get(
        "/metricas/comercio", params={"territorio_id": "curitiba-bairro-inexistente"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_cors_libera_origem_do_frontend_local(client):
    resp = client.options(
        "/categorias",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
