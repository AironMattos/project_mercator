from infrastructure.connectors.ibge_cnae.connector import IbgeCnaeConnector

ITEM_EXEMPLO = {
    "id": "9602501",
    "descricao": "CABELEIREIROS, MANICURE E PEDICURE",
    "classe": {
        "id": "96025",
        "descricao": "...",
        "grupo": {
            "id": "960",
            "descricao": "...",
            "divisao": {
                "id": "96",
                "descricao": "...",
                "secao": {"id": "S", "descricao": "..."},
            },
        },
    },
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self._payload = payload

    def get(self, url, timeout=None):
        return FakeResponse(self._payload)


def test_fetch_salva_snapshot_bruto(tmp_path):
    session = FakeSession([ITEM_EXEMPLO])
    connector = IbgeCnaeConnector(session=session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo == [ITEM_EXEMPLO]
    from pathlib import Path

    assert Path(snapshot.snapshot_ref).exists()


def test_normalize_extrai_hierarquia_completa(tmp_path):
    session = FakeSession([ITEM_EXEMPLO])
    connector = IbgeCnaeConnector(session=session, raw_dir=tmp_path)
    snapshot = connector.fetch()

    cnaes = connector.normalize(snapshot)

    assert len(cnaes) == 1
    c = cnaes[0]
    assert c.codigo_cnae == "9602501"
    assert c.descricao == "CABELEIREIROS, MANICURE E PEDICURE"
    assert c.secao == "S"
    assert c.divisao == "96"
    assert c.grupo == "960"
    assert c.classe == "96025"
