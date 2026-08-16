from pathlib import Path

from infrastructure.connectors.chavesnamao_anuncios.parsing import (
    parse_pagina_detalhe,
    parse_url_anuncio,
    tipologia_normalizada,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_url_venda_curitiba():
    url = (
        "https://www.chavesnamao.com.br/imovel/"
        "apartamento-a-venda-2-quartos-com-garagem-pr-curitiba-campo-comprido-"
        "65m2-RS379000/id-45712812/"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.id_anuncio == "45712812"
    assert campos.operacao == "venda"
    assert campos.tipologia_raw == "apartamento"
    assert campos.bairro_slug == "campo-comprido"
    assert campos.area_m2_url == 65.0
    assert campos.preco_url == 379000.0
    assert campos.quartos_url == 2
    assert tipologia_normalizada(campos) == "apartamento"


def test_parse_url_aluguel_curitiba():
    url = (
        "https://www.chavesnamao.com.br/imovel/"
        "casa-para-alugar-3-quartos-com-garagem-pr-curitiba-hauer-400m2-RS3000/"
        "id-45713748/"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.operacao == "aluguel"
    assert campos.tipologia_raw == "casa"
    assert campos.bairro_slug == "hauer"
    assert campos.preco_url == 3000.0


def test_parse_url_terreno_sem_quartos():
    url = (
        "https://www.chavesnamao.com.br/imovel/"
        "terreno-a-venda-pr-curitiba-tingui-360m2-RS550000/id-45713956/"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.tipologia_raw == "terreno"
    assert campos.quartos_url is None


def test_parse_url_comercial_com_salas_nao_confunde_com_quartos():
    # "15-salas" não é "quartos" - a regex de quartos é específica pro
    # sufixo "-quartos", nunca casa "-salas".
    url = (
        "https://www.chavesnamao.com.br/imovel/"
        "casa-comercial-para-alugar-15-salas-com-garagem-pr-curitiba-"
        "centro-civico-480m2-RS14500/id-45713746/"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.quartos_url is None


def test_parse_url_bairro_composto_multi_palavra():
    url = (
        "https://www.chavesnamao.com.br/imovel/"
        "apartamento-a-venda-1-quarto-pr-curitiba-cristo-rei-21m2-RS269000/"
        "id-45713217/"
    )
    campos = parse_url_anuncio(url)

    assert campos is not None
    assert campos.bairro_slug == "cristo-rei"


def test_parse_url_fora_do_padrao_devolve_none():
    assert parse_url_anuncio("https://www.chavesnamao.com.br/imovel/algo-estranho/") is None
    assert parse_url_anuncio("https://www.chavesnamao.com.br/apartamentos-a-venda/pr/") is None


def test_parse_pagina_detalhe_real():
    html = (FIXTURES / "detalhe_venda_apartamento.html").read_text(encoding="utf-8")
    campos = parse_pagina_detalhe(html)

    assert campos.preco == 379000.0
    assert campos.area_util_m2 == 51.0
    assert campos.quartos == 2
    assert campos.banheiros == 1
    assert campos.vagas == 1
    assert campos.condominio == 600.0
    assert campos.iptu == 800.0
    assert campos.andar == 3


def test_parse_pagina_detalhe_nunca_extrai_dado_pessoal():
    html = (FIXTURES / "detalhe_venda_apartamento.html").read_text(encoding="utf-8")
    campos = parse_pagina_detalhe(html)

    # CamposPagina não tem nenhum campo de nome/telefone/e-mail/CRECI -
    # a ausência desses atributos no dataclass É a garantia (não dá pra
    # persistir o que o objeto nunca carrega). Confirma isso na prática:
    # nenhum dos valores dos campos existentes contém a string do
    # corretor real que aparece na página fixture.
    valores = str(vars(campos))
    assert "BOSA" not in valores
