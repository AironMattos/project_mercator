import gzip
from datetime import date, datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.chavesnamao_anuncios.connector import (
    ChavesNaMaoAnunciosConnector,
)

SITEMAP_INDEX_XML = """<?xml version="1.0"?>
<sitemapindex>
<sitemap><loc>https://www.chavesnamao.com.br/sitemap-venda-imoveis-01.xml.gz</loc></sitemap>
<sitemap><loc>https://www.chavesnamao.com.br/sitemap-aluguel-imoveis-01.xml.gz</loc></sitemap>
<sitemap><loc>https://www.chavesnamao.com.br/sitemap-venda-cidades-bairros.xml.gz</loc></sitemap>
</sitemapindex>"""

URL_CURITIBA_VENDA = (
    "https://www.chavesnamao.com.br/imovel/"
    "apartamento-a-venda-2-quartos-com-garagem-pr-curitiba-campo-comprido-"
    "65m2-RS379000/id-45712812/"
)
URL_OUTRA_CIDADE = (
    "https://www.chavesnamao.com.br/imovel/"
    "casa-a-venda-3-quartos-com-garagem-rj-niteroi-piratininga-"
    "220m2-RS980000/id-45713958/"
)


def _sitemap_gz(urls: list[str]) -> bytes:
    itens = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0"?><urlset>{itens}</urlset>'
    return gzip.compress(xml.encode("utf-8"))


DETALHE_HTML_MINIMO = """
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"RealEstateListing",
"description":"3\\u00ba andar, apto conservado",
"about":{"offers":{"price":379000}}}]}
</script>
<p aria-label="area-util"><b>65 m2</b></p>
<p aria-label="Quartos"><b>2</b></p>
<p aria-label="Banheiros"><b>1</b></p>
<p aria-label="Garagens"><b>1</b></p>
<span class="row spacing"><p>Condomínio</p><p>R$ 450</p></span>
<span class="row spacing"><p>IPTU</p><p>R$ 800</p></span>
</body></html>
"""


class FakeResponse:
    def __init__(self, text: str = "", content: bytes = b""):
        self.text = text
        self.content = content

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self):
        self.headers: dict[str, str] = {}
        self.urls_requisitadas: list[str] = []

    def get(self, url: str, timeout: int | None = None, stream: bool = False):
        self.urls_requisitadas.append(url)
        if url.endswith("sitemap-index.xml"):
            return FakeResponse(text=SITEMAP_INDEX_XML)
        if "sitemap-venda-imoveis-01" in url:
            return FakeResponse(content=_sitemap_gz([URL_CURITIBA_VENDA, URL_OUTRA_CIDADE]))
        if "sitemap-aluguel-imoveis-01" in url:
            return FakeResponse(content=_sitemap_gz([]))
        return FakeResponse(text=DETALHE_HTML_MINIMO)


def test_fetch_filtra_sitemaps_de_anuncio_individual_ignora_categoria(tmp_path):
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)

    connector.fetch()

    urls_sitemap_requisitadas = [u for u in fake.urls_requisitadas if u.endswith(".xml.gz")]
    assert any("venda-imoveis-01" in u for u in urls_sitemap_requisitadas)
    assert any("aluguel-imoveis-01" in u for u in urls_sitemap_requisitadas)
    # sitemap-venda-cidades-bairros.xml.gz é página de categoria, não de
    # anúncio individual - nunca deveria ser buscado.
    assert not any("cidades-bairros" in u for u in urls_sitemap_requisitadas)


def test_fetch_filtra_apenas_curitiba(tmp_path):
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)

    snapshot = connector.fetch()

    assert snapshot.conteudo == [URL_CURITIBA_VENDA]


def test_normalize_monta_entidade_e_observacao(tmp_path):
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)
    snapshot = RawSnapshot(
        fonte_id="chavesnamao_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA_VENDA],
    )

    registros = list(
        connector.normalize(
            snapshot,
            observado_em=date(2026, 8, 15),
            territorio_id_por_slug={"campo-comprido": "curitiba-bairro-campo-comprido"},
        )
    )

    assert len(registros) == 1
    r = registros[0]
    assert r.entidade.tipo_entidade == "anuncio_imovel"
    assert r.observacao.operacao == "venda"
    assert r.observacao.tipologia == "apartamento"
    assert r.observacao.preco == 379000.0
    assert r.observacao.condominio == 450.0
    assert r.observacao.iptu == 800.0
    assert r.observacao.quartos == 2
    assert r.observacao.vagas == 1
    assert r.observacao.andar == 3
    assert r.observacao.territorio_id == "curitiba-bairro-campo-comprido"
    assert r.observacao.impressao_digital


def test_normalize_bairro_nao_resolvido_ainda_gera_impressao_digital_por_slug(tmp_path):
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)
    snapshot = RawSnapshot(
        fonte_id="chavesnamao_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA_VENDA],
    )

    registros = list(
        connector.normalize(snapshot, observado_em=date(2026, 8, 15), territorio_id_por_slug={})
    )

    assert len(registros) == 1
    assert registros[0].observacao.territorio_id is None
    assert registros[0].observacao.impressao_digital  # não fica vazia


def test_normalize_respeita_ja_coletados(tmp_path):
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)
    snapshot = RawSnapshot(
        fonte_id="chavesnamao_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA_VENDA],
    )

    registros = list(
        connector.normalize(
            snapshot,
            observado_em=date(2026, 8, 15),
            territorio_id_por_slug={},
            ja_coletados={"45712812"},
        )
    )

    assert registros == []


def test_normalize_respeita_limite(tmp_path):
    url2 = URL_CURITIBA_VENDA.replace("45712812", "45712813")
    fake = FakeSession()
    connector = ChavesNaMaoAnunciosConnector(session=fake, raw_dir=tmp_path, intervalo_minimo_s=0)
    snapshot = RawSnapshot(
        fonte_id="chavesnamao_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA_VENDA, url2],
    )

    registros = list(
        connector.normalize(
            snapshot, observado_em=date(2026, 8, 15), territorio_id_por_slug={}, limite=1
        )
    )

    assert len(registros) == 1
