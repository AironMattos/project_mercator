from datetime import date, datetime, timezone
from pathlib import Path

from infrastructure.connectors.apolar_anuncios.connector import ApolarAnunciosConnector
from infrastructure.connectors.base import RawSnapshot

FIXTURES = Path(__file__).parent / "fixtures"

SITEMAP_XML = """<?xml version="1.0"?>
<urlset>
<url><loc>https://www.apolar.com.br/alugar/curitiba/sitio-cercado/alugar-residencial-apartamento-curitiba-sitio-cercado-100127</loc></url>
<url><loc>https://www.apolar.com.br/alugar/curitiba/sitio-cercado</loc></url>
<url><loc>https://www.apolar.com.br/alugar/almirante-tamandare/jardim-ipanema/alugar-residencial-apartamento-almirante-tamandare-jardim-ipanema-100283</loc></url>
</urlset>"""

URL_CURITIBA = (
    "https://www.apolar.com.br/alugar/curitiba/sitio-cercado/"
    "alugar-residencial-apartamento-curitiba-sitio-cercado-100127"
)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, text: str):
        self._text = text
        self.headers: dict[str, str] = {}
        self.urls_requisitadas: list[str] = []

    def get(self, url: str, timeout: int | None = None):
        self.urls_requisitadas.append(url)
        return FakeResponse(self._text)


def _renderizador_fake(html: str):
    chamadas: list[str] = []

    def renderizar(url: str) -> str:
        chamadas.append(url)
        return html

    renderizar.chamadas = chamadas  # type: ignore[attr-defined]
    renderizar.fechado = False  # type: ignore[attr-defined]

    def fechar() -> None:
        renderizar.fechado = True  # type: ignore[attr-defined]

    renderizar.fechar = fechar  # type: ignore[attr-defined]
    return renderizar


def test_fetch_filtra_paginas_de_detalhe_de_curitiba(tmp_path):
    fake_session = FakeSession(SITEMAP_XML)
    connector = ApolarAnunciosConnector(session=fake_session, raw_dir=tmp_path, intervalo_minimo_s=0)

    snapshot = connector.fetch()

    assert snapshot.conteudo == [URL_CURITIBA]  # categoria e outra cidade ficam de fora


def test_normalize_usa_renderizador_injetado_e_fecha_ao_final(tmp_path):
    html = (FIXTURES / "detalhe_aluguel_apartamento.html").read_text(encoding="utf-8")
    fake_renderizador = _renderizador_fake(html)
    connector = ApolarAnunciosConnector(raw_dir=tmp_path, intervalo_minimo_s=0, renderizador=fake_renderizador)
    snapshot = RawSnapshot(
        fonte_id="apolar_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA],
    )

    registros = list(
        connector.normalize(
            snapshot,
            observado_em=date(2026, 8, 15),
            territorio_id_por_slug={"sitio-cercado": "curitiba-bairro-sitio-cercado"},
        )
    )

    assert len(registros) == 1
    r = registros[0]
    assert r.entidade.tipo_entidade == "anuncio_imovel"
    assert r.observacao.operacao == "aluguel"
    assert r.observacao.tipologia == "apartamento"
    assert r.observacao.preco == 1100.0
    assert r.observacao.condominio == 550.0
    assert r.observacao.iptu == 23.79
    assert r.observacao.quartos == 2
    assert r.observacao.vagas == 1
    assert r.observacao.andar == 1
    assert r.observacao.territorio_id == "curitiba-bairro-sitio-cercado"
    assert fake_renderizador.chamadas == [URL_CURITIBA]
    assert fake_renderizador.fechado is True


def test_normalize_sem_area_util_gera_impressao_digital_unica_nao_resolvivel(tmp_path):
    html_sem_area = "<html><body><div class='price-box'><div class='price-new'>R$ 500,00</div></div></body></html>"
    fake_renderizador = _renderizador_fake(html_sem_area)
    connector = ApolarAnunciosConnector(raw_dir=tmp_path, intervalo_minimo_s=0, renderizador=fake_renderizador)
    snapshot = RawSnapshot(
        fonte_id="apolar_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA],
    )

    registros = list(
        connector.normalize(snapshot, observado_em=date(2026, 8, 15), territorio_id_por_slug={})
    )

    assert len(registros) == 1
    assert registros[0].observacao.impressao_digital == "sem-fp:100127"


def test_normalize_respeita_ja_coletados_e_limite(tmp_path):
    html = (FIXTURES / "detalhe_aluguel_apartamento.html").read_text(encoding="utf-8")
    fake_renderizador = _renderizador_fake(html)
    connector = ApolarAnunciosConnector(raw_dir=tmp_path, intervalo_minimo_s=0, renderizador=fake_renderizador)
    outra_url = URL_CURITIBA.replace("100127", "100128")
    snapshot = RawSnapshot(
        fonte_id="apolar_anuncios",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=[URL_CURITIBA, outra_url],
    )

    registros = list(
        connector.normalize(
            snapshot,
            observado_em=date(2026, 8, 15),
            territorio_id_por_slug={},
            ja_coletados={"100127"},
        )
    )

    assert len(registros) == 1
    assert fake_renderizador.chamadas == [outra_url]
