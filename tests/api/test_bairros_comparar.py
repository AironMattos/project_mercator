from __future__ import annotations

# Cenário do conftest.py: dois bairros (curitiba-bairro-centro,
# curitiba-bairro-batel).


def test_comparar_dois_bairros_traz_o_mesmo_formato_do_resumo_individual(client):
    resp = client.get(
        "/bairros/comparar", params={"ids": "curitiba-bairro-centro,curitiba-bairro-batel"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["itens"]) == 2
    territorios = {item["territorio_id"] for item in body["itens"]}
    assert territorios == {"curitiba-bairro-centro", "curitiba-bairro-batel"}

    centro = next(i for i in body["itens"] if i["territorio_id"] == "curitiba-bairro-centro")
    resp_individual = client.get("/bairros/curitiba-bairro-centro/resumo")
    assert centro == resp_individual.json()


def test_comparar_menos_de_dois_bairros_e_422(client):
    resp = client.get("/bairros/comparar", params={"ids": "curitiba-bairro-centro"})
    assert resp.status_code == 422


def test_comparar_mais_de_quatro_bairros_e_422(client):
    ids = ",".join(f"bairro-{i}" for i in range(5))
    resp = client.get("/bairros/comparar", params={"ids": ids})
    assert resp.status_code == 422


def test_comparar_bairro_inexistente_e_404(client):
    resp = client.get(
        "/bairros/comparar", params={"ids": "curitiba-bairro-centro,bairro-que-nao-existe"}
    )
    assert resp.status_code == 404
    assert "bairro-que-nao-existe" in resp.json()["detail"]
