from pathlib import Path

from infrastructure.connectors.apolar_anuncios.parsing import (
    parse_pagina_detalhe,
    parse_url_anuncio,
    tipologia_normalizada,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_url_alugar_curitiba():
    url = (
        "https://www.apolar.com.br/alugar/curitiba/sitio-cercado/"
        "alugar-residencial-apartamento-curitiba-sitio-cercado-100127"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.id_anuncio == "100127"
    assert campos.operacao == "aluguel"
    assert campos.uso == "residencial"
    assert campos.tipologia_raw == "apartamento"
    assert campos.bairro_slug == "sitio-cercado"
    assert tipologia_normalizada(campos) == "apartamento"


def test_parse_url_venda_curitiba():
    url = (
        "https://www.apolar.com.br/venda/curitiba/butiatuvinha/"
        "venda-residencial-casa-curitiba-butiatuvinha-151309"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.operacao == "venda"
    assert campos.tipologia_raw == "casa"
    assert campos.bairro_slug == "butiatuvinha"


def test_parse_url_terreno_comercialresidencial():
    # slug real observado no checkpoint 12a
    url = (
        "https://www.apolar.com.br/venda/curitiba/tingui/"
        "venda-comercialresidencial-terreno-curitiba-tingui-155544"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.uso == "comercialresidencial"
    assert campos.tipologia_raw == "terreno"
    assert tipologia_normalizada(campos) == "terreno"


def test_parse_url_categoria_nao_e_anuncio_devolve_none():
    assert parse_url_anuncio("https://www.apolar.com.br/alugar/curitiba/sitio-cercado") is None
    assert parse_url_anuncio("https://www.apolar.com.br/alugar") is None


def test_parse_pagina_detalhe_real():
    html = (FIXTURES / "detalhe_aluguel_apartamento.html").read_text(encoding="utf-8")
    campos = parse_pagina_detalhe(html)

    assert campos.preco == 1100.0
    assert campos.area_util_m2 == 48.0
    assert campos.quartos == 2
    assert campos.vagas == 1
    assert campos.condominio == 550.0
    assert campos.iptu == 23.79
    assert campos.andar == 1


def test_parse_pagina_detalhe_banheiros_ausente_fica_none():
    html = (FIXTURES / "detalhe_aluguel_apartamento.html").read_text(encoding="utf-8")
    campos = parse_pagina_detalhe(html)

    # este anúncio real não publica banheiros na ficha - não deveria
    # inventar um valor.
    assert campos.banheiros is None
