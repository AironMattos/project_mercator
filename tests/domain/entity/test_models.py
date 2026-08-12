import pytest

from domain.entity import Entidade


def test_entidade_valida_e_aceita():
    e = Entidade(tipo_entidade="comercio", identificador_fonte="123456")
    assert e.tipo_entidade == "comercio"
    assert e.identificador_fonte == "123456"
    assert e.entidade_id is not None


def test_entidade_id_gerado_automaticamente_e_unico():
    e1 = Entidade(tipo_entidade="comercio", identificador_fonte="1")
    e2 = Entidade(tipo_entidade="comercio", identificador_fonte="2")
    assert e1.entidade_id != e2.entidade_id


def test_tipo_entidade_vazio_rejeitado():
    with pytest.raises(ValueError):
        Entidade(tipo_entidade="", identificador_fonte="123456")


def test_identificador_fonte_vazio_rejeitado():
    with pytest.raises(ValueError):
        Entidade(tipo_entidade="comercio", identificador_fonte="")
