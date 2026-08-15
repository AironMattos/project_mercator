from datetime import datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.ippuc_pgv.connector import IppucPgvConnector

# Anel real dentro do envelope de Curitiba em EPSG:31982 (mesmo usado nos
# testes de geocuritiba_bairro).
RING = [[670000, 7183000], [670010, 7183010], [670020, 7183000], [670000, 7183000]]


def _feature(objectid: int, nm_bairro: str = "CENTRO", vukt: float = 1200.0) -> dict:
    return {
        "attributes": {
            "objectid": objectid,
            "chave": f"CHAVE-{objectid}",
            "nm_bairro": nm_bairro,
            "vukt": vukt,
        },
        "geometry": {"rings": [RING]},
    }


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, nome_layer="Microrregião (PGV 2025)", total_features=3, page_size=2):
        self.offsets_requisitados: list[int] = []
        self._nome_layer = nome_layer
        self._total_features = total_features
        self._page_size = page_size

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

        return FakeResponse({"name": self._nome_layer, "maxRecordCount": self._page_size})


def test_fetch_pagina_ate_esgotar_exceeded_transfer_limit(tmp_path):
    fake_session = FakeSession(total_features=5, page_size=2)
    connector = IppucPgvConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert len(snapshot.conteudo["features"]) == 5
    assert fake_session.offsets_requisitados == [0, 2, 4]
    assert snapshot.conteudo["nome_layer"] == "Microrregião (PGV 2025)"


def test_normalize_produz_valor_referencia_com_vigencia_do_nome_da_layer():
    connector = IppucPgvConnector()
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={"features": [_feature(1, vukt=1500.0)], "nome_layer": "Microrregião (PGV 2025)"},
    )

    valores = connector.normalize(snapshot)

    assert len(valores) == 1
    v = valores[0]
    assert v.tipo_valor == "venal"
    assert v.componente == "terreno"
    assert v.valor_m2 == 1500.0
    assert v.vigencia_inicio.year == 2025
    assert v.fonte_id == "ippuc_pgv"
    assert v.objectid_fonte == 1


def test_normalize_preserva_objectid_fonte_para_dedup_por_registro():
    connector = IppucPgvConnector()
    # Duas microrregiões distintas do mesmo bairro - devem virar dois
    # registros normalizados, não colapsar em um só (bug real corrigido
    # no checkpoint 11c).
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "features": [
                _feature(1, nm_bairro="CENTRO", vukt=1200.0),
                _feature(2, nm_bairro="CENTRO", vukt=1400.0),
            ],
            "nome_layer": "Microrregião (PGV 2025)",
        },
    )

    valores = connector.normalize(snapshot)

    assert len(valores) == 2
    assert {v.objectid_fonte for v in valores} == {1, 2}


def test_normalize_resolve_territorio_id_por_slug_de_bairro():
    connector = IppucPgvConnector()
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "features": [_feature(1, nm_bairro="CAPÃO DA IMBUIA")],
            "nome_layer": "Microrregião (PGV 2025)",
        },
    )

    valores = connector.normalize(
        snapshot, territorio_id_por_slug={"capao-da-imbuia": "curitiba-bairro-capao-da-imbuia"}
    )

    assert valores[0].territorio_id == "curitiba-bairro-capao-da-imbuia"


def test_normalize_bairro_sem_correspondencia_fica_sem_territorio_id():
    connector = IppucPgvConnector()
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "features": [_feature(1, nm_bairro="BAIRRO INEXISTENTE")],
            "nome_layer": "Microrregião (PGV 2025)",
        },
    )

    valores = connector.normalize(snapshot, territorio_id_por_slug={})

    assert valores[0].territorio_id is None


def test_normalize_ignora_feature_sem_vukt():
    connector = IppucPgvConnector()
    feature_sem_vukt = _feature(1)
    feature_sem_vukt["attributes"]["vukt"] = None
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={"features": [feature_sem_vukt], "nome_layer": "Microrregião (PGV 2025)"},
    )

    valores = connector.normalize(snapshot)

    assert valores == []


def test_vigencia_cai_no_ano_corrente_quando_nome_da_layer_nao_tem_ano():
    connector = IppucPgvConnector()
    snapshot = RawSnapshot(
        fonte_id="ippuc_pgv",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={"features": [_feature(1)], "nome_layer": "Microrregião (sem ano)"},
    )

    valores = connector.normalize(snapshot)

    assert valores[0].vigencia_inicio.year == datetime.now(timezone.utc).year
