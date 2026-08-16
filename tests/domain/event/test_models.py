import uuid
from datetime import date

import pytest

from domain.event import Evento


def _base_kwargs():
    return dict(
        entity_type="comercio",
        event_type="PRIMEIRA_OBSERVACAO",
        entidade_id=uuid.uuid4(),
        data_evento=date(2026, 8, 1),
        confianca="baixa",
        origem_observacoes=(uuid.uuid4(),),
    )


def test_evento_valido_e_aceito():
    e = Evento(**_base_kwargs())
    assert e.event_type == "PRIMEIRA_OBSERVACAO"
    assert e.territorio_id is None
    assert e.payload == {}
    assert e.evento_id is not None


def test_event_type_invalido_rejeitado():
    kwargs = _base_kwargs()
    kwargs["event_type"] = "EVENTO_INVENTADO"
    with pytest.raises(ValueError):
        Evento(**kwargs)


def test_confianca_invalida_rejeitada():
    kwargs = _base_kwargs()
    kwargs["confianca"] = "certeza_absoluta"
    with pytest.raises(ValueError):
        Evento(**kwargs)


def test_origem_observacoes_vazia_rejeitada():
    kwargs = _base_kwargs()
    kwargs["origem_observacoes"] = ()
    with pytest.raises(ValueError):
        Evento(**kwargs)


def test_entity_type_vazio_rejeitado():
    kwargs = _base_kwargs()
    kwargs["entity_type"] = ""
    with pytest.raises(ValueError):
        Evento(**kwargs)


def test_fechamento_confirmado_e_um_tipo_valido_mas_reservado():
    kwargs = _base_kwargs()
    kwargs["event_type"] = "FECHAMENTO_CONFIRMADO"
    kwargs["confianca"] = "alta"
    e = Evento(**kwargs)
    assert e.event_type == "FECHAMENTO_CONFIRMADO"


@pytest.mark.parametrize(
    "event_type", ["ALVARA_APROVADO", "OBRA_CONCLUIDA", "ALVARA_DEMOLICAO"]
)
def test_tipos_de_evento_de_obra_sao_validos(event_type):
    kwargs = _base_kwargs()
    kwargs["entity_type"] = "obra"
    kwargs["event_type"] = event_type
    kwargs["confianca"] = "alta"
    e = Evento(**kwargs)
    assert e.event_type == event_type


def test_zoneamento_alterado_e_um_tipo_valido_mas_reservado():
    kwargs = _base_kwargs()
    kwargs["entity_type"] = "territorio"
    kwargs["event_type"] = "ZONEAMENTO_ALTERADO"
    kwargs["confianca"] = "alta"
    e = Evento(**kwargs)
    assert e.event_type == "ZONEAMENTO_ALTERADO"


@pytest.mark.parametrize("event_type", ["LANCAMENTO", "TRANSACAO"])
def test_lancamento_e_transacao_sao_validos_mas_reservados(event_type):
    kwargs = _base_kwargs()
    kwargs["event_type"] = event_type
    kwargs["confianca"] = "baixa"
    e = Evento(**kwargs)
    assert e.event_type == event_type


@pytest.mark.parametrize(
    "event_type", ["ANUNCIO_PUBLICADO", "ANUNCIO_ENCERRADO", "PRECO_ALTERADO", "REANUNCIO"]
)
def test_tipos_de_evento_de_anuncio_sao_validos(event_type):
    kwargs = _base_kwargs()
    kwargs["entity_type"] = "anuncio_imovel"
    kwargs["event_type"] = event_type
    kwargs["confianca"] = "baixa"
    e = Evento(**kwargs)
    assert e.event_type == event_type
