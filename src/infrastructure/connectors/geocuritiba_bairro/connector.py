from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from domain.territory import Territorio
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.geocuritiba_bairro.geometry import (
    aneis_esri_para_multipolygon,
)
from infrastructure.connectors.text import slugify

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/"
    "Publico_GeoCuritiba_MapaCadastral/MapServer/2"
)
RAW_DIR = Path("data/raw/geocuritiba_bairro")


class GeoCuritibaBairroConnector:
    """Conector da camada Bairro do GeoCuritiba (IPPUC), servida via ArcGIS
    REST. Fonte estática de referência - limites de bairro não mudam com
    cadência mensal como as demais fontes do projeto.
    """

    fonte_id = "geocuritiba_bairro"
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

    def normalize(self, snapshot: RawSnapshot) -> list[Territorio]:
        territorios = []
        for feature in snapshot.conteudo:
            attrs = feature["attributes"]
            rings = feature.get("geometry", {}).get("rings", [])
            nome = (attrs.get("nome") or "").strip()
            if not nome:
                logger.warning(
                    "feature sem nome ignorada: objectid=%s", attrs.get("objectid")
                )
                continue

            geometria = aneis_esri_para_multipolygon(rings) if rings else None
            territorios.append(
                Territorio(
                    territorio_id=f"curitiba-bairro-{slugify(nome)}",
                    nivel="bairro",
                    nome=nome,
                    geometria=geometria,
                    cidade_id="curitiba",
                )
            )
        return territorios

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
