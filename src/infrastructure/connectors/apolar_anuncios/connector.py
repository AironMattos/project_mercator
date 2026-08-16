from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from domain.anuncio import ObservacaoAnuncio, calcular_impressao_digital
from domain.entity import Entidade
from infrastructure.connectors.apolar_anuncios.parsing import (
    parse_pagina_detalhe,
    parse_url_anuncio,
    tipologia_normalizada,
)
from infrastructure.connectors.base import RawSnapshot

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.apolar.com.br/sitemap.xml"
RAW_DIR = Path("data/raw/apolar_anuncios")
# Só páginas de detalhe (terminam em -<id numérico>) - as de categoria/
# listagem (ex.: /alugar/curitiba/sitio-cercado) não têm essa cauda, ver
# achado do checkpoint 12a.
PADRAO_DETALHE_CURITIBA = re.compile(
    r"^https://www\.apolar\.com\.br/(alugar|venda)/curitiba/[^/]+/[^/]+-\d+/?$"
)
INTERVALO_MINIMO_S = 3.0
LIMIAR_HORAS_PARA_AVISAR = 4.0

# Assinatura do renderizador injetável (real: Playwright; testes: fake que
# devolve HTML fixo) - separa "como renderizar a página" (rede,
# dependente de navegador) de "como interpretar o HTML renderizado"
# (parsing.py, puro).
Renderizador = Callable[[str], str]


def _renderizador_playwright(user_agent: str) -> Renderizador:
    """Cria o renderizador real (Playwright/Chromium) - só é chamado se
    ninguém injetar um renderizador de teste. Import de playwright.sync_api
    fica dentro da função para o resto do módulo continuar importável em
    ambiente sem o pacote instalado (ex.: só rodando os testes de
    parsing.py, que não dependem de Playwright)."""
    from playwright.sync_api import sync_playwright

    class _Sessao:
        def __init__(self) -> None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()
            self._page = self._browser.new_page(user_agent=user_agent)

        def renderizar(self, url: str) -> str:
            self._page.goto(url, wait_until="networkidle", timeout=30000)
            return self._page.content()

        def fechar(self) -> None:
            self._browser.close()
            self._pw.stop()

    sessao = _Sessao()

    # Função solta (não o bound method `sessao.renderizar` direto) -
    # achado real rodando contra o site de verdade (unit tests injetam um
    # fake e nunca pegam isso): bound methods não têm `__dict__` próprio,
    # então `renderizador.fechar = ...` levanta AttributeError.
    def renderizador(url: str) -> str:
        return sessao.renderizar(url)

    renderizador.fechar = sessao.fechar  # type: ignore[attr-defined]
    return renderizador


@dataclass(frozen=True)
class RegistroNormalizado:
    entidade: Entidade
    observacao: ObservacaoAnuncio
    bairro_slug: str
    territorio_id: str | None


