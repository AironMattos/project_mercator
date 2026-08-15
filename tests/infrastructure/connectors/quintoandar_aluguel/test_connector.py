from datetime import datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.quintoandar_aluguel.connector import QuintoandarAluguelConnector

CSV_EXEMPLO = (
    "ts_date,city_name,house_room,est_price,chg,acum12m\n"
    "2019-03-01,cur,city,,,\n"
    "2025-08-01,cur,city,45.9983509082252,0.00434683230341482,0.150319923570635\n"
    "2025-08-01,cur,1,63.8511141436587,-0.0155288635336723,0.116469412607861\n"
    "2025-08-01,bhe,city,20.7813404950228,0.0130658747194423,0.0911680083073341\n"
)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, text: str):
        self._text = text
        self.urls_requisitadas: list[str] = []

    def get(self, url: str, timeout: int | None = None):
        self.urls_requisitadas.append(url)
        return FakeResponse(self._text)


def test_fetch_baixa_e_salva_o_csv_bruto(tmp_path):
    fake_session = FakeSession(CSV_EXEMPLO)
    connector = QuintoandarAluguelConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo == CSV_EXEMPLO
    assert len(list(tmp_path.iterdir())) == 1


def test_normalize_filtra_apenas_curitiba():
    connector = QuintoandarAluguelConnector()
    snapshot = RawSnapshot(
        fonte_id="quintoandar_indice_aluguel",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=CSV_EXEMPLO,
    )

    indicadores = connector.normalize(snapshot)

    assert all(i.cidade == "Curitiba" for i in indicadores)
    # bhe (Belo Horizonte) e a linha de cur sem est_price ficam de fora.
    assert len(indicadores) == 2


def test_normalize_mapeia_house_room_para_segmento():
    connector = QuintoandarAluguelConnector()
    snapshot = RawSnapshot(
        fonte_id="quintoandar_indice_aluguel",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=CSV_EXEMPLO,
    )

    indicadores = {i.segmento: i for i in connector.normalize(snapshot)}

    assert indicadores["cidade_toda"].aluguel_m2 == 45.9983509082252
    assert indicadores["1_dormitorio"].aluguel_m2 == 63.8511141436587


def test_normalize_linha_sem_est_price_e_ignorada():
    connector = QuintoandarAluguelConnector()
    snapshot = RawSnapshot(
        fonte_id="quintoandar_indice_aluguel",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=CSV_EXEMPLO,
    )

    indicadores = connector.normalize(snapshot)

    assert all(i.periodo_referencia.isoformat() != "2019-03-01" for i in indicadores)


def test_normalize_chg_e_acum12m_vazios_viram_none():
    connector = QuintoandarAluguelConnector()
    csv_com_vazios = (
        "ts_date,city_name,house_room,est_price,chg,acum12m\n"
        "2019-05-01,cur,city,19.1577987758467,,\n"
    )
    snapshot = RawSnapshot(
        fonte_id="quintoandar_indice_aluguel",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref="memoria",
        conteudo=csv_com_vazios,
    )

    indicadores = connector.normalize(snapshot)

    assert indicadores[0].variacao_mensal is None
    assert indicadores[0].variacao_12m is None
