from datetime import date

import pytest

from domain.contexto import IndicadorFipezapBairro, IndicadorFipezapCidade
from infrastructure.connectors.fipezap.connector import FipezapConnector
from infrastructure.connectors.base import RawSnapshot


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class _FakeSession:
    """Simula o servidor da Fipe: só o `ano_mes` em `meses_disponiveis`
    devolve 200 para venda/locação, qualquer outro devolve 404 - mesmo
    padrão do conector real, sem rede."""

    def __init__(self, meses_disponiveis: set[str]) -> None:
        self.headers: dict[str, str] = {}
        self._meses_disponiveis = meses_disponiveis
        self.urls_chamadas: list[str] = []

    def get(self, url: str, timeout: int):
        self.urls_chamadas.append(url)
        for ano_mes in self._meses_disponiveis:
            if ano_mes in url:
                return _FakeResponse(200, content=f"pdf-{url}".encode())
        return _FakeResponse(404)


def test_fetch_resolve_mes_mais_recente_disponivel(tmp_path):
    hoje = date.today()
    ano_mes_atual = f"{hoje.year:04d}{hoje.month:02d}"
    session = _FakeSession(meses_disponiveis={ano_mes_atual})
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo.periodo_referencia == date(hoje.year, hoje.month, 1)
    assert set(snapshot.conteudo.pdfs_por_operacao) == {"venda", "locacao"}


def test_fetch_retrocede_meses_ate_achar_relatorio_publicado(tmp_path):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    # mês atual (ainda não publicado) e o anterior tb não - só 2 meses atrás
    for _ in range(2):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    ano_mes_disponivel = f"{ano:04d}{mes:02d}"

    session = _FakeSession(meses_disponiveis={ano_mes_disponivel})
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo.periodo_referencia == date(ano, mes, 1)


def test_fetch_levanta_erro_se_nenhum_mes_recente_disponivel(tmp_path):
    session = _FakeSession(meses_disponiveis=set())
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    with pytest.raises(RuntimeError):
        connector.fetch()


class _FakeSessionComErroTransitorio:
    """Simula o achado real: um 403 nas primeiras N tentativas, depois
    200 - sem sleep de verdade no teste (monkeypatch de time.sleep)."""

    def __init__(self, falhas_antes_de_sucesso: int, status_falha: int = 403) -> None:
        self.headers: dict[str, str] = {}
        self._falhas_restantes = falhas_antes_de_sucesso
        self._status_falha = status_falha
        self.chamadas = 0

    def get(self, url: str, timeout: int):
        self.chamadas += 1
        if self._falhas_restantes > 0:
            self._falhas_restantes -= 1
            return _FakeResponse(self._status_falha)
        return _FakeResponse(200, content=b"pdf-conteudo")


def test_baixar_com_retentativa_recupera_de_erro_transitorio(tmp_path, monkeypatch):
    monkeypatch.setattr("infrastructure.connectors.fipezap.connector.time.sleep", lambda s: None)
    session = _FakeSessionComErroTransitorio(falhas_antes_de_sucesso=2)
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    conteudo = connector._baixar_com_retentativa("https://exemplo/qualquer.pdf")

    assert conteudo == b"pdf-conteudo"
    assert session.chamadas == 3


def test_baixar_com_retentativa_desiste_apos_max_tentativas(tmp_path, monkeypatch):
    monkeypatch.setattr("infrastructure.connectors.fipezap.connector.time.sleep", lambda s: None)
    session = _FakeSessionComErroTransitorio(falhas_antes_de_sucesso=999, status_falha=500)
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    with pytest.raises(Exception):
        connector._baixar_com_retentativa("https://exemplo/qualquer.pdf")


def test_fetch_salva_raw_zone_e_referencia_snapshot(tmp_path):
    hoje = date.today()
    ano_mes_atual = f"{hoje.year:04d}{hoje.month:02d}"
    session = _FakeSession(meses_disponiveis={ano_mes_atual})
    connector = FipezapConnector(session=session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert (tmp_path / ano_mes_atual / "venda.pdf").exists()
    assert (tmp_path / ano_mes_atual / "locacao.pdf").exists()
    assert snapshot.snapshot_ref == str(tmp_path / ano_mes_atual)


PAGINAS_VENDA_FAKE = [
    "SUMÁRIO\n...",
    (
        "DESTAQUES DO MÊS\n"
        "Curitiba(+0,08%)paragrafomensal.\n"
        "Curitiba(+0,32%)paragrafoano.\n"
        "Curitiba(+3,85%)paragrafo12meses.\n"
        "Curitiba(R$11.761/m²)precomedio."
    ),
    "CURITIBA (PR)\nBATEL R$ 17.525 /m² -0,8%\nCENTRO R$ 11.159 /m² +6,1%",
]

PAGINAS_LOCACAO_FAKE = [
    "SUMÁRIO\n...",
    (
        "DESTAQUES DO MÊS\n"
        "Curitiba(+0,57%)paragrafomensal.\n"
        "Curitiba(+5,14%)paragrafoano.\n"
        "Curitiba(+9,17%)paragrafo12meses.\n"
        "Curitiba(R$48,91/m²)precomedio."
    ),
    "CURITIBA (PR)\nBATEL R$ 54,2 /m² +24,7%\nCENTRO R$ 52,8 /m² +9,9%",
]


def _fake_extrator(pdf_bytes: bytes) -> list[str]:
    if b"venda" in pdf_bytes:
        return PAGINAS_VENDA_FAKE
    return PAGINAS_LOCACAO_FAKE


def test_normalize_monta_indicadores_cidade_e_bairro_das_duas_operacoes():
    connector = FipezapConnector(extrator_paginas=_fake_extrator)
    snapshot = RawSnapshot(
        fonte_id="fipezap",
        capturado_em=None,
        snapshot_ref="data/raw/fipezap/202607",
        conteudo=_snapshot_fake(),
    )

    resultado = connector.normalize(snapshot, territorio_id_por_slug={})

    cidades = [r for r in resultado if isinstance(r, IndicadorFipezapCidade)]
    bairros = [r for r in resultado if isinstance(r, IndicadorFipezapBairro)]
    assert {c.operacao for c in cidades} == {"venda", "locacao"}
    assert len(bairros) == 4  # 2 bairros x 2 operações
    venda_cidade = next(c for c in cidades if c.operacao == "venda")
    assert venda_cidade.preco_medio_m2 == 11761.0


def test_normalize_resolve_territorio_id_dos_bairros():
    connector = FipezapConnector(extrator_paginas=_fake_extrator)
    snapshot = RawSnapshot(
        fonte_id="fipezap",
        capturado_em=None,
        snapshot_ref="data/raw/fipezap/202607",
        conteudo=_snapshot_fake(),
    )

    resultado = connector.normalize(
        snapshot, territorio_id_por_slug={"batel": "curitiba-bairro-batel"}
    )

    bairros = [r for r in resultado if isinstance(r, IndicadorFipezapBairro)]
    batel = next(b for b in bairros if b.bairro_nome == "BATEL" and b.operacao == "venda")
    assert batel.territorio_id == "curitiba-bairro-batel"


def _snapshot_fake():
    from infrastructure.connectors.fipezap.connector import SnapshotFipezap

    return SnapshotFipezap(
        periodo_referencia=date(2026, 7, 1),
        pdfs_por_operacao={"venda": b"pdf-venda-conteudo", "locacao": b"pdf-locacao-conteudo"},
    )