class ApolarAnunciosConnector:
    """Conector do Radar de Anúncios para a Apolar (checkpoint 12d).

    Achado real (checkpoint 12a/12d): o site é uma SPA em Vue totalmente
    renderizada no cliente - `requests` sozinho só vê título/meta
    description, nunca preço/quartos/vagas/condomínio. `normalize()` usa
    Playwright (Chromium headless) para renderizar cada página antes de
    fazer o parse - decisão confirmada com o dono do projeto (não é uma
    troca por endpoint interno de API, que a seção 7 do prompt de
    referência proíbe explicitamente; é a mesma página pública que
    qualquer visitante/crawler que executa JS veria).

    `fetch()` continua HTTP puro - o sitemap.xml em si é XML estático,
    não precisa de navegador."""

    fonte_id = "apolar_anuncios"
    cadencia = "semanal"

    def __init__(
        self,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
        intervalo_minimo_s: float = INTERVALO_MINIMO_S,
        user_agent: str = "MercatorBot/0.1 (+https://github.com/AironMattos/project_mercator)",
        renderizador: Renderizador | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", user_agent)
        self._raw_dir = raw_dir
        self._intervalo_minimo_s = intervalo_minimo_s
        self._user_agent = user_agent
        self._renderizador_injetado = renderizador
        self._ultima_requisicao: float = 0.0

    def _aguardar_ritmo(self) -> None:
        decorrido = time.monotonic() - self._ultima_requisicao
        se_falta = self._intervalo_minimo_s - decorrido
        if se_falta > 0:
            time.sleep(se_falta)
        self._ultima_requisicao = time.monotonic()

    def fetch(self) -> RawSnapshot:
        capturado_em = datetime.now(timezone.utc)
        self._raw_dir.mkdir(parents=True, exist_ok=True)

        self._aguardar_ritmo()
        resp = self._session.get(SITEMAP_URL, timeout=60)
        resp.raise_for_status()
        urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
        urls_curitiba = [u for u in urls if PADRAO_DETALHE_CURITIBA.match(u)]
        logger.info(
            "%d URLs no sitemap, %d páginas de detalhe de Curitiba", len(urls), len(urls_curitiba)
        )

        horas_estimadas = len(urls_curitiba) * self._intervalo_minimo_s / 3600
        if horas_estimadas > LIMIAR_HORAS_PARA_AVISAR:
            logger.warning(
                "%d anúncios de Curitiba encontrados - renderizar todos a %.0fs/req levaria "
                "~%.1fh. normalize() aceita `limite` e `ja_coletados` para rodar em lotes "
                "retomáveis.",
                len(urls_curitiba),
                self._intervalo_minimo_s,
                horas_estimadas,
            )

        snapshot_ref = self._raw_dir / f"urls_{capturado_em.strftime('%Y%m%dT%H%M%S')}.json"
        snapshot_ref.write_text(json.dumps(urls_curitiba), encoding="utf-8")

        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=str(snapshot_ref),
            conteudo=urls_curitiba,
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        observado_em: date,
        territorio_id_por_slug: dict[str, str],
        ja_coletados: set[str] | None = None,
        limite: int | None = None,
    ) -> Iterator[RegistroNormalizado]:
        ja_coletados = ja_coletados or set()
        buscados_nesta_chamada = 0

        renderizador = self._renderizador_injetado or _renderizador_playwright(self._user_agent)
        try:
            for url in snapshot.conteudo:
                campos_url = parse_url_anuncio(url)
                if campos_url is None:
                    logger.warning("URL fora do padrão esperado, ignorada: %s", url)
                    continue
                if campos_url.id_anuncio in ja_coletados:
                    continue
                if limite is not None and buscados_nesta_chamada >= limite:
                    break

                self._aguardar_ritmo()
                try:
                    html = renderizador(url)
                except Exception as exc:  # noqa: BLE001 - renderização de página real, várias falhas possíveis
                    logger.warning("falha ao renderizar %s: %s", url, exc)
                    continue
                buscados_nesta_chamada += 1

                campos_pagina = parse_pagina_detalhe(html)

                yield self._montar_registro(
                    campos_url, campos_pagina, observado_em, territorio_id_por_slug
                )
        finally:
            fechar = getattr(renderizador, "fechar", None)
            if fechar is not None:
                fechar()

    def _montar_registro(
        self,
        campos_url,
        campos_pagina,
        observado_em: date,
        territorio_id_por_slug: dict[str, str],
    ) -> RegistroNormalizado:
        tipologia = tipologia_normalizada(campos_url)
        territorio_id = territorio_id_por_slug.get(campos_url.bairro_slug)
        chave_territorial = territorio_id or campos_url.bairro_slug

        impressao_digital = ""
        if campos_pagina.area_util_m2 is not None:
            impressao_digital = calcular_impressao_digital(
                territorio_id=chave_territorial,
                area_util_m2=campos_pagina.area_util_m2,
                quartos=campos_pagina.quartos,
                vagas=campos_pagina.vagas,
                andar=campos_pagina.andar,
                condominio=campos_pagina.condominio,
            )

        identificador_fonte = hash_identificador_anuncio(self.fonte_id, campos_url.id_anuncio)
        entidade = Entidade(tipo_entidade="anuncio_imovel", identificador_fonte=identificador_fonte)

        observacao = ObservacaoAnuncio(
            entidade_id=entidade.entidade_id,
            observado_em=observado_em,
            operacao=campos_url.operacao,
            tipologia=tipologia,
            preco=campos_pagina.preco,
            condominio=campos_pagina.condominio,
            iptu=campos_pagina.iptu,
            area_util_m2=campos_pagina.area_util_m2,
            quartos=campos_pagina.quartos,
            banheiros=campos_pagina.banheiros,
            vagas=campos_pagina.vagas,
            andar=campos_pagina.andar,
            # Achado real (ver parsing.py/testes): a Apolar não publica
            # área útil pra todo anúncio de forma consistente com o resto
            # da ficha (às vezes só "Área Total"). Sem área, a impressão
            # digital fica vazia e o anúncio não participa da resolução
            # entre fontes (seção 8.1) - mas continua gravado normalmente
            # como observação, só não é agregável em cluster.
            impressao_digital=impressao_digital or f"sem-fp:{campos_url.id_anuncio}",
            fonte_id=self.fonte_id,
            snapshot_ref=campos_url.url,
            territorio_id=territorio_id,
        )
        return RegistroNormalizado(
            entidade=entidade,
            observacao=observacao,
            bairro_slug=campos_url.bairro_slug,
            territorio_id=territorio_id,
        )

def hash_identificador_anuncio(fonte_id: str, id_anuncio: str) -> str:
    return hashlib.sha256(f"{fonte_id}:{id_anuncio}".encode("utf-8")).hexdigest()
