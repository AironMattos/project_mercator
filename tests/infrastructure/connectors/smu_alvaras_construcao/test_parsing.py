from infrastructure.connectors.smu_alvaras_construcao.parsing import (
    celula_ou_none,
    normalizar_indicacao_fiscal,
    parse_tabela,
)


def _linha_html(*valores: str) -> str:
    celulas = "".join(f"<td>{v}</td>" for v in valores)
    return f"<tr>{celulas}</tr>"


def test_celula_ou_none_decodifica_entidade_html_e_remove_nbsp():
    assert celula_ou_none("&#231;&#227;o") == "ção"
    assert celula_ou_none("&nbsp;") is None
    assert celula_ou_none("&nbsp;01/04/2026&nbsp;") == "01/04/2026"


def test_parse_tabela_pula_linha_de_cabecalho():
    header = _linha_html(*(f"Coluna {i}" for i in range(34)))
    valores_alvara = [str(i) for i in range(34)]
    valores_alvara[13] = "12345"  # numero_alvara (índice 13)
    dado = _linha_html(*valores_alvara)
    html = f"<table>{header}{dado}</table>"

    registros = parse_tabela(html)

    assert len(registros) == 1
    assert registros[0]["numero_alvara"] == "12345"


def test_parse_tabela_relatorio_alvara_34_colunas_mapeia_por_posicao():
    valores = ["&nbsp;"] * 34
    valores[0] = "38.033.021"  # indicacao_fiscal
    valores[13] = "417418"  # numero_alvara
    valores[10] = "2"  # quantidade_pavimentos
    valores[19] = "545,93"  # metragem_construida_lote
    html = f"<table>{_linha_html(*(['x'] * 34))}{_linha_html(*valores)}</table>"

    registros = parse_tabela(html)

    assert len(registros) == 1
    r = registros[0]
    assert r["indicacao_fiscal"] == "38.033.021"
    assert r["numero_alvara"] == "417418"
    assert r["quantidade_pavimentos"] == "2"
    assert r["metragem_construida_lote"] == "545,93"
    assert "area_vistoria" not in r  # relatório de alvará não tem essa 35ª coluna


def test_parse_tabela_relatorio_cvco_35_colunas_inclui_area_vistoria():
    valores = ["&nbsp;"] * 35
    valores[13] = "417418"
    valores[31] = "88776"  # numero_cvco
    valores[34] = "545,93"  # area_vistoria
    html = f"<table>{_linha_html(*(['x'] * 35))}{_linha_html(*valores)}</table>"

    registros = parse_tabela(html)

    assert registros[0]["numero_cvco"] == "88776"
    assert registros[0]["area_vistoria"] == "545,93"


def test_parse_tabela_linha_totalmente_vazia_ignorada():
    header = _linha_html(*(["x"] * 34))
    linha_vazia = _linha_html(*(["&nbsp;"] * 34))
    html = f"<table>{header}{linha_vazia}</table>"

    assert parse_tabela(html) == []


def test_normalizar_indicacao_fiscal_remove_pontos():
    # achado real do checkpoint 11c: SMU usa pontos ("12.006.027"),
    # lote_cadastral (GeoCuritiba) guarda só dígitos ("12006027").
    assert normalizar_indicacao_fiscal("12.006.027") == "12006027"


def test_normalizar_indicacao_fiscal_none_ou_vazio():
    assert normalizar_indicacao_fiscal(None) is None
    assert normalizar_indicacao_fiscal("") is None
