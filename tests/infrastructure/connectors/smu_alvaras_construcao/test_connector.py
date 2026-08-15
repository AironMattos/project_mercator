from datetime import date

from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.smu_alvaras_construcao.connector import (
    AlvaraConstrucaoConnector,
    CvcoConnector,
)

FORM_HTML = """
<html><body><form>
<input type="hidden" id="__VIEWSTATE" value="VS123" />
<input type="hidden" id="__VIEWSTATEGENERATOR" value="GEN456" />
<input type="hidden" id="__EVENTVALIDATION" value="EV789" />
</form></body></html>
"""


def _tabela_html(numero_alvara="417418", indicacao_fiscal="38.033.021"):
    header = "<tr>" + "<td>h</td>" * 34 + "</tr>"
    valores = ["&nbsp;"] * 34
    valores[0] = indicacao_fiscal
    valores[13] = numero_alvara
    linha = "<tr>" + "".join(f"<td>{v}</td>" for v in valores) + "</tr>"
    return f"<table>{header}{linha}</table>"


class FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.encoding = "ISO-8859-1"

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, tabela_html: str):
        self.posts: list[dict] = []
        self._tabela_html = tabela_html

    def get(self, url, timeout=None):
        assert url.endswith("relatoriomensalalvara.aspx")
        return FakeResponse(FORM_HTML)

    def post(self, url, data=None, timeout=None):
        assert url.endswith("Default.aspx")
        self.posts.append(data)
        return FakeResponse(self._tabela_html)


def test_fetch_extrai_campos_ocultos_e_faz_postback_correto(tmp_path):
    fake_session = FakeSession(_tabela_html())
    connector = AlvaraConstrucaoConnector(session=fake_session, raw_dir=tmp_path)

    snapshot = connector.fetch(ano=2026, mes_inicio=1, mes_fim=7)

    assert len(fake_session.posts) == 1
    payload = fake_session.posts[0]
    assert payload["__VIEWSTATE"] == "VS123"
    assert payload["__VIEWSTATEGENERATOR"] == "GEN456"
    assert payload["__EVENTVALIDATION"] == "EV789"
    assert payload["rblRelacao"] == "1"
    assert payload["ddlAno"] == "2026"
    assert payload["ddlMes"] == "1"
    assert payload["ddlMesFinal"] == "7"
    assert snapshot.conteudo["observado_em"] == date(2026, 1, 1)


def test_fetch_cvco_usa_rblrelacao_2():
    fake_session = FakeSession(_tabela_html())
    connector = CvcoConnector(session=fake_session)

    connector.fetch(ano=2026, mes_inicio=1, mes_fim=7)

    assert fake_session.posts[0]["rblRelacao"] == "2"


def test_normalize_produz_entidade_obra_e_observacao():
    connector = AlvaraConstrucaoConnector()
    snapshot = RawSnapshot(
        fonte_id="smu_alvara_construcao",
        capturado_em=None,
        snapshot_ref="memoria",
        conteudo={"html": _tabela_html(numero_alvara="999888"), "observado_em": date(2026, 1, 1)},
    )

    registros = list(connector.normalize(snapshot))

    assert len(registros) == 1
    r = registros[0]
    assert r.entidade.tipo_entidade == "obra"
    assert r.entidade.identificador_fonte == "999888"
    assert r.observacao.atributos["numero_alvara"] == "999888"
    assert r.observacao.fonte_id == "smu_alvara_construcao"


def test_normalize_resolve_territorio_id_por_indicacao_fiscal():
    connector = AlvaraConstrucaoConnector()
    snapshot = RawSnapshot(
        fonte_id="smu_alvara_construcao",
        capturado_em=None,
        snapshot_ref="memoria",
        conteudo={
            "html": _tabela_html(indicacao_fiscal="38.033.021"),
            "observado_em": date(2026, 1, 1),
        },
    )

    registros = list(
        connector.normalize(
            snapshot,
            # chave normalizada (só dígitos) - o conector remove os pontos
            # da Indicação Fiscal antes de consultar o lookup (achado real
            # do checkpoint 11c: lote_cadastral guarda sem pontos).
            territorio_id_por_indicacao_fiscal={
                "38033021": "curitiba-bairro-bairro-alto"
            },
        )
    )

    assert registros[0].territorio_id == "curitiba-bairro-bairro-alto"


def test_normalize_ignora_linha_sem_numero_alvara():
    connector = AlvaraConstrucaoConnector()
    valores = ["&nbsp;"] * 34
    header = "<tr>" + "<td>h</td>" * 34 + "</tr>"
    linha = "<tr>" + "".join(f"<td>{v}</td>" for v in valores) + "</tr>"
    snapshot = RawSnapshot(
        fonte_id="smu_alvara_construcao",
        capturado_em=None,
        snapshot_ref="memoria",
        conteudo={"html": f"<table>{header}{linha}</table>", "observado_em": date(2026, 1, 1)},
    )

    registros = list(connector.normalize(snapshot))

    assert registros == []
