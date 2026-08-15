from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from domain.contexto import IndicadorAluguelMercado
from infrastructure.connectors.base import RawSnapshot

logger = logging.getLogger(__name__)

URL = "https://publicfiles.data.quintoandar.com.br/indice_quintoandar_imovelweb/index_quintoandar_imovelweb_serie.csv"
RAW_DIR = Path("data/raw/quintoandar_aluguel")

# Código de cidade real confirmado no checkpoint 11d (não documentado
# publicamente) - o CSV cobre bhe/bsb/cur/poa/rio/spo. Este produto é
# só Curitiba, então o conector filtra para 'cur' e não tenta as outras.
CODIGO_CIDADE_CURITIBA = "cur"
NOME_CIDADE_CURITIBA = "Curitiba"

SEGMENTO_POR_HOUSE_ROOM = {
    "city": "cidade_toda",
    "1": "1_dormitorio",
    "2": "2_dormitorios",
    "3": "3_dormitorios",
}


class QuintoandarAluguelConnector:
    """Conector do Índice QuintoAndar/Imovelweb de aluguel (CSV público,
    checkpoint 11d) - cobre bhe/bsb/cur/poa/rio/spo, filtrado aqui para
    Curitiba ('cur'). Atualização real observada é mensal (não trimestral
    como sugerido pelo material de imprensa da QuintoAndar - achado do
    checkpoint 11d, ver docs/fontes-imobiliario.md), calculada sobre uma
    combinação de anúncios E contratos fechados (não só contratos reais,
    outro ponto que diverge do que a documentação de imprensa sugere)."""

    fonte_id = "quintoandar_indice_aluguel"
    cadencia = "mensal"

    def __init__(
        self,
        url: str = URL,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        self._url = url
        self._session = session or requests.Session()
        self._raw_dir = raw_dir

    def fetch(self) -> RawSnapshot:
        resp = self._session.get(self._url, timeout=30)
        resp.raise_for_status()
        conteudo_csv = resp.text

        capturado_em = datetime.now(timezone.utc)
        snapshot_ref = self._salvar_raw(conteudo_csv, capturado_em)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=snapshot_ref,
            conteudo=conteudo_csv,
        )

    def normalize(self, snapshot: RawSnapshot) -> list[IndicadorAluguelMercado]:
        leitor = csv.DictReader(snapshot.conteudo.splitlines())
        resultado = []
        for linha in leitor:
            if linha["city_name"] != CODIGO_CIDADE_CURITIBA:
                continue
            segmento = SEGMENTO_POR_HOUSE_ROOM.get(linha["house_room"])
            if segmento is None:
                logger.warning("house_room não reconhecido ignorado: %s", linha["house_room"])
                continue
            preco = linha.get("est_price", "").strip()
            if not preco:
                # Primeiros meses da série real têm est_price vazio antes
                # de a amostra ser suficiente - achado do checkpoint 11d,
                # não erro de parsing. Sem leitura, não há o que gravar.
                continue

            resultado.append(
                IndicadorAluguelMercado(
                    cidade=NOME_CIDADE_CURITIBA,
                    periodo_referencia=date.fromisoformat(linha["ts_date"]),
                    segmento=segmento,
                    aluguel_m2=float(preco),
                    variacao_mensal=_float_ou_none(linha.get("chg")),
                    variacao_12m=_float_ou_none(linha.get("acum12m")),
                    fonte_id=self.fonte_id,
                    snapshot_ref=snapshot.snapshot_ref,
                )
            )
        return resultado

    def _salvar_raw(self, conteudo_csv: str, capturado_em: datetime) -> str:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        path = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.csv"
        path.write_text(conteudo_csv, encoding="utf-8")
        return str(path)


def _float_ou_none(valor: str | None) -> float | None:
    if valor is None or not valor.strip():
        return None
    return float(valor)
