import pytest

from commerce.categories import Categoria


def test_categoria_valida_e_aceita():
    c = Categoria(categoria_id="bares_restaurantes", nome="Bares, restaurantes e lanchonetes")
    assert c.categoria_id == "bares_restaurantes"


def test_categoria_id_vazio_rejeitado():
    with pytest.raises(ValueError):
        Categoria(categoria_id="", nome="X")


def test_nome_vazio_rejeitado():
    with pytest.raises(ValueError):
        Categoria(categoria_id="x", nome="")
