from infrastructure.geocoding.nominatim import geocodificar, montar_endereco


class FakeJsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.ultima_url_params = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.ultima_url_params = params
        return FakeJsonResponse(self._payload)


def test_montar_endereco_monta_string_completa():
    endereco = montar_endereco("R. CONDE DOS ARCOS", "996", "LINDÓIA", "81010120")

    assert endereco == "R. CONDE DOS ARCOS, 996, LINDÓIA, 81010-120, Curitiba, PR, Brasil"


def test_montar_endereco_omite_campos_vazios():
    endereco = montar_endereco("R. X", None, None, None)

    assert endereco == "R. X, Curitiba, PR, Brasil"


def test_geocodificar_sem_resultado_e_falha():
    session = FakeSession([])

    resultado = geocodificar("endereço inexistente, Curitiba, PR, Brasil", session)

    assert resultado.status == "falha"
    assert resultado.ponto is None


def test_geocodificar_um_candidato_e_sucesso():
    session = FakeSession([{"lat": "-25.4799", "lon": "-49.2788", "importance": 0.5, "type": "house"}])

    resultado = geocodificar("R. X, 10, Curitiba, PR, Brasil", session)

    assert resultado.status == "sucesso"
    assert resultado.ponto.x == -49.2788
    assert resultado.ponto.y == -25.4799


def test_geocodificar_dois_candidatos_proximos_e_sucesso_usa_o_primeiro():
    session = FakeSession(
        [
            {"lat": "-25.4799", "lon": "-49.2788", "importance": 0.6, "type": "house"},
            {"lat": "-25.47995", "lon": "-49.27885", "importance": 0.4, "type": "house"},
        ]
    )

    resultado = geocodificar("R. X, 10, Curitiba, PR, Brasil", session)

    assert resultado.status == "sucesso"
    assert resultado.ponto.y == -25.4799


def test_geocodificar_dois_candidatos_distantes_e_ambiguo():
    session = FakeSession(
        [
            {"lat": "-25.4799", "lon": "-49.2788", "importance": 0.6, "type": "house"},
            {"lat": "-25.5500", "lon": "-49.3500", "importance": 0.55, "type": "house"},
        ]
    )

    resultado = geocodificar("R. X, 10, Curitiba, PR, Brasil", session)

    assert resultado.status == "ambiguo"
    assert resultado.ponto is None
