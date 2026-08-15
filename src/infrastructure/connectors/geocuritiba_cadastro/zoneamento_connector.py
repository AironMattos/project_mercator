from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.geometry import aneis_esri_para_multipolygon

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/"
    "Publico_GeoCuritiba_MapaCadastral/MapServer/36"
)
RAW_DIR = Path("data/raw/geocuritiba_zoneamento")


class ZoneamentoConnector:
    """Conector da camada "Zoneamento Lei 15.511/2019" do GeoCuritiba
    (MapaCadastral, layer 36) - 223 polígonos, confirmado no checkpoint
    11a. Só classificação de zona (código/nome/sigla/legislação) e as
    duas datas de versionamento que a própria camada expõe - sem índice
    construtivo/gabarito/taxa de ocupação, que nenhuma camada pública do
    GeoCuritiba carrega.

    territorio_id fica sempre None aqui: a camada não carrega nome de
    bairro por feição (campos confirmados no checkpoint 11a não incluem
    isso), então não há slug pra casar contra dim_territorio - resolver
    por bairro exigiria um join espacial (centróide dentro do polígono
    de dim_territorio), fora do escopo deste conector.
    """

    fonte_id = "geocuritiba_zoneamento"
    cadencia = "estatica"

    def __init__(
        self,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        self._base_url = base_url
        self._session = session or requests.Session()
        self._raw_dir = raw_dir

    def fetch(self) -> RawSnapshot:
        page_size = self._max_record_count()
        features: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._query_page(offset=offset, count=page_size)
            page_features = page.get("features", [])
            features.extend(page_features)
            if not page.get("exceededTransferLimit") or not page_features:
                break
            offset += len(page_features)

        capturado_em = datetime.now(timezone.utc)
        snapshot_ref = self._salvar_raw(features, capturado_em)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=snapshot_ref,
            conteudo=features,
        )

    def normalize(self, snapshot: RawSnapshot) -> list[dict[str, Any]]:
        """Devolve dicts prontos para o repositório (não um dataclass de
        domínio dedicado - esta camada é classificação/versionamento
        puro, sem regra de negócio associada além do que a fonte já
        expõe; um dataclass aqui só duplicaria os mesmos campos do
        ORM sem validação adicional)."""
        registros = []
        for feature in snapshot.conteudo:
            attrs = feature["attributes"]
            rings = feature.get("geometry", {}).get("rings", [])
            if not rings:
                logger.warning(
                    "feição de zoneamento sem geometria ignorada: objectid=%s",
                    attrs.get("objectid"),
                )
                continue

            registros.append(
                {
                    "geometria": aneis_esri_para_multipolygon(rings),
                    "objectid_fonte": attrs["objectid"],
                    "cd_zona": attrs.get("cd_zona") or "",
                    "sg_zona": attrs.get("sg_zona") or "",
                    "nm_zona": attrs.get("nm_zona") or "",
                    "nm_grupo": attrs.get("nm_grupo"),
                    "legislacao": attrs.get("legislacao"),
                    "data_versao": attrs.get("data_versao"),
                    "data_atualizacao": attrs.get("data_atualizacao"),
                    "territorio_id": None,
                    "fonte_id": self.fonte_id,
                    "snapshot_ref": snapshot.snapshot_ref,
                }
            )
        return registros

    def _max_record_count(self) -> int:
        resp = self._session.get(self._base_url, params={"f": "json"}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("maxRecordCount", 1000)

    def _query_page(self, offset: int, count: int) -> dict[str, Any]:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "orderByFields": "objectid",
            "resultOffset": offset,
            "resultRecordCount": count,
        }
        resp = self._session.get(f"{self._base_url}/query", params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"erro da API GeoCuritiba: {data['error']}")
        return data

    def _salvar_raw(
        self, features: list[dict[str, Any]], capturado_em: datetime
    ) -> str:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        path = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.json"
        path.write_text(
            json.dumps({"features": features}, ensure_ascii=False), encoding="utf-8"
        )
        return str(path)
