from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from domain.valuation import ValorReferenciaTerritorial
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.geometry import aneis_esri_para_multipolygon
from infrastructure.connectors.text import slugify

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/"
    "Publico_GeoCuritiba_Planta_Generica_Valores/MapServer/0"
)
RAW_DIR = Path("data/raw/ippuc_pgv")

# Padrão real confirmado no checkpoint 11a: o nome da layer carrega o ano
# de vigência ("Microrregião (PGV 2025)"), mas não há campo de data por
# feição - é o único sinal de vintage disponível na fonte. Se o nome
# mudar de formato no futuro, cai no fallback (ano corrente) com aviso.
PADRAO_ANO_NO_NOME = re.compile(r"PGV\s*(\d{4})")


class IppucPgvConnector:
    """Conector da Planta Genérica de Valores (IPPUC), layer "Microrregião"
    do serviço Publico_GeoCuritiba_Planta_Generica_Valores - VUKT (Valor
    Unitário Característico de Terreno) por microrregião, em R$/m².

    Granularidade real é microrregião (1.062 polígonos), não face de
    quadra/lote - achado do checkpoint 11a, divergente do prompt de
    referência original. Só componente='terreno': a fonte não separa
    valor de construção (ver checkpoint 11a).
    """

    fonte_id = "ippuc_pgv"
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
        metadata = self._layer_metadata()
        page_size = metadata.get("maxRecordCount", 1000)
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
            conteudo={"features": features, "nome_layer": metadata.get("name", "")},
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_slug: dict[str, str] | None = None,
    ) -> list[ValorReferenciaTerritorial]:
        territorio_id_por_slug = territorio_id_por_slug or {}
        vigencia_inicio = self._vigencia_a_partir_do_nome(snapshot.conteudo["nome_layer"])
        bairros_nao_casados: set[str] = set()

        valores = []
        for feature in snapshot.conteudo["features"]:
            attrs = feature["attributes"]
            rings = feature.get("geometry", {}).get("rings", [])
            vukt = attrs.get("vukt")
            if not rings or vukt is None:
                logger.warning(
                    "feição sem geometria ou sem vukt ignorada: chave=%s",
                    attrs.get("chave"),
                )
                continue

            nm_bairro = (attrs.get("nm_bairro") or "").strip()
            territorio_id = None
            if nm_bairro:
                territorio_id = territorio_id_por_slug.get(slugify(nm_bairro))
                if territorio_id is None:
                    bairros_nao_casados.add(nm_bairro)

            valores.append(
                ValorReferenciaTerritorial(
                    geometria=aneis_esri_para_multipolygon(rings),
                    objectid_fonte=attrs.get("objectid"),
                    territorio_id=territorio_id,
                    tipo_valor="venal",
                    componente="terreno",
                    valor_m2=float(vukt),
                    moeda_data=vigencia_inicio,
                    fonte_id=self.fonte_id,
                    metodologia=(
                        "Planta Genérica de Valores (IPPUC) - VUKT (Valor Unitário "
                        "Característico de Terreno) por microrregião, R$/m²"
                    ),
                    vigencia_inicio=vigencia_inicio,
                    snapshot_ref=snapshot.snapshot_ref,
                )
            )

        if bairros_nao_casados:
            logger.warning(
                "%d bairro(s) da PGV sem correspondência em dim_territorio: %s",
                len(bairros_nao_casados),
                sorted(bairros_nao_casados),
            )
        return valores

    def _layer_metadata(self) -> dict[str, Any]:
        resp = self._session.get(self._base_url, params={"f": "json"}, timeout=30)
        resp.raise_for_status()
        return resp.json()

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

    def _vigencia_a_partir_do_nome(self, nome_layer: str) -> date:
        match = PADRAO_ANO_NO_NOME.search(nome_layer)
        if match:
            return date(int(match.group(1)), 1, 1)
        ano_atual = datetime.now(timezone.utc).year
        logger.warning(
            "não foi possível extrair o ano de vigência do nome da layer "
            "(%r) - usando o ano corrente (%d) como fallback",
            nome_layer,
            ano_atual,
        )
        return date(ano_atual, 1, 1)

    def _salvar_raw(
        self, features: list[dict[str, Any]], capturado_em: datetime
    ) -> str:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        path = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.json"
        path.write_text(
            json.dumps({"features": features}, ensure_ascii=False), encoding="utf-8"
        )
        return str(path)
