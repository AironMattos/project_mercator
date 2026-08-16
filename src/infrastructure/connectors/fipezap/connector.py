"""Conector do Índice FipeZAP (checkpoint 12b do Radar de Anúncios, seção
9 do prompt de referência). Fonte estática de baixa cadência (mensal),
dois relatórios PDF por mês (venda e locação residencial) - achado real
verificado antes de escrever este módulo: `downloads.fipe.org.br` não
publica `robots.txt` (redireciona pra uma página 404 do site principal -
sem restrição declarada) e o download funciona sem autenticação, mas só
com um User-Agent próprio; o `User-Agent` padrão do `requests` recebe 403
do WAF da Fipe (achado real - não é evasão de bloqueio, é a mesma
identificação honesta que a seção 7 do prompt de referência já exige de
qualquer conector).

**Uso estritamente interno** (seção 9 do prompt de referência: "sem
licença publicada — use internamente para validação e não redistribua o
número sem escrever para a Fipe antes"). Isso não é reforçado neste
módulo - é responsabilidade da camada de API/UI nunca construir um
endpoint público que devolva este dado (ver domain.contexto.models,
docstring de IndicadorFipezapCidade/IndicadorFipezapBairro).
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from domain.contexto import IndicadorFipezapBairro, IndicadorFipezapCidade
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.fipezap.parsing import montar_indicadores

logger = logging.getLogger(__name__)

BASE_URL = "https://downloads.fipe.org.br/indices/fipezap"
RAW_DIR = Path("data/raw/fipezap")
MESES_MAXIMOS_PARA_TENTAR = 4
RETENTATIVAS_MAXIMAS = 3
CIDADE = "Curitiba"
OPERACOES = ("venda", "locacao")


def _url_relatorio(ano_mes: str, operacao: str) -> str:
    return f"{BASE_URL}/fipezap-{ano_mes}-residencial-{operacao}.pdf"


def _mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


@dataclass(frozen=True)
class SnapshotFipezap:
    periodo_referencia: date
    pdfs_por_operacao: dict[str, bytes]


class FipezapConnector:
    """`fetch()` resolve o mês mais recente com os dois relatórios
    (venda e locação) publicados, tentando o mês corrente e retrocedendo
    até `MESES_MAXIMOS_PARA_TENTAR` meses - o informe é publicado com
    atraso de dias/semanas em relação ao mês de referência (achado real:
    em 16/08/2026 o mês de agosto/2026 ainda não estava disponível, só
    julho/2026). `normalize()` extrai texto via pdfplumber e delega toda
    a interpretação para `parsing.py` (puro, testável sem PDF real)."""

    fonte_id = "fipezap"
    cadencia = "mensal"

    def __init__(
        self,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
        user_agent: str = "MercatorBot/0.1 (+https://github.com/AironMattos/project_mercator)",
        extrator_paginas: Callable[[bytes], list[str]] | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", user_agent)
        self._raw_dir = raw_dir
        # Injetável para teste (mesmo padrão do `renderizador` do
        # conector apolar_anuncios) - evita precisar construir um PDF
        # binário de verdade só para testar a orquestração de
        # normalize(); a extração real via pdfplumber é o padrão.
        self._extrator_paginas = extrator_paginas or _extrair_paginas_pdfplumber

    def fetch(self) -> RawSnapshot:
        hoje = datetime.now(timezone.utc).date()
        ano, mes = hoje.year, hoje.month

        for _ in range(MESES_MAXIMOS_PARA_TENTAR):
            ano_mes = f"{ano:04d}{mes:02d}"
            pdfs = self._tentar_baixar_mes(ano_mes)
            if pdfs is not None:
                periodo_referencia = date(ano, mes, 1)
                snapshot_ref = self._salvar_raw(ano_mes, pdfs)
                return RawSnapshot(
                    fonte_id=self.fonte_id,
                    capturado_em=datetime.now(timezone.utc),
                    snapshot_ref=snapshot_ref,
                    conteudo=SnapshotFipezap(
                        periodo_referencia=periodo_referencia, pdfs_por_operacao=pdfs
                    ),
                )
            ano, mes = _mes_anterior(ano, mes)

        raise RuntimeError(
            f"nenhum informe FipeZAP encontrado nos últimos "
            f"{MESES_MAXIMOS_PARA_TENTAR} meses a partir de {hoje.isoformat()}"
        )

    def _tentar_baixar_mes(self, ano_mes: str) -> dict[str, bytes] | None:
        """Qualquer motivo de falha (404 definitivo, ou erro persistente
        mesmo depois do retry/backoff) leva ao mesmo resultado prático:
        tentar o mês anterior, sem abortar `fetch()` inteiro. Achado
        real rodando contra o site de verdade: o mês corrente (ainda não
        publicado) às vezes devolve 403 em vez de 404 de forma
        inconsistente entre requisições (provavelmente uma borda de
        CDN/cache da Fipe, não um bloqueio real - o mesmo mês publicado
        do lado, ex. o anterior, respondeu 200 normalmente nas mesmas
        janelas de tempo) - sem essa distinção o pipeline nunca
        conseguiria cair pro mês anterior de verdade quando isso
        acontecesse."""
        pdfs: dict[str, bytes] = {}
        for operacao in OPERACOES:
            try:
                conteudo = self._baixar_com_retentativa(_url_relatorio(ano_mes, operacao))
            except requests.RequestException as exc:
                logger.warning(
                    "desistindo de %s (%s) após esgotar tentativas: %s - tentando mês anterior",
                    ano_mes,
                    operacao,
                    exc,
                )
                return None
            if conteudo is None:
                return None
            pdfs[operacao] = conteudo
        logger.info("informe FipeZAP de %s encontrado (venda + locação)", ano_mes)
        return pdfs

    def _baixar_com_retentativa(self, url: str) -> bytes | None:
        """404 é resposta definitiva (devolve None pra `_tentar_baixar_mes`
        tratar como mês não publicado). Qualquer outro erro usa backoff
        exponencial antes de propagar a exceção pra quem chamou decidir o
        que fazer - seção 7 do prompt de referência ("Backoff exponencial
        em erro")."""
        espera_s = 2.0
        ultimo_erro: Exception | None = None
        for tentativa in range(1, RETENTATIVAS_MAXIMAS + 1):
            try:
                resp = self._session.get(url, timeout=30)
            except requests.RequestException as exc:
                ultimo_erro = exc
            else:
                if resp.status_code == 404:
                    return None
                if resp.status_code < 400:
                    return resp.content
                ultimo_erro = requests.HTTPError(f"status {resp.status_code} em {url}")

            if tentativa < RETENTATIVAS_MAXIMAS:
                logger.warning(
                    "falha ao baixar %s (tentativa %d/%d): %s - tentando de novo em %.0fs",
                    url,
                    tentativa,
                    RETENTATIVAS_MAXIMAS,
                    ultimo_erro,
                    espera_s,
                )
                time.sleep(espera_s)
                espera_s *= 2

        assert ultimo_erro is not None
        raise ultimo_erro

    def _salvar_raw(self, ano_mes: str, pdfs: dict[str, bytes]) -> str:
        destino_dir = self._raw_dir / ano_mes
        destino_dir.mkdir(parents=True, exist_ok=True)
        for operacao, conteudo in pdfs.items():
            (destino_dir / f"{operacao}.pdf").write_bytes(conteudo)
        return str(destino_dir)

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_slug: dict[str, str],
    ) -> list[IndicadorFipezapCidade | IndicadorFipezapBairro]:
        conteudo: SnapshotFipezap = snapshot.conteudo

        paginas_por_operacao = {
            operacao: self._extrator_paginas(pdf_bytes)
            for operacao, pdf_bytes in conteudo.pdfs_por_operacao.items()
        }
        for operacao, paginas in paginas_por_operacao.items():
            if not paginas:
                logger.warning(
                    "PDF de %s (%s) não produziu nenhuma página de texto",
                    operacao,
                    conteudo.periodo_referencia,
                )

        snapshot_ref_por_operacao = {
            operacao: f"{snapshot.snapshot_ref}/{operacao}.pdf"
            for operacao in conteudo.pdfs_por_operacao
        }

        resultado = montar_indicadores(
            paginas_por_operacao=paginas_por_operacao,
            periodo_referencia=conteudo.periodo_referencia,
            snapshot_ref_por_operacao=snapshot_ref_por_operacao,
            territorio_id_por_slug=territorio_id_por_slug,
            fonte_id=self.fonte_id,
            cidade=CIDADE,
        )
        if not resultado:
            logger.warning(
                "nenhum indicador extraído do informe FipeZAP de %s", conteudo.periodo_referencia
            )
        return resultado


def _extrair_paginas_pdfplumber(pdf_bytes: bytes) -> list[str]:
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [pagina.extract_text() or "" for pagina in pdf.pages]
