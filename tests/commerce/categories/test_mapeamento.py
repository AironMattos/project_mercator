from commerce.categories import CATEGORIAS, MAPEAMENTO_CNAE_CATEGORIA


def test_toda_categoria_referenciada_no_mapeamento_esta_definida():
    referenciadas = set(MAPEAMENTO_CNAE_CATEGORIA.values())
    assert referenciadas <= set(CATEGORIAS)


def test_toda_categoria_definida_tem_pelo_menos_um_codigo_mapeado():
    usadas = set(MAPEAMENTO_CNAE_CATEGORIA.values())
    assert set(CATEGORIAS) <= usadas


def test_codigos_cnae_tem_formato_de_sete_digitos():
    for codigo in MAPEAMENTO_CNAE_CATEGORIA:
        assert codigo.isdigit() and len(codigo) == 7, codigo


def test_lista_pequena_e_explicita():
    # checkpoint 4 pede explicitamente uma lista pequena, não cobertura
    # total da CNAE (~1300 subclasses oficiais) - guarda-corpo para não
    # crescer isso sem querer virar uma tabela gigante por engano.
    assert 15 <= len(CATEGORIAS) <= 35
    assert len(MAPEAMENTO_CNAE_CATEGORIA) < 200
