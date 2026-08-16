from domain.anuncio.impressao_digital import calcular_impressao_digital


def _fp(**overrides):
    base = dict(
        territorio_id="curitiba-bairro-campo-comprido",
        area_util_m2=65.0,
        quartos=2,
        vagas=1,
        andar=3,
        condominio=450.0,
    )
    base.update(overrides)
    return calcular_impressao_digital(**base)


def test_mesmos_atributos_geram_mesma_impressao():
    assert _fp() == _fp()


def test_bairro_diferente_gera_impressao_diferente():
    assert _fp(territorio_id="curitiba-bairro-centro") != _fp()


def test_area_arredondada_ao_metro_inteiro_casa():
    # duas fontes reportando 65.0 e 65.4 são o mesmo imóvel na prática -
    # achado real do checkpoint 12a (mesma unidade, "65m2" vs "51m2
    # privativos" no mesmo anúncio - a diferença exata varia por fonte,
    # mas o arredondamento ao m² inteiro é o que evita que isso quebre a
    # resolução).
    assert _fp(area_util_m2=65.0) == _fp(area_util_m2=65.4)


def test_area_muito_diferente_nao_casa():
    assert _fp(area_util_m2=65.0) != _fp(area_util_m2=90.0)


def test_condominio_arredondado_a_centena_casa():
    assert _fp(condominio=420.0) == _fp(condominio=440.0)


def test_condominio_none_diferente_de_condominio_zero():
    # "não informado" e "informado como zero" não podem colidir.
    assert _fp(condominio=None) != _fp(condominio=0.0)


def test_vagas_ausente_diferente_de_vagas_zero():
    assert _fp(vagas=None) != _fp(vagas=0)


def test_quartos_diferente_gera_impressao_diferente():
    assert _fp(quartos=2) != _fp(quartos=3)


def test_andar_diferente_gera_impressao_diferente():
    assert _fp(andar=3) != _fp(andar=5)
