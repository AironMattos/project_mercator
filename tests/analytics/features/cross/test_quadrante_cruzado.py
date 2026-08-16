from analytics.features.cross.quadrante_cruzado import (
    COMERCIO_CRESCE_OFERTA_ESCASSA,
    MOVIMENTO_BAIXO_NOS_DOIS_LADOS,
    MOVIMENTO_NOS_DOIS_LADOS,
    OFERTA_CRESCE_COMERCIO_PARADO,
    classificar_quadrante_cruzado,
)


def test_movimento_nos_dois_lados():
    assert classificar_quadrante_cruzado(0.1, 0.1) == MOVIMENTO_NOS_DOIS_LADOS


def test_comercio_cresce_oferta_escassa():
    assert classificar_quadrante_cruzado(0.1, -0.1) == COMERCIO_CRESCE_OFERTA_ESCASSA


def test_oferta_cresce_comercio_parado():
    assert classificar_quadrante_cruzado(-0.1, 0.1) == OFERTA_CRESCE_COMERCIO_PARADO


def test_movimento_baixo_nos_dois_lados():
    assert classificar_quadrante_cruzado(-0.1, -0.1) == MOVIMENTO_BAIXO_NOS_DOIS_LADOS


def test_sem_comercio_fica_none():
    assert classificar_quadrante_cruzado(None, 0.1) is None


def test_sem_anuncio_fica_none():
    assert classificar_quadrante_cruzado(0.1, None) is None
