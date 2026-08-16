from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from domain.anuncio.taxonomia import normalizar_tipologia

# https://www.apolar.com.br/{alugar|venda}/curitiba/{bairro-slug}/
#   {alugar|venda}-{uso}-{tipologia}-curitiba-...-{id}
_PADRAO_CAMINHO = re.compile(
    r"^https://www\.apolar\.com\.br/(?P<operacao_raw>alugar|venda)/curitiba/"
    r"(?P<bairro_slug>[^/]+)/(?P<slug_completo>[^/]+)/?$"
)
_PADRAO_SLUG = re.compile(
    r"^(?:alugar|venda)-(?P<uso>residencial|comercial|comercialresidencial)-"
    r"(?P<tipologia_raw>[a-z]+)-curitiba-.+-(?P<id_anuncio>\d+)$"
)
_PADRAO_ANDAR = re.compile(r"\bAndar:\s*(\d+)")


@dataclass(frozen=True)
class CamposUrl:
    """Campos extraídos só da URL do sitemap - achado real do checkpoint
    12d: a Apolar é uma SPA em Vue renderizada 100% no cliente, e o slug
    da URL é a única coisa disponível sem executar JS (útil pra descoberta
    rápida, mas price/quartos/vagas/condomínio exigem
    parse_pagina_renderizada, que precisa do Playwright - ver
    connector.py)."""

    url: str
    id_anuncio: str
    operacao: str
    uso: str
    tipologia_raw: str
    bairro_slug: str


def parse_url_anuncio(url: str) -> CamposUrl | None:
    m_caminho = _PADRAO_CAMINHO.match(url)
    if not m_caminho:
        return None
    m_slug = _PADRAO_SLUG.match(m_caminho.group("slug_completo"))
    if not m_slug:
        return None

    operacao_raw = m_caminho.group("operacao_raw")
    operacao = "aluguel" if operacao_raw == "alugar" else "venda"

    return CamposUrl(
        url=url,
        id_anuncio=m_slug.group("id_anuncio"),
        operacao=operacao,
        uso=m_slug.group("uso"),
        tipologia_raw=m_slug.group("tipologia_raw"),
        bairro_slug=m_caminho.group("bairro_slug"),
    )


@dataclass(frozen=True)
class CamposPagina:
    """Campos extraídos da página renderizada (Playwright, checkpoint
    12d) - `.property-details li` (rótulo: valor em <strong>) e
    `.price-box`/`.price-others-values` pro preço e valores associados.
    `andar` só sai do texto livre de "Informações Adicionais" (mesma
    limitação documentada no conector da Chaves na Mão - não há campo
    dedicado). Nunca lê nome/telefone/e-mail/CRECI - esses campos não têm
    contrapartida neste dataclass, então não têm como ser persistidos."""

    preco: float | None
    area_util_m2: float | None
    quartos: int | None
    banheiros: int | None
    vagas: int | None
    condominio: float | None
    iptu: float | None
    andar: int | None


_ROTULOS_PROPERTY_DETAILS = {
    "dormitórios": "quartos",
    "área útil": "area_util_m2",
    "garagem": "vagas",
    "banheiros": "banheiros",
}


def parse_pagina_detalhe(html: str) -> CamposPagina:
    soup = BeautifulSoup(html, "lxml")
    detalhes = _extrair_property_details(soup)

    preco = _numero(_texto_seletor(soup, "div.price-new"))
    condominio = _valor_price_others(soup, "condomínio")
    iptu = _valor_price_others(soup, "iptu")

    andar_match = _PADRAO_ANDAR.search(soup.get_text("\n"))
    andar = int(andar_match.group(1)) if andar_match else None

    return CamposPagina(
        preco=preco,
        area_util_m2=detalhes.get("area_util_m2"),
        quartos=_int_ou_none(detalhes.get("quartos")),
        banheiros=_int_ou_none(detalhes.get("banheiros")),
        vagas=_int_ou_none(detalhes.get("vagas")),
        condominio=condominio,
        iptu=iptu,
        andar=andar,
    )


def _extrair_property_details(soup: BeautifulSoup) -> dict[str, float]:
    resultado: dict[str, float] = {}
    for li in soup.select("ul.property-details li"):
        texto = li.get_text(" ", strip=True)
        if ":" not in texto:
            continue
        rotulo_bruto, _, valor_bruto = texto.partition(":")
        chave = _ROTULOS_PROPERTY_DETAILS.get(rotulo_bruto.strip().lower())
        if chave is None:
            continue
        numero = _numero(valor_bruto)
        if numero is not None:
            resultado[chave] = numero
    return resultado


def _valor_price_others(soup: BeautifulSoup, rotulo: str) -> float | None:
    for li in soup.select("ul.price-others-values li"):
        texto = li.get_text(" ", strip=True).lower()
        if texto.startswith(rotulo):
            return _numero(li.get_text(" ", strip=True))
    return None


def _texto_seletor(soup: BeautifulSoup, seletor: str) -> str | None:
    el = soup.select_one(seletor)
    return el.get_text(" ", strip=True) if el else None


def _numero(texto: str | None) -> float | None:
    if not texto:
        return None
    m = re.search(r"[\d.,]+", texto)
    if not m:
        return None
    bruto = m.group(0)
    # "1.100,00" (BRL) -> 1100.00; "48" (m², sem separador) -> 48.0.
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    return float(bruto)


def _int_ou_none(valor: float | None) -> int | None:
    return int(valor) if valor is not None else None


def tipologia_normalizada(campos_url: CamposUrl) -> str:
    """A tipologia real está em `tipologia_raw` (ex.: "apartamento",
    "terreno") - `uso` ("residencial"/"comercial"/"comercialresidencial",
    achado do checkpoint 12a) descreve a destinação do imóvel, não o tipo
    físico, e não entra na normalização."""
    return normalizar_tipologia(campos_url.tipologia_raw)
