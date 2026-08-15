from infrastructure.connectors.geocuritiba_cadastro.lote_connector import (
    LoteCadastralConnector,
)

RING = [[670000, 7183000], [670010, 7183010], [670020, 7183000], [670000, 7183000]]


def _feature(objectid: int, ind_fiscal="12345678", nm_bairro="CENTRO", com_geometria=True):
    return {
        "attributes": {
            "objectid": objectid,
            "gtm_ind_fiscal": ind_fiscal,
            "gtm_insc_imob": "0100070144",
            "gtm_mtr_area_terreno": 300.5,
            "gtm_nm_bairro": nm_bairro,
            "gtm_sigla_zoneamento": "ZR2",
        },
        "geometry": {"rings": [RING]} if com_geometria else {"rings": []},
    }


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, total_features=5, page_size=2):
        self.offsets_requisitados = []
        self._total_features = total_features
        self._page_size = page_size

    def get(self, url, params=None, timeout=None):
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


def test_fetch_pagina_e_grava_jsonl_em_disco(tmp_path):
    fake_session = FakeSession(total_features=5, page_size=2)
    connector = LoteCadastralConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo["total"] == 5
    assert fake_session.offsets_requisitados == [0, 2, 4]
    linhas = open(snapshot.conteudo["path"], encoding="utf-8").readlines()
    assert len(linhas) == 5


def test_normalize_produz_um_registro_por_feature_e_resolve_territorio():
    connector = LoteCadastralConnector()
    from datetime import datetime, timezone

    from infrastructure.connectors.base import RawSnapshot

    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "raw.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_feature(1, nm_bairro="CENTRO")) + "\n")
            f.write(json.dumps(_feature(2, nm_bairro="BAIRRO INEXISTENTE")) + "\n")

        snapshot = RawSnapshot(
            fonte_id="geocuritiba_lote_cadastral",
            capturado_em=datetime.now(timezone.utc),
            snapshot_ref=str(path),
            conteudo={"path": str(path), "total": 2},
        )

        registros = list(
            connector.normalize(
                snapshot, territorio_id_por_slug={"centro": "curitiba-bairro-centro"}
            )
        )

    assert len(registros) == 2
    assert registros[0].indicacao_fiscal == "12345678"
    assert registros[0].territorio_id == "curitiba-bairro-centro"
    assert registros[0].sigla_zoneamento == "ZR2"
    assert registros[1].territorio_id is None


def test_normalize_indicacao_fiscal_em_branco_vira_none():
    import json
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path

    from infrastructure.connectors.base import RawSnapshot

    connector = LoteCadastralConnector()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "raw.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(_feature(1, ind_fiscal=" ")) + "\n")

        snapshot = RawSnapshot(
            fonte_id="geocuritiba_lote_cadastral",
            capturado_em=datetime.now(timezone.utc),
            snapshot_ref=str(path),
            conteudo={"path": str(path), "total": 1},
        )
        registros = list(connector.normalize(snapshot))

    assert registros[0].indicacao_fiscal is None
