from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from domain.anuncio import ObservacaoAnuncio, calcular_impressao_digital
from domain.entity import Entidade
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.chavesnamao_anuncios.parsing import (
    parse_pagina_detalhe,
    parse_url_anuncio,
    tipologia_normalizada,
)

logger = logging.getLogger(__name__)

SITEMAP_INDEX_URL = "https://www.chavesnamao.com.br/sitemap-index.xml"
RAW_DIR = Path("data/raw/chavesnamao_anuncios")
PADRAO_SITEMAP_ANUNCIO = re.compile(r"sitemap-(venda|aluguel)-imoveis-\d+\.xml\.gz$")
ANCORA_CURITIBA = "-pr-curitiba-"

# Seção 7 do prompt de referência: "Máximo de 1 requisição a cada 3
# segundos por domínio". Vale tanto pra descoberta (sitemaps) quanto pra
# coleta (páginas de detalhe) - o mesmo limitador serve os dois, só a
# escala de chamadas difere (94 sitemaps vs. potencialmente dezenas de
# milhares de páginas de detalhe, ver achado de escala abaixo).
INTERVALO_MINIMO_S = 3.0

# Achado real do checkpoint 12d, rodando a descoberta completa contra o
# site real: 81.408 anúncios de Curitiba/PR entre os 4.644.116 URLs
# nacionais dos 94 sitemaps de venda+aluguel - bate com a citação de
# imprensa já registrada em docs/fontes-anuncios.md ("~80 mil imóveis em
# Curitiba"). A 1 req/3s, coletar TODOS de uma vez levaria ~68 horas -
# mesma classe de achado do checkpoint 9c (Nominatim): reportar antes de
# tentar, não silenciosamente rodar dias. `normalize()` aceita `limite` e
# `ja_coletados` exatamente para permitir rodar em lotes retomáveis ao
# longo de várias execuções, em vez de uma sessão contínua impraticável.
LIMIAR_HORAS_PARA_AVISAR = 4.0


@dataclass(frozen=True)
class RegistroNormalizado:
    entidade: Entidade
    observacao: ObservacaoAnuncio
    bairro_slug: str
    territorio_id: str | None


