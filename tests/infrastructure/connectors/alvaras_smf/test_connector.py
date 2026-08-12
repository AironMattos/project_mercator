from datetime import date
from pathlib import Path

from infrastructure.connectors.alvaras_smf.connector import AlvarasSmfConnector
from infrastructure.connectors.base import RawSnapshot

DIRETORIO_HTML = """
<html><body>
<a href="2026-06-01_Alvaras_-_Base_de_Dados.csv">2026-06-01_Alvaras_-_Base_de_Dados.csv</a>
<a href="2026-06-01_Alvaras_-_Dicionario_de_Dados.csv">dicionario</a>
<a href="2026-07-01_Alvaras_-_Base_de_Dados.csv">2026-07-01_Alvaras_-_Base_de_Dados.csv</a>
<a href="2026-08-01_Alvaras_-_Base_de_Dados.csv">2026-08-01_Alvaras_-_Base_de_Dados.csv</a>
</body></html>
"""

CSV_CONTEUDO = (
    "NOME_EMPRESARIAL;INICIO_ATIVIDADE;NUMERO_DO_ALVARA;NOME_FANTASIA;DATA_EMISSAO;"
    "DATA_EXPIRACAO;ENDERECO;NUMERO;UNIDADE;ANDAR;COMPLEMENTO;BAIRRO;CEP;"
    "CNAE_ATIVIDADE_PRINCIPAL;ATIVIDADE_PRINCIPAL\n"
    "SONIA MARIA;29/05/2013;1133631;***;29/05/2013;***;R. DEP. VIDAL;001403;***;***;"
    "***;TATUQUARA;81470000;5-70.20.00;CABELEIREIRO\n"
    "JOAO DA SILVA;01/01/2020;9999999;***;01/01/2020;***;R. X;10;***;***;"
    "***;BAIRRO INEXISTENTE XYZ;80000000;1-11.11.11;PADARIA\n"
    "LINHA SEM ALVARA;01/01/2020;***;***;01/01/2020;***;R. Y;10;***;***;"
    "***;CENTRO;80000000;1-11.11.11;PADARIA\n"
)


class FakeStreamResponse:
    def __init__(self, content: bytes, headers: dict | None = None):
        self._content = content
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeTextResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, diretorio_html: str, csv_bytes: bytes):
        self._diretorio_html = diretorio_html
        self._csv_bytes = csv_bytes
        self.urls_requisitadas: list[str] = []

    def get(self, url: str, **kwargs):
        self.urls_requisitadas.append(url)
        if url.endswith(".csv"):
            return FakeStreamResponse(
                self._csv_bytes, headers={"Content-Length": str(len(self._csv_bytes))}
            )
        return FakeTextResponse(self._diretorio_html)


def test_arquivo_mais_recente_escolhe_o_mes_mais_novo():
    session = FakeSession(DIRETORIO_HTML, b"")
    connector = AlvarasSmfConnector(session=session)
    assert connector._arquivo_mais_recente() == "2026-08-01_Alvaras_-_Base_de_Dados.csv"


def test_fetch_baixa_em_streaming_e_resolve_data_de_referencia(tmp_path):
    conteudo = CSV_CONTEUDO.encode("latin-1")
    session = FakeSession(DIRETORIO_HTML, conteudo)
    connector = AlvarasSmfConnector(session=session, raw_dir=tmp_path)

    snapshot = connector.fetch()

    assert snapshot.conteudo["observado_em"] == date(2026, 8, 1)
    destino = Path(snapshot.conteudo["path"])
    assert destino.exists()
    assert destino.read_bytes() == conteudo


def test_normalize_resolve_bairro_e_ignora_linha_sem_alvara(tmp_path):
    csv_path = tmp_path / "amostra.csv"
    csv_path.write_bytes(CSV_CONTEUDO.encode("latin-1"))

    connector = AlvarasSmfConnector()
    snapshot = RawSnapshot(
        fonte_id="alvaras_smf",
        capturado_em=None,
        snapshot_ref=str(csv_path),
        conteudo={"path": str(csv_path), "observado_em": date(2026, 8, 1)},
    )

    lookup = {"tatuquara": "curitiba-bairro-tatuquara", "centro": "curitiba-bairro-centro"}
    registros = list(connector.normalize(snapshot, lookup))

    # a linha "LINHA SEM ALVARA" (NUMERO_DO_ALVARA == "***") deve ser ignorada
    assert len(registros) == 2

    r0 = registros[0]
    assert r0.entidade.identificador_fonte == "1133631"
    assert r0.territorio_id == "curitiba-bairro-tatuquara"
    assert r0.observacao.atributos["bairro"] == "TATUQUARA"
    assert r0.observacao.atributos["territorio_id"] == "curitiba-bairro-tatuquara"
    assert r0.observacao.entidade_id == r0.entidade.entidade_id
    assert r0.observacao.observado_em == date(2026, 8, 1)

    r1 = registros[1]
    assert r1.territorio_id is None  # "BAIRRO INEXISTENTE XYZ" não casa
    assert r1.observacao.atributos["bairro"] == "BAIRRO INEXISTENTE XYZ"


def test_normalize_sem_lookup_deixa_territorio_id_none(tmp_path):
    csv_path = tmp_path / "amostra.csv"
    csv_path.write_bytes(CSV_CONTEUDO.encode("latin-1"))

    connector = AlvarasSmfConnector()
    snapshot = RawSnapshot(
        fonte_id="alvaras_smf",
        capturado_em=None,
        snapshot_ref=str(csv_path),
        conteudo={"path": str(csv_path), "observado_em": date(2026, 8, 1)},
    )

    registros = list(connector.normalize(snapshot))
    assert all(r.territorio_id is None for r in registros)
