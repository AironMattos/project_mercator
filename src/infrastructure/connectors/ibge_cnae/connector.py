from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from commerce.cnae import Cnae
from infrastructure.connectors.base import RawSnapshot

BASE_URL = "https://servicodados.ibge.gov.br/api/v2/cnae/subclasses"
RAW_DIR = Path("data/raw/ibge_cnae")


class IbgeCnaeConnector:
    """Conector da tabela oficial de referência de CNAE (IBGE, API pública
    servicodados.ibge.gov.br). Fonte estática - a classificação muda raramente
    (nova versão a cada alguns anos), não é uma fonte mensal.
    """

    fonte_id = "ibge_cnae"
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
        resp = self._session.get(self._base_url, timeout=60)
        resp.raise_for_status()
        dados = resp.json()

        capturado_em = datetime.now(timezone.utc)
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        destino = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.json"
        destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=str(destino),
            conteudo=dados,
        )

    def normalize(self, snapshot: RawSnapshot) -> list[Cnae]:
        resultado = []
        for item in snapshot.conteudo:
            classe: dict[str, Any] = item["classe"]
            grupo = classe["grupo"]
            divisao = grupo["divisao"]
            secao = divisao["secao"]
            resultado.append(
                Cnae(
                    codigo_cnae=item["id"],
                    descricao=item["descricao"],
                    secao=secao["id"],
                    divisao=divisao["id"],
                    grupo=grupo["id"],
                    classe=classe["id"],
                    subclasse=item["id"],
                )
            )
        return resultado
