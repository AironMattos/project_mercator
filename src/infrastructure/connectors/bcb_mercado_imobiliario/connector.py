from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from domain.valuation import IndicadorMercadoImobiliarioUf
from infrastructure.connectors.base import RawSnapshot

logger = logging.getLogger(__name__)

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/MercadoImobiliario/versao/v1/odata/mercadoimobiliario"
RAW_DIR = Path("data/raw/bcb_mercado_imobiliario")

# As 14 séries reais confirmadas contra a Metodologia.pdf oficial do BCB
# (checkpoint 11d, seção "Imóveis") - o serviço OData não expõe um
# catálogo de séries navegável (é uma tabela genérica Data/Info/Valor com
# milhares de séries de crédito imobiliário misturadas), então esta lista
# é reproduzida explicitamente aqui, não descoberta em runtime. categoria
# desambigua a natureza do número (nunca somar contagem com valor
# monetário); tipo_valor só é preenchido para as duas séries de
# categoria='valor', reaproveitando a mesma validação das quatro
# grandezas de domain.valuation.
#
# 'imoveis_valor_compra' vira tipo_valor='transacao' (não 'avaliacao'):
# a Metodologia.pdf descreve as duas como "a mediana do valor dos imóveis
# ADQUIRIDOS na data-base classificada em avaliação ou compra" - "compra"
# é o preço efetivamente contratado na aquisição, "avaliação" é a
# estimativa do banco para a garantia. São conceitos diferentes mesmo
# vindo da mesma fonte (SCR/ACNV1501) - ver docs/fontes-imobiliario.md
# para o viés de amostra (só imóveis financiados via alienação
# fiduciária/hipoteca, não toda transação do estado).
INDICADORES: dict[str, dict[str, str | None]] = {
    "imoveis_tipo_apartamento": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_tipo_casa": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_dormitorio_1": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_dormitorio_2": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_dormitorio_3": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_dormitorio_4_mais": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_area_privativa": {"categoria": "area", "unidade": "m²", "tipo_valor": None},
    "imoveis_area_total": {"categoria": "area", "unidade": "m²", "tipo_valor": None},
    "imoveis_implantacao_condominio": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_implantacao_isolado": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_valor_avaliacao": {"categoria": "valor", "unidade": "R$", "tipo_valor": "avaliacao"},
    "imoveis_valor_compra": {"categoria": "valor", "unidade": "R$", "tipo_valor": "transacao"},
    "imoveis_garantia_hipoteca": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
    "imoveis_garantia_alienacao_fiduciaria": {"categoria": "contagem", "unidade": "imóveis", "tipo_valor": None},
}


class BcbMercadoImobiliarioConnector:
    """Conector do serviço MercadoImobiliario do BCB (OData), granularidade
    UF (checkpoint 11d) - histórico mensal desde 2018-01, licença ODbL
    (confirmado em dadosabertos.bcb.gov.br). Escopo desta fase: só
    Paraná (uf='PR') - rotular sempre como "Paraná", nunca implicar
    Curitiba (a fonte não tem granularidade municipal)."""

    fonte_id = "bcb_mercado_imobiliario"
    cadencia = "mensal"

    def __init__(
        self,
        uf: str = "PR",
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        self._uf = uf
        self._base_url = base_url
        self._session = session or requests.Session()
        self._raw_dir = raw_dir

    def fetch(self) -> RawSnapshot:
        leituras: list[dict[str, Any]] = []
        for indicador in INDICADORES:
            info = f"{indicador}_{self._uf.lower()}"
            leituras.extend(self._query_serie(info))

        capturado_em = datetime.now(timezone.utc)
        snapshot_ref = self._salvar_raw(leituras, capturado_em)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=snapshot_ref,
            conteudo={"leituras": leituras, "uf": self._uf},
        )

    def normalize(self, snapshot: RawSnapshot) -> list[IndicadorMercadoImobiliarioUf]:
        uf = snapshot.conteudo["uf"]
        resultado = []
        for leitura in snapshot.conteudo["leituras"]:
            indicador_uf = leitura["Info"]
            sufixo = f"_{uf.lower()}"
            if not indicador_uf.endswith(sufixo):
                logger.warning("série com sufixo de UF inesperado ignorada: %s", indicador_uf)
                continue
            indicador = indicador_uf[: -len(sufixo)]
            meta = INDICADORES.get(indicador)
            if meta is None:
                logger.warning("série não catalogada ignorada: %s", indicador_uf)
                continue

            resultado.append(
                IndicadorMercadoImobiliarioUf(
                    uf=uf,
                    periodo_referencia=date.fromisoformat(leitura["Data"]),
                    indicador=indicador,
                    categoria=meta["categoria"],
                    tipo_valor=meta["tipo_valor"],
                    unidade=meta["unidade"],
                    leitura=float(leitura["Valor"]),
                    fonte_id=self.fonte_id,
                    snapshot_ref=snapshot.snapshot_ref,
                )
            )
        return resultado

    def _query_serie(self, info: str) -> list[dict[str, Any]]:
        # Query string montada à mão e passada dentro da própria URL, não
        # via `params=` - achado do checkpoint 11d: requests codifica
        # espaço como "+" quando o dict `params` é usado, e o parser
        # OData do BCB interpreta "+" como o operador de adição, não como
        # espaço (o erro real observado foi "types Edm.Boolean e
        # Edm.String não são compatíveis", porque "Info+eq+'x'" virava
        # "Info + eq + 'x'"). Passar a query já montada na URL faz o
        # requests codificar espaço como %20, que o serviço aceita.
        url = (
            f"{self._base_url}?$filter=Info eq '{info}'"
            "&$orderby=Data asc&$top=1000&$format=json"
        )
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "@odata.nextLink" in data:
            logger.warning(
                "série %s tem mais páginas do que o esperado (@odata.nextLink "
                "presente) - resultado pode estar incompleto",
                info,
            )
        return data.get("value", [])

    def _salvar_raw(self, leituras: list[dict[str, Any]], capturado_em: datetime) -> str:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        path = self._raw_dir / f"{capturado_em:%Y%m%dT%H%M%S}.json"
        path.write_text(json.dumps({"leituras": leituras}, ensure_ascii=False), encoding="utf-8")
        return str(path)
