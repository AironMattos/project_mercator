from datetime import datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.geocuritiba_cadastro.zoneamento_connector import (
    ZoneamentoConnector,
)

RING = [[670000, 7183000], [670010, 7183010], [670020, 7183000], [670000, 7183000]]


def _feature(objectid: int, com_geometria=True):
    return {
        "attributes": {
            "objectid": objectid,
            "cd_zona": "ZR2",
            "sg_zona": "ZR2",
            "nm_zona": "Zona Residencial 2",
            "nm_grupo": "Residencial",
            "legislacao": "Lei 15.511/2019",
            "data_versao": "2019-12-20",
            "data_atualizacao": "2026-01-01",
        },
        "geometry": {"rings": [RING]} if com_geometria else {"rings": []},
    }


def test_normalize_produz_um_registro_por_feature_com_geometria():
    connector = ZoneamentoConnector()
    snapshot = RawSnapshot(
        fonte_id="geocuritiba_zoneamento",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[_feature(1), _feature(2, com_geometria=False)],
    )

    registros = connector.normalize(snapshot)

    assert len(registros) == 1
    assert registros[0]["cd_zona"] == "ZR2"
    assert registros[0]["data_versao"] == "2019-12-20"
    assert registros[0]["territorio_id"] is None
