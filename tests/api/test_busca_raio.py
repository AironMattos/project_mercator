import pytest
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


# --- checkpoint 11d: densidade/turnover/eventos/comparação com bairro -----


def test_busca_raio_densidade_usa_area_do_circulo_de_busca(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})
    body = resp.json()

    # 2 estabelecimentos (perto_alta, media_sem_categoria) num círculo de
    # raio 500m (0,5km) - área = pi*0,5^2 ~= 0,7854 km².
    assert body["total"] == 2
    assert body["densidade_km2"] == pytest.approx(2 / (3.141592653589793 * 0.5**2), rel=1e-6)


def test_busca_raio_sem_evento_no_cenario_zera_aberturas_fechamentos(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    # cenário semeado não tem nenhuma linha em fato_evento_territorial pras
    # entidades da busca por raio - aberturas/fechamentos/saldo devem vir
    # zero (contagem real de zero eventos), não None nem erro.
    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})
    body = resp.json()

    assert body["aberturas"] == 0
    assert body["fechamentos"] == 0
    assert body["saldo"] == 0
    assert body["quebra_categoria"] == []
    assert body["serie_temporal"] == []
    # turnover = (0+0)/2 estabelecimentos ativos = 0.0, um número real (o
    # estoque existe, só não houve evento no período coberto).
    assert body["turnover"] == pytest.approx(0.0)


def test_busca_raio_turnover_none_quando_nenhum_estabelecimento_no_raio(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    # categoria que não bate com nenhum estabelecimento do cenário -> total=0
    resp = client.get(
        "/busca-raio",
        params={"endereco": "R. X, 10, Curitiba", "raio_m": 500, "categoria_id": "saude_clinicas"},
    )
    body = resp.json()

    assert body["total"] == 0
    assert body["turnover"] is None
    assert body["densidade_km2"] == 0.0


def test_busca_raio_compara_com_bairro_majoritario(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get("/busca-raio", params={"endereco": "R. X, 10, Curitiba", "raio_m": 500})
    body = resp.json()

    # Os dois estabelecimentos do raio estão em curitiba-bairro-centro -
    # mesmo bairro/mesmo indicador de aberturas já coberto em
    # test_bairro_resumo_centro_traz_aberturas_confiavel_e_saldo_em_construcao.
    assert body["comparacao_bairro"] is not None
    assert body["comparacao_bairro"]["territorio_id"] == "curitiba-bairro-centro"
    assert body["comparacao_bairro"]["nome"] == "Centro"
    assert body["comparacao_bairro"]["aberturas"]["baseline"] == pytest.approx(0.125)


def test_busca_raio_sem_estabelecimento_no_raio_nao_tem_comparacao_bairro(client, monkeypatch):
    _mockar_geocodificar(
        monkeypatch, ResultadoNominatim(status="sucesso", ponto=Point(REF_LON, REF_LAT))
    )

    resp = client.get(
        "/busca-raio",
        params={"endereco": "R. X, 10, Curitiba", "raio_m": 500, "categoria_id": "saude_clinicas"},
    )
    body = resp.json()

    assert body["comparacao_bairro"] is None
