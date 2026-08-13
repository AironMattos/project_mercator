from shapely.geometry import Point

import routers.busca_raio as busca_raio_router
from infrastructure.geocoding.nominatim import ResultadoNominatim

REF_LAT = -25.435
REF_LON = -49.275


def _mockar_geocodificar(monkeypatch, resultado: ResultadoNominatim):
    monkeypatch.setattr(busca_raio_router, "geocodificar", lambda endereco, session: resultado)


def test_busca_raio_endereco_nao_encontrado_e_404(client, monkeypatch):
    _mockar_geocodificar(monkeypatch, ResultadoNominatim(status="falha", ponto=None))

    resp = client.get("/busca-raio", params={"endereco": "endereço que não existe", "raio_m": 500})

    assert resp.status_code == 404


def test_busca_raio_endereco_ambiguo_e_422(client, monkeypatch):
    _mockar_geocodificar(monkeypatch, ResultadoNominatim(status="ambiguo", ponto=None))

    resp = client.get("/busca-raio", params={"endereco": "rua com dois candidatos", "raio_m": 500})

    assert resp.status_code == 422


def test_busca_raio_conta_alta_e_media_exclui_baixa(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})

    assert resp.status_code == 200
    body = resp.json()
    # perto_alta (50m) e media_sem_categoria (300m) entram; baixa (100m)
    # não entra na contagem principal mas é contado em excluidos.
    assert body["total"] == 2
    assert body["excluidos_baixa_confianca"] == 1
    nomes = {e["nome"] for e in body["estabelecimentos"]}
    assert nomes == {"Restaurante Perto", "MEDIA SEM CATEGORIA LTDA"}
    # ordenado por distância
    assert body["estabelecimentos"][0]["nome"] == "Restaurante Perto"


def test_busca_raio_nao_inclui_estabelecimento_fora_do_raio(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})

    body = resp.json()
    nomes = {e["nome"] for e in body["estabelecimentos"]}
    assert "Muito Longe" not in nomes


def test_busca_raio_com_raio_maior_inclui_o_estabelecimento_longe(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 5000})

    body = resp.json()
    nomes = {e["nome"] for e in body["estabelecimentos"]}
    assert "Muito Longe" in nomes


def test_busca_raio_filtro_categoria(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get(
        "/busca-raio",
        params={"endereco": "R. X, 10, Curitiba", "raio_m": 500, "categoria_id": "bares_restaurantes"},
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["estabelecimentos"][0]["nome"] == "Restaurante Perto"
    assert body["estabelecimentos"][0]["categoria_id"] == "bares_restaurantes"


def test_busca_raio_resposta_inclui_ponto_de_busca(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})

    body = resp.json()
    assert body["ponto_busca"]["lat"] == REF_LAT


def test_busca_raio_estabelecimento_inclui_endereco_de_exibicao(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})

    body = resp.json()
    perto = next(e for e in body["estabelecimentos"] if e["nome"] == "Restaurante Perto")
    assert perto["endereco"] == "R. X, 10 - CENTRO"
    assert body["ponto_busca"]["lon"] == REF_LON
