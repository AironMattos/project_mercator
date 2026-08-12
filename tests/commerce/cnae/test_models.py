import pytest

from commerce.cnae import Cnae


def test_cnae_valido_e_aceito():
    c = Cnae(
        codigo_cnae="9602501",
        descricao="CABELEIREIROS, MANICURE E PEDICURE",
        secao="S",
        divisao="96",
        grupo="960",
        classe="96025",
        subclasse="9602501",
    )
    assert c.codigo_cnae == "9602501"


def test_codigo_cnae_vazio_rejeitado():
    with pytest.raises(ValueError):
        Cnae(
            codigo_cnae="",
            descricao="X",
            secao="S",
            divisao="96",
            grupo="960",
            classe="96025",
            subclasse="9602501",
        )


def test_descricao_vazia_rejeitada():
    with pytest.raises(ValueError):
        Cnae(
            codigo_cnae="9602501",
            descricao="",
            secao="S",
            divisao="96",
            grupo="960",
            classe="96025",
            subclasse="9602501",
        )
