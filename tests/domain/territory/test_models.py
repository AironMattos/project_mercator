import pytest
from shapely.geometry import Polygon

from domain.territory import Territorio


def _quadrado() -> Polygon:
    return Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])


def test_territorio_valido_e_aceito():
    t = Territorio(
        territorio_id="curitiba-bairro-centro",
        nivel="bairro",
        nome="CENTRO",
        geometria=_quadrado(),
    )
    assert t.territorio_id == "curitiba-bairro-centro"
    assert t.cidade_id == "curitiba"


def test_territorio_sem_geometria_e_aceito():
    t = Territorio(territorio_id="curitiba-bairro-centro", nivel="bairro", nome="CENTRO")
    assert t.geometria is None


@pytest.mark.parametrize("nivel", ["", "quadra", "estado"])
def test_nivel_invalido_rejeitado(nivel):
    with pytest.raises(ValueError):
        Territorio(territorio_id="x", nivel=nivel, nome="X")


def test_territorio_id_vazio_rejeitado():
    with pytest.raises(ValueError):
        Territorio(territorio_id="", nivel="bairro", nome="X")


def test_nome_vazio_rejeitado():
    with pytest.raises(ValueError):
        Territorio(territorio_id="x", nivel="bairro", nome="")


def test_geometria_vazia_rejeitada():
    with pytest.raises(ValueError):
        Territorio(
            territorio_id="x", nivel="bairro", nome="X", geometria=Polygon()
        )