class ChavesNaMaoAnunciosConnector:
    """Conector do Radar de Anúncios para a Chaves na Mão (checkpoint 12d).

    Descoberta exclusivamente por sitemap (nunca busca/paginação, seção 7
    do prompt de referência). `fetch()` resolve só a LISTA de URLs de
    anúncio de Curitiba/PR (rápido - sitemaps são arquivos estáticos,
    ~94 arquivos, minutos, não horas). `normalize()` é quem faz o trabalho
    lento e rate-limited: uma requisição por página de detalhe, a
    INTERVALO_MINIMO_S de distância, com o mesmo rate limit valendo tanto
    pra sitemap quanto pra detalhe.

    Coleta feita com a decisão explícita do dono do projeto de prosseguir
    apesar do veredito desfavorável de Termos de Uso (ver
    docs/fontes-anuncios.md, seção 2, decisão de 2026-08-15) - a
    disciplina técnica desta seção (rate limit, identificação honesta,
    nunca burlar proteção técnica, descarte de dado pessoal) continua
    valendo com o mesmo rigor, é a única salvaguarda que resta nesta
    fonte.
    """

    fonte_id = "chavesnamao_anuncios"
    cadencia = "semanal"

    def __init__(
        self,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
        intervalo_minimo_s: float = INTERVALO_MINIMO_S,
        user_agent: str = "MercatorBot/0.1 (+https://github.com/AironMattos/project_mercator)",
    ) -> None:
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", user_agent)
        self._raw_dir = raw_dir
        self._intervalo_minimo_s = intervalo_minimo_s
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
        resp = self._session.get(SITEMAP_INDEX_URL, timeout=30)
        resp.raise_for_status()
        locs = re.findall(r"<loc>([^<]+)</loc>", resp.text)
        sitemaps_anuncio = sorted(u for u in locs if PADRAO_SITEMAP_ANUNCIO.search(u))
        logger.info("%d sitemaps de anúncio individual encontrados", len(sitemaps_anuncio))

        urls_curitiba: list[str] = []
        for i, sitemap_url in enumerate(sitemaps_anuncio, start=1):
            self._aguardar_ritmo()
            resp = self._session.get(sitemap_url, timeout=60)
            resp.raise_for_status()
            xml = gzip.decompress(resp.content).decode("utf-8")
            urls = re.findall(r"<loc>([^<]+)</loc>", xml)
            urls_curitiba.extend(u for u in urls if ANCORA_CURITIBA in u)
            if i % 20 == 0 or i == len(sitemaps_anuncio):
                logger.info(
                    "%d/%d sitemaps lidos, %d anúncios de Curitiba encontrados até agora",
                    i,
                    len(sitemaps_anuncio),
                    len(urls_curitiba),
                )

        horas_estimadas = len(urls_curitiba) * self._intervalo_minimo_s / 3600
        if horas_estimadas > LIMIAR_HORAS_PARA_AVISAR:
            logger.warning(
                "%d anúncios de Curitiba encontrados - coletar todos a %.0fs/req levaria "
                "~%.1fh. normalize() aceita `limite` e `ja_coletados` para rodar em lotes "
                "retomáveis ao longo de várias execuções, em vez de uma sessão contínua.",
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
        """Gerador (fonte grande, mesmo padrão de alvaras_smf) - uma
        requisição HTTP rate-limited por anúncio. `ja_coletados` (ids de
        anúncio já processados nesta rodada) e `limite` (máximo de novas
        páginas a buscar nesta chamada) existem para permitir retomar um
        lote parcial entre execuções, sem re-baixar o que já foi coletado
        - mesmo espírito de "retomável" já usado no pipeline de
        geocodificação (checkpoint 9b)."""
        ja_coletados = ja_coletados or set()
        buscados_nesta_chamada = 0

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
                resp = self._session.get(url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("falha ao buscar %s: %s", url, exc)
                continue
            buscados_nesta_chamada += 1

            campos_pagina = parse_pagina_detalhe(resp.text)

            yield self._montar_registro(
                campos_url, campos_pagina, observado_em, territorio_id_por_slug
            )

    def _montar_registro(
        self,
        campos_url,
        campos_pagina,
        observado_em: date,
        territorio_id_por_slug: dict[str, str],
    ) -> RegistroNormalizado:
        tipologia = tipologia_normalizada(campos_url)
        territorio_id = territorio_id_por_slug.get(campos_url.bairro_slug)

        # area_m2 sempre vem da URL (a regex de parse_url_anuncio exige o
        # grupo "\d+m2" - nunca None); campos_pagina.area_util_m2 (mais
        # preciso, quando presente) tem prioridade.
        area_util_m2 = campos_pagina.area_util_m2 or campos_url.area_m2_url
        preco = campos_pagina.preco if campos_pagina.preco is not None else campos_url.preco_url
        quartos = campos_pagina.quartos if campos_pagina.quartos is not None else campos_url.quartos_url

        # A impressão digital precisa de uma chave territorial pra
        # existir, mas nunca pode ficar vazia (ObservacaoAnuncio exige) -
        # sem territorio_id resolvido contra dim_territorio, cai pro slug
        # bruto do bairro (sempre disponível, vem da URL). O achado de
        # bairro não resolvido continua visível em `territorio_id=None`
        # na observação (mesmo tratamento de "CIC"/"Cidade Industrial" no
        # Radar de Comércio) - só a impressão digital usa o fallback, pra
        # nunca perder a capacidade de resolução entre fontes por causa
        # de uma variação de grafia de bairro.
        chave_territorial = territorio_id or campos_url.bairro_slug
        impressao_digital = calcular_impressao_digital(
            territorio_id=chave_territorial,
            area_util_m2=area_util_m2,
            quartos=quartos,
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
            preco=preco,
            condominio=campos_pagina.condominio,
            iptu=campos_pagina.iptu,
            area_util_m2=area_util_m2,
            quartos=quartos,
            banheiros=campos_pagina.banheiros,
            vagas=campos_pagina.vagas,
            andar=campos_pagina.andar,
            impressao_digital=impressao_digital,
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
    """identificador_fonte = hash(portal + id_do_anuncio), seção 8 do
    prompt de referência - função pública porque o pipeline de ingestão
    também precisa dela pra checar, sem reler HTML nenhum, se um anúncio
    já foi coletado nesta rodada (ver run_chavesnamao_anuncios.py)."""
    return hashlib.sha256(f"{fonte_id}:{id_anuncio}".encode("utf-8")).hexdigest()
