from urllib.parse import parse_qs, urlparse

from infrastructure.connectors.geocuritiba_bairro.connector import (
    GeoCuritibaBairroConnector,
)


def _feature(objectid: int) -> dict:
    return {
        "attributes": {"objectid": objectid, "nome": f"BAIRRO {objectid}"},
        "geometry": {"rings": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
    }


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Simula o servidor ArcGIS: maxRecordCount=2 e um total de 5 features,
    forçando o conector a paginar em 3 páginas (2 + 2 + 1).
    """

    def __init__(self):
        self.offsets_requisitados: list[int] = []
        self._total_features = 5
        self._page_size = 2

    def get(self, url: str, params: dict | None = None, timeout: int | None = None):
        params = params or {}
        if url.endswith("/query"):
            offset = int(params["resultOffset"])
            count = int(params["resultRecordCount"])
            self.offsets_requisitados.append(offset)

            restantes = max(0, self._total_features - offset)
            n = min(count, restantes)
            features = [_feature(offset + i) for i in range(n)]
            exceeded = (offset + n) < self._total_features
            return FakeResponse({"features": features, "exceededTransferLimit": exceeded})

        return FakeResponse({"maxRecordCount": self._page_size})


def test_fetch_pagina_ate_esgotar_exceeded_transfer_limit(tmp_path):
    fake_session = FakeSession()
    connector = GeoCuritibaBairroConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert len(snapshot.conteudo) == 5
    assert fake_session.offsets_requisitados == [0, 2, 4]
    objectids = [f["attributes"]["objectid"] for f in snapshot.conteudo]
    assert objectids == [0, 1, 2, 3, 4]


def test_fetch_grava_snapshot_bruto_em_disco(tmp_path):
    fake_session = FakeSession()
    connector = GeoCuritibaBairroConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    from pathlib import Path

    assert Path(snapshot.snapshot_ref).exists()
    assert Path(snapshot.snapshot_ref).parent == tmp_path


def test_normalize_produz_um_territorio_por_feature_com_nome():
    connector = GeoCuritibaBairroConnector()
    from infrastructure.connectors.base import RawSnapshot
    from datetime import datetime, timezone

    snapshot = RawSnapshot(
        fonte_id="geocuritiba_bairro",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[_feature(1), _feature(2)],
    )

    territorios = connector.normalize(snapshot)

    assert len(territorios) == 2
    assert territorios[0].nivel == "bairro"
    assert territorios[0].nome == "BAIRRO 1"
    assert territorios[0].territorio_id == "curitiba-bairro-bairro-1"


def test_normalize_ignora_feature_sem_nome():
    connector = GeoCuritibaBairroConnector()
    from infrastructure.connectors.base import RawSnapshot
    from datetime import datetime, timezone

    feature_sem_nome = {
        "attributes": {"objectid": 99, "nome": None},
        "geometry": {"rings": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
    }
    snapshot = RawSnapshot(
        fonte_id="geocuritiba_bairro",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[_feature(1), feature_sem_nome],
    )

    territorios = connector.normalize(snapshot)

    assert len(territorios) == 1
