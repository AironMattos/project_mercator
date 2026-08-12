from commerce.cnae.normalizacao import normalizar_codigo_cnae


def test_normaliza_formato_dominante_cabeleireiros():
    # confirmado contra a descrição oficial do IBGE: 9602-5/01 =
    # "Cabeleireiros, manicure e pedicure"
    assert normalizar_codigo_cnae("S.96.0.2-5/01-00") == "9602501"


def test_normaliza_formato_dominante_padaria_revenda():
    # confirmado contra a descrição oficial: 4721-1/02 = "Padaria e
    # confeitaria com predominância de revenda"
    assert normalizar_codigo_cnae("G.47.2.1-1/02-00") == "4721102"


def test_normaliza_formato_dominante_padaria_producao_propria():
    # confirmado contra a descrição oficial: 1091-1/02 = "Fabricação de
    # produtos de padaria e confeitaria com predominância de produção própria"
    assert normalizar_codigo_cnae("C.10.9.1-1/02-00") == "1091102"


def test_formato_legado_nao_reconhecido_retorna_none():
    # "5-70.20.00" - não corresponde a nenhum código CNAE real (dígitos não
    # batem com nenhuma descrição oficial conhecida); tratado como não
    # resolvido, não como erro.
    assert normalizar_codigo_cnae("5-70.20.00") is None


def test_placeholder_nao_reconhecido_retorna_none():
    # seção "X" não existe na CNAE oficial (vai de A a U) - é um
    # placeholder de "não classificado", não um código real.
    assert normalizar_codigo_cnae("X.88.8.8-8/88-88") is None


def test_none_retorna_none():
    assert normalizar_codigo_cnae(None) is None


def test_vazio_retorna_none():
    assert normalizar_codigo_cnae("") is None


def test_texto_arbitrario_retorna_none():
    assert normalizar_codigo_cnae("não informado") is None
