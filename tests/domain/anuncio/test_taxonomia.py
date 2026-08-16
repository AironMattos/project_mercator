from domain.anuncio.taxonomia import NAO_CLASSIFICADO, normalizar_tipologia


def test_normaliza_termos_diretos():
    assert normalizar_tipologia("apartamento") == "apartamento"
    assert normalizar_tipologia("casa") == "casa"
    assert normalizar_tipologia("terreno") == "terreno"


def test_normaliza_sinonimos():
    assert normalizar_tipologia("apto") == "apartamento"
    assert normalizar_tipologia("kitnet") == "kitnet_studio"
    assert normalizar_tipologia("studio") == "kitnet_studio"
    assert normalizar_tipologia("penthouse") == "cobertura"
    assert normalizar_tipologia("sitio") == "chacara_sitio"


def test_normaliza_composto_apolar():
    # slug real observado no checkpoint 12a: /venda/curitiba/tingui/
    # venda-comercialresidencial-terreno-curitiba-tingui-155544
    assert normalizar_tipologia("comercialresidencial") == "terreno"


def test_case_insensitive_e_ignora_acento():
    assert normalizar_tipologia("Apartamento") == "apartamento"
    assert normalizar_tipologia("SOBRADO") == "sobrado"


def test_termo_desconhecido_vira_nao_classificado():
    assert normalizar_tipologia("iglu") == NAO_CLASSIFICADO


def test_string_vazia_vira_nao_classificado():
    assert normalizar_tipologia("") == NAO_CLASSIFICADO
