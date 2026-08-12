import uuid
from datetime import date

from analytics.features import ContagemEventos, calcular_contagem_por_bairro_categoria_mes
from domain.event import Evento


def _evento(
    event_type: str,
    territorio_id: str | None,
    categoria_id: str | None,
    data_evento: date,
) -> Evento:
    payload = {"categoria_id": categoria_id} if categoria_id else {}
    return Evento(
        entity_type="comercio",
        event_type=event_type,
        entidade_id=uuid.uuid4(),
        territorio_id=territorio_id,
        data_evento=data_evento,
        confianca="baixa",
        origem_observacoes=(uuid.uuid4(),),
        payload=payload,
    )


def test_conta_por_bairro_categoria_mes_e_tipo():
    eventos = [
        _evento("PRIMEIRA_OBSERVACAO", "curitiba-bairro-centro", "bares_restaurantes", date(2026, 8, 1)),
        _evento("PRIMEIRA_OBSERVACAO", "curitiba-bairro-centro", "bares_restaurantes", date(2026, 8, 1)),
        _evento("ABERTURA_CONFIRMADA", "curitiba-bairro-centro", "bares_restaurantes", date(2026, 8, 1)),
        _evento("DESAPARECIMENTO", "curitiba-bairro-centro", "bares_restaurantes", date(2026, 8, 1)),
    ]

    resultado = calcular_contagem_por_bairro_categoria_mes(eventos)

    assert len(resultado) == 3  # PRIMEIRA_OBSERVACAO, ABERTURA_CONFIRMADA, DESAPARECIMENTO
    por_tipo = {c.event_type: c for c in resultado}
    assert por_tipo["PRIMEIRA_OBSERVACAO"].contagem == 2
    assert por_tipo["ABERTURA_CONFIRMADA"].contagem == 1
    assert por_tipo["DESAPARECIMENTO"].contagem == 1
    for c in resultado:
        assert c.territorio_id == "curitiba-bairro-centro"
        assert c.categoria_id == "bares_restaurantes"
        assert c.mes == date(2026, 8, 1)


def test_ignora_mudanca_categoria():
    eventos = [
        _evento("MUDANCA_CATEGORIA", "curitiba-bairro-centro", "bares_restaurantes", date(2026, 8, 1)),
    ]

    resultado = calcular_contagem_por_bairro_categoria_mes(eventos)

    assert resultado == []


def test_agrupa_por_mes_nao_por_dia_exato():
    eventos = [
        _evento("DESAPARECIMENTO", "curitiba-bairro-centro", None, date(2026, 8, 1)),
        _evento("DESAPARECIMENTO", "curitiba-bairro-centro", None, date(2026, 8, 15)),
    ]

    resultado = calcular_contagem_por_bairro_categoria_mes(eventos)

    assert len(resultado) == 1
    assert resultado[0].contagem == 2
    assert resultado[0].mes == date(2026, 8, 1)


def test_territorio_e_categoria_ausentes_viram_grupo_proprio():
    eventos = [
        _evento("PRIMEIRA_OBSERVACAO", None, None, date(2026, 8, 1)),
    ]

    resultado = calcular_contagem_por_bairro_categoria_mes(eventos)

    assert len(resultado) == 1
    assert resultado[0].territorio_id is None
    assert resultado[0].categoria_id is None
    assert resultado[0].contagem == 1


def test_sem_eventos_retorna_lista_vazia():
    assert calcular_contagem_por_bairro_categoria_mes([]) == []


def test_contagem_eventos_e_dataclass_simples():
    c = ContagemEventos(
        territorio_id="curitiba-bairro-centro",
        categoria_id="bares_restaurantes",
        mes=date(2026, 8, 1),
        event_type="PRIMEIRA_OBSERVACAO",
        contagem=5,
    )
    assert c.contagem == 5
