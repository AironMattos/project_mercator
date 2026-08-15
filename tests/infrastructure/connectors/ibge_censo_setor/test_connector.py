import zipfile
from datetime import datetime, timezone

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.ibge_censo_setor.connector import IbgeCensoSetorConnector

CSV_HEADER = (
    '"CD_SETOR";"SITUACAO";"CD_SIT";"CD_TIPO";"AREA_KM2";"CD_REGIAO";"NM_REGIAO";'
    '"CD_UF";"NM_UF";"CD_MUN";"NM_MUN";"CD_DIST";"NM_DIST";"CD_SUBDIST";"NM_SUBDIST";'
    '"CD_BAIRRO";"NM_BAIRRO";"v0001";"v0002";"v0003";"v0004";"v0005";"v0006";'
    '"v0007";"v0008";"v0009"\n'
)


def _linha_curitiba(cd_setor="410690205010001", nm_bairro="Centro"):
    return (
        f'"{cd_setor}";"Urbana";"1";"0";"0,0696899";"2";"Sul";"41";"Paraná";'
        f'"4106902";"Curitiba";"410690205";"Curitiba";"41069020500";"";'
        f'"4106902001";"{nm_bairro}";"496";"361";"361";"0";"1,4";"0,0000";'
        f'"242";"20";"86"\n'
    )


def _linha_outro_municipio():
    return (
        '"110001505000002";"Urbana";"1";"0";"0,5393102";"1";"Norte";"11";'
        '"Rondônia";"1100015";"Alta Floresta D\'Oeste";"110001505";'
        '"Alta Floresta D\'Oeste";"11000150500";"";"1100015006";"Redondo";'
        '"376";"376";"376";"0";"2,8";"0,0923";"336";"11";"29"\n'
    )


def _criar_zip(tmp_path, csv_content: str, nome_zip="Agregados_por_setores_basico_BR.zip") -> str:
    zip_path = tmp_path / nome_zip
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Agregados_por_setores_basico_BR.csv", csv_content.encode("latin-1"))
    return str(zip_path)


class FakeListagemResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSessionListagem:
    """Só resolve o nome do arquivo mais recente via listagem HTML - o
    download em si é substituído nos testes que não precisam dele."""

    def __init__(self, html: str):
        self._html = html

    def get(self, url: str, timeout: int | None = None):
        return FakeListagemResponse(self._html)


def test_arquivo_mais_recente_extrai_nome_com_data_da_listagem():
    html = 'antes <a href="Agregados_por_setores_basico_BR_20260520.zip">x</a> depois'
    connector = IbgeCensoSetorConnector(session=FakeSessionListagem(html))

    nome = connector._arquivo_mais_recente()

    assert nome == "Agregados_por_setores_basico_BR_20260520.zip"


def test_normalize_filtra_apenas_curitiba(tmp_path):
    csv_content = CSV_HEADER + _linha_curitiba() + _linha_outro_municipio()
    zip_path = _criar_zip(tmp_path, csv_content)
    connector = IbgeCensoSetorConnector()
    snapshot = RawSnapshot(
        fonte_id="ibge_censo_setor",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref=zip_path,
        conteudo=zip_path,
    )

    setores = connector.normalize(snapshot)

    assert len(setores) == 1
    assert setores[0].municipio_codigo == "4106902"


def test_normalize_converte_area_km2_de_decimal_virgula(tmp_path):
    csv_content = CSV_HEADER + _linha_curitiba()
    zip_path = _criar_zip(tmp_path, csv_content)
    connector = IbgeCensoSetorConnector()
    snapshot = RawSnapshot(
        fonte_id="ibge_censo_setor",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref=zip_path,
        conteudo=zip_path,
    )

    setores = connector.normalize(snapshot)

    assert setores[0].area_km2 == 0.0696899


def test_normalize_resolve_territorio_id_por_slug_de_bairro(tmp_path):
    csv_content = CSV_HEADER + _linha_curitiba(nm_bairro="Centro")
    zip_path = _criar_zip(tmp_path, csv_content)
    connector = IbgeCensoSetorConnector()
    snapshot = RawSnapshot(
        fonte_id="ibge_censo_setor",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref=zip_path,
        conteudo=zip_path,
    )

    setores = connector.normalize(
        snapshot, territorio_id_por_slug={"centro": "curitiba-bairro-centro"}
    )

    assert setores[0].territorio_id == "curitiba-bairro-centro"


def test_normalize_bairro_sem_correspondencia_fica_sem_territorio_id(tmp_path):
    csv_content = CSV_HEADER + _linha_curitiba(nm_bairro="Botiatuvinha")
    zip_path = _criar_zip(tmp_path, csv_content)
    connector = IbgeCensoSetorConnector()
    snapshot = RawSnapshot(
        fonte_id="ibge_censo_setor",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref=zip_path,
        conteudo=zip_path,
    )

    setores = connector.normalize(
        snapshot, territorio_id_por_slug={"butiatuvinha": "curitiba-bairro-butiatuvinha"}
    )

    assert setores[0].territorio_id is None


def test_normalize_mapeia_contagens_de_domicilios_e_populacao(tmp_path):
    csv_content = CSV_HEADER + _linha_curitiba()
    zip_path = _criar_zip(tmp_path, csv_content)
    connector = IbgeCensoSetorConnector()
    snapshot = RawSnapshot(
        fonte_id="ibge_censo_setor",
        capturado_em=datetime.now(timezone.utc),
        snapshot_ref=zip_path,
        conteudo=zip_path,
    )

    setores = connector.normalize(snapshot)

    s = setores[0]
    assert s.populacao_total == 496
    assert s.domicilios_total == 361
    assert s.domicilios_particulares_ocupados == 242
    assert s.domicilios_particulares_vagos == 86
    assert s.ano_referencia == 2022
