from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.geometry import aneis_esri_para_multipolygon
from infrastructure.connectors.text import slugify

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/"
    "Publico_GeoCuritiba_MapaCadastral/MapServer/15"
)
RAW_DIR = Path("data/raw/geocuritiba_lote_cadastral")
CAMPOS = (
    "objectid,gtm_ind_fiscal,gtm_insc_imob,gtm_mtr_area_terreno,"
    "gtm_nm_bairro,gtm_sigla_zoneamento"
)


@dataclass(frozen=True)
class RegistroLote:
    objectid_fonte: int
    indicacao_fiscal: str | None
    inscricao_imobiliaria: str | None
    area_terreno: float | None
    nome_bairro: str | None
    territorio_id: str | None
    sigla_zoneamento: str | None
    geometria: Any
    fonte_id: str
    snapshot_ref: str


class LoteCadastralConnector:
    """Conector da camada "Lote Cadastral" do GeoCuritiba (MapaCadastral,
    layer 15) - a chave que liga o relatório de Alvará/CVCO da SMU
    (Indicação Fiscal/Inscrição Imobiliária) a território e zoneamento,
    sem geocodificação (achado do checkpoint 11a).

    ~308 mil feições - fetch()/normalize() em streaming (JSONL em disco),
    mesmo padrão de segurança de memória de alvaras_smf; nunca carrega o
    dataset inteiro em memória de uma vez.
    """

    fonte_id = "geocuritiba_lote_cadastral"
    cadencia = "mensal"

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
        capturado_em = datetime.now(timezone.utc)
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        destino = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.jsonl"

        total = 0
        offset = 0
        with open(destino, "w", encoding="utf-8") as arquivo:
            while True:
                page = self._query_page(offset=offset, count=page_size)
                features = page.get("features", [])
                for feature in features:
                    arquivo.write(json.dumps(feature, ensure_ascii=False) + "\n")
                total += len(features)
                if not page.get("exceededTransferLimit") or not features:
                    break
                offset += len(features)
                if offset % (page_size * 20) == 0:
                    logger.info("baixados %d lotes...", offset)

        logger.info("download concluído: %d lotes em %s", total, destino)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=str(destino),
            conteudo={"path": str(destino), "total": total},
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_slug: dict[str, str] | None = None,
    ) -> Iterator[RegistroLote]:
        territorio_id_por_slug = territorio_id_por_slug or {}
        bairros_nao_casados: set[str] = set()

        with open(snapshot.conteudo["path"], encoding="utf-8") as arquivo:
            for linha in arquivo:
                feature = json.loads(linha)
                registro = self._normalizar_feature(
                    feature, snapshot.snapshot_ref, territorio_id_por_slug, bairros_nao_casados
                )
                if registro is not None:
                    yield registro

        if bairros_nao_casados:
            logger.warning(
                "%d bairro(s) do lote cadastral sem correspondência em dim_territorio: %s",
                len(bairros_nao_casados),
                sorted(bairros_nao_casados),
            )

    def _normalizar_feature(
        self,
        feature: dict[str, Any],
        snapshot_ref: str,
        territorio_id_por_slug: dict[str, str],
        bairros_nao_casados: set[str],
    ) -> RegistroLote | None:
        attrs = feature["attributes"]
        rings = feature.get("geometry", {}).get("rings", [])
        geometria = aneis_esri_para_multipolygon(rings) if rings else None

        indicacao_fiscal = (attrs.get("gtm_ind_fiscal") or "").strip() or None
        nome_bairro = (attrs.get("gtm_nm_bairro") or "").strip()
        territorio_id = None
        if nome_bairro:
            territorio_id = territorio_id_por_slug.get(slugify(nome_bairro))
            if territorio_id is None:
                bairros_nao_casados.add(nome_bairro)

        return RegistroLote(
            objectid_fonte=attrs["objectid"],
            indicacao_fiscal=indicacao_fiscal,
            inscricao_imobiliaria=(attrs.get("gtm_insc_imob") or "").strip() or None,
            area_terreno=attrs.get("gtm_mtr_area_terreno"),
            nome_bairro=nome_bairro or None,
            territorio_id=territorio_id,
            sigla_zoneamento=(attrs.get("gtm_sigla_zoneamento") or "").strip() or None,
            geometria=geometria,
            fonte_id=self.fonte_id,
            snapshot_ref=snapshot_ref,
        )

    def _max_record_count(self) -> int:
        resp = self._session.get(self._base_url, params={"f": "json"}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("maxRecordCount", 1000)

    def _query_page(self, offset: int, count: int) -> dict[str, Any]:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": CAMPOS,
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
