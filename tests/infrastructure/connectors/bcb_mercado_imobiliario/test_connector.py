from datetime import datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.bcb_mercado_imobiliario.connector import (
    BcbMercadoImobiliarioConnector,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Responde por Info exato, imitando o filtro $filter=Info eq '...'
    que o conector monta - dados fixos só para os indicadores usados nos
    testes, lista vazia para o resto (imita a série existir mas sem
    leitura no período consultado)."""

    def __init__(self, dados_por_info: dict[str, list[dict]]):
        self._dados_por_info = dados_por_info
        self.infos_requisitados: list[str] = []

    def get(self, url: str, timeout: int | None = None):
        info = url.split("'")[1]
        self.infos_requisitados.append(info)
        return FakeResponse({"value": self._dados_por_info.get(info, [])})


def test_fetch_consulta_as_14_series_catalogadas_com_sufixo_de_uf(tmp_path):
    fake_session = FakeSession({})
    connector = BcbMercadoImobiliarioConnector(uf="PR", session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert len(fake_session.infos_requisitados) == 14
    assert all(info.endswith("_pr") for info in fake_session.infos_requisitados)
    assert snapshot.conteudo["leituras"] == []


def test_normalize_valor_avaliacao_vira_categoria_valor_tipo_avaliacao():
    connector = BcbMercadoImobiliarioConnector(uf="PR")
    snapshot = RawSnapshot(
        fonte_id="bcb_mercado_imobiliario",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "uf": "PR",
            "leituras": [{"Data": "2026-04-30", "Info": "imoveis_valor_avaliacao_pr", "Valor": 300000}],
        },
    )

    indicadores = connector.normalize(snapshot)

    assert len(indicadores) == 1
    i = indicadores[0]
    assert i.categoria == "valor"
    assert i.tipo_valor == "avaliacao"
    assert i.leitura == 300000.0
    assert i.unidade == "R$"


def test_normalize_valor_compra_vira_tipo_valor_transacao_nao_avaliacao():
    # Achado do checkpoint 11d (Metodologia.pdf oficial do BCB): "compra"
    # é o preço efetivamente contratado na aquisição, não uma segunda
    # avaliação - por isso mapeado para 'transacao', nunca 'avaliacao'.
    connector = BcbMercadoImobiliarioConnector(uf="PR")
    snapshot = RawSnapshot(
        fonte_id="bcb_mercado_imobiliario",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "uf": "PR",
            "leituras": [{"Data": "2026-04-30", "Info": "imoveis_valor_compra_pr", "Valor": 290000}],
        },
    )

    indicadores = connector.normalize(snapshot)

    assert indicadores[0].tipo_valor == "transacao"


def test_normalize_indicador_de_contagem_nao_carrega_tipo_valor():
    connector = BcbMercadoImobiliarioConnector(uf="PR")
    snapshot = RawSnapshot(
        fonte_id="bcb_mercado_imobiliario",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "uf": "PR",
            "leituras": [{"Data": "2026-04-30", "Info": "imoveis_dormitorio_1_pr", "Valor": 247}],
        },
    )

    indicadores = connector.normalize(snapshot)

    assert indicadores[0].categoria == "contagem"
    assert indicadores[0].tipo_valor is None
    assert indicadores[0].unidade == "imóveis"


def test_normalize_ignora_serie_nao_catalogada():
    connector = BcbMercadoImobiliarioConnector(uf="PR")
    snapshot = RawSnapshot(
        fonte_id="bcb_mercado_imobiliario",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "uf": "PR",
            "leituras": [{"Data": "2026-04-30", "Info": "credito_estoque_carteira_credito_pj_livre_pr", "Valor": 1.0}],
        },
    )

    indicadores = connector.normalize(snapshot)

    assert indicadores == []


def test_normalize_ignora_serie_com_sufixo_de_uf_diferente():
    connector = BcbMercadoImobiliarioConnector(uf="PR")
    snapshot = RawSnapshot(
        fonte_id="bcb_mercado_imobiliario",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo={
            "uf": "PR",
            "leituras": [{"Data": "2026-04-30", "Info": "imoveis_valor_avaliacao_sp", "Valor": 1.0}],
        },
    )

    indicadores = connector.normalize(snapshot)

    assert indicadores == []
