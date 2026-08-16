from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from domain.anuncio.taxonomia import normalizar_tipologia

# Âncora fixa: este conector só coleta Curitiba/PR (escopo do produto,
# seção 11 do prompt de referência: "uma cidade"). A URL da Chaves na Mão
# não separa cidade/bairro por um delimitador estável quando os dois são
# compostos por mais de uma palavra (ex.: "porto-seguro", "vale-verde") -
# ancorar no literal "-pr-curitiba-" resolve a ambiguidade sem precisar
# adivinhar onde a cidade termina e o bairro começa.
_PADRAO_URL = re.compile(
    r"^https://www\.chavesnamao\.com\.br/imovel/"
    r"(?P<prefixo>.+)-pr-curitiba-(?P<bairro_slug>.+)"
    r"-(?P<area_m2>\d+)m2-RS(?P<preco>\d+)"
    r"/id-(?P<id_anuncio>\d+)/?$"
)
_PADRAO_QUARTOS = re.compile(r"-(\d+)-quartos\b")
_PADRAO_ANDAR = re.compile(r"(\d+)[ºª°]\s*andar", re.IGNORECASE)


@dataclass(frozen=True)
class CamposUrl:
    """Campos extraídos só da URL do sitemap - disponíveis antes de
    qualquer fetch da página de detalhe (rápido, sem rede)."""

    url: str
    id_anuncio: str
    operacao: str
    tipologia_raw: str
    bairro_slug: str
    area_m2_url: float
    preco_url: float
    quartos_url: int | None


def parse_url_anuncio(url: str) -> CamposUrl | None:
    """Extrai os campos codificados no slug da URL de um anúncio de
    Curitiba/PR - None se a URL não bater com o padrão esperado (ex.: uma
    página de categoria/listagem, não de anúncio individual)."""
    m = _PADRAO_URL.match(url)
    if not m:
        return None

    prefixo = m.group("prefixo")
    if "-a-venda" in prefixo:
        operacao = "venda"
        tipologia_raw = prefixo.split("-a-venda")[0]
    elif "-para-alugar" in prefixo:
        operacao = "aluguel"
        tipologia_raw = prefixo.split("-para-alugar")[0]
    else:
        return None

    quartos_match = _PADRAO_QUARTOS.search(prefixo)
    quartos_url = int(quartos_match.group(1)) if quartos_match else None

    return CamposUrl(
        url=url,
        id_anuncio=m.group("id_anuncio"),
        operacao=operacao,
        tipologia_raw=tipologia_raw,
        bairro_slug=m.group("bairro_slug"),
        area_m2_url=float(m.group("area_m2")),
        preco_url=float(m.group("preco")),
        quartos_url=quartos_url,
    )


@dataclass(frozen=True)
class CamposPagina:
    """Campos extraídos da página de detalhe renderizada no servidor
    (JSON-LD + ficha técnica em HTML) - complementa CamposUrl com o que
    não está no slug: preço exato, área útil, banheiros, vagas,
    condomínio, IPTU e (best-effort) andar. Nunca inclui nome, telefone,
    e-mail, CRECI ou o texto livre da descrição - só os campos numéricos
    abaixo são lidos, o resto do HTML nunca é persistido (ver
    docs/lia-anuncios.md, seção 1)."""

    preco: float | None
    area_util_m2: float | None
    quartos: int | None
    banheiros: int | None
    vagas: int | None
    condominio: float | None
    iptu: float | None
    andar: int | None


def parse_pagina_detalhe(html: str) -> CamposPagina:
    """Parse da página de detalhe real (server-rendered, checkpoint 12a) -
    dois pontos de extração, cada um com fallback próprio:

    1. JSON-LD (`application/ld+json`, schema.org RealEstateListing) -
       fonte mais confiável pra preço (`offers.price`, sempre numérico).
    2. Ficha técnica em HTML: elementos com `aria-label` exato em
       {"area-util","area-total","Quartos","Banheiros","Garagens"} (a
       lista de imóveis similares no rodapé da página usa os mesmos
       rótulos em minúsculo - "quartos"/"garagens"/"area" - e por isso
       nunca colide com este casamento sensível a maiúsculas), e pares
       `<span class="row spacing">` com exatamente dois `<p>` (rótulo,
       valor) pra Condomínio/IPTU.

    `andar` só sai do texto livre da descrição do JSON-LD (não há campo
    dedicado na ficha técnica desta fonte) - fica None quando o padrão
    "Nº andar" não aparece, nunca inventado."""
    soup = BeautifulSoup(html, "lxml")

    preco = _extrair_preco_json_ld(soup)
    andar = _extrair_andar_da_descricao(soup)

    area_util_m2 = _extrair_numero_aria_label(soup, "area-util")
    quartos = _extrair_int_aria_label(soup, "Quartos")
    banheiros = _extrair_int_aria_label(soup, "Banheiros")
    vagas = _extrair_int_aria_label(soup, "Garagens")

    valores_rotulados = _extrair_valores_rotulados(soup)
    condominio = valores_rotulados.get("condomínio") or valores_rotulados.get("condominio")
    iptu = valores_rotulados.get("iptu")

    return CamposPagina(
        preco=preco,
        area_util_m2=area_util_m2,
        quartos=quartos,
        banheiros=banheiros,
        vagas=vagas,
        condominio=condominio,
        iptu=iptu,
        andar=andar,
    )


def _extrair_preco_json_ld(soup: BeautifulSoup) -> float | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            dados = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        grafo = dados.get("@graph", [dados]) if isinstance(dados, dict) else []
        for item in grafo:
            if item.get("@type") != "RealEstateListing":
                continue
            oferta = (item.get("about") or {}).get("offers") or {}
            preco = oferta.get("price")
            if preco is not None:
                return float(preco)
    return None


def _extrair_andar_da_descricao(soup: BeautifulSoup) -> int | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            dados = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        grafo = dados.get("@graph", [dados]) if isinstance(dados, dict) else []
        for item in grafo:
            if item.get("@type") != "RealEstateListing":
                continue
            descricao = item.get("description", "")
            m = _PADRAO_ANDAR.search(descricao)
            if m:
                return int(m.group(1))
    return None


def _extrair_numero_aria_label(soup: BeautifulSoup, aria_label: str) -> float | None:
    el = soup.find(attrs={"aria-label": aria_label})
    if el is None:
        return None
    m = re.search(r"[\d.,]+", el.get_text())
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))


def _extrair_int_aria_label(soup: BeautifulSoup, aria_label: str) -> int | None:
    valor = _extrair_numero_aria_label(soup, aria_label)
    return int(valor) if valor is not None else None


def _extrair_valores_rotulados(soup: BeautifulSoup) -> dict[str, float]:
    resultado: dict[str, float] = {}
    for span in soup.select("span.row.spacing"):
        ps = span.find_all("p", recursive=False)
        if len(ps) != 2:
            continue
        rotulo = ps[0].get_text(strip=True).lower()
        m = re.search(r"[\d.,]+", ps[1].get_text())
        if not m:
            continue
        resultado[rotulo] = float(m.group(0).replace(".", "").replace(",", "."))
    return resultado


def tipologia_normalizada(campos_url: CamposUrl) -> str:
    return normalizar_tipologia(campos_url.tipologia_raw)
