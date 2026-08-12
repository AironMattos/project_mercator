import uuid
from datetime import date

from domain.event import detectar_desaparecimento, detectar_eventos_par
from domain.observation import ObservacaoEntidade

ENTITY_TYPE = "comercio"


def _observacao(observado_em: date, atributos: dict, entidade_id=None) -> ObservacaoEntidade:
    return ObservacaoEntidade(
        entidade_id=entidade_id or uuid.uuid4(),
        observado_em=observado_em,
        atributos=atributos,
        fonte_id="alvaras_smf",
        snapshot_ref=f"data/raw/alvaras_smf/{observado_em.isoformat()}.csv",
    )


def test_primeira_observacao_quando_negocio_antigo_e_sem_anterior():
    atual = _observacao(
        date(2026, 8, 1),
        {"inicio_atividade": "2010-01-15", "cnae_principal": "5-70.20.00", "territorio_id": "curitiba-bairro-centro"},
    )

    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.event_type == "PRIMEIRA_OBSERVACAO"
    assert evento.confianca == "baixa"
    assert evento.entidade_id == atual.entidade_id
    assert evento.territorio_id == "curitiba-bairro-centro"
    assert evento.origem_observacoes == (atual.observacao_id,)


def test_primeira_observacao_quando_sem_inicio_atividade_informado():
    atual = _observacao(date(2026, 8, 1), {"inicio_atividade": None, "cnae_principal": "5-70.20.00"})

    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)

    assert len(eventos) == 1
    assert eventos[0].event_type == "PRIMEIRA_OBSERVACAO"


def test_abertura_confirmada_quando_inicio_no_mes_coberto_pelo_snapshot():
    # o snapshot é datado no dia 1º (2026-08-01) mas reflete o estado
    # consolidado até o fim do mês ANTERIOR (julho) - confirmado
    # empiricamente contra o dado real (ver domain/event/regras.py).
    atual = _observacao(
        date(2026, 8, 1),
        {"inicio_atividade": "2026-07-15", "cnae_principal": "5-70.20.00", "territorio_id": "curitiba-bairro-centro"},
    )

    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.event_type == "ABERTURA_CONFIRMADA"
    assert evento.confianca == "alta"
    assert evento.origem_observacoes == (atual.observacao_id,)


def test_abertura_confirmada_no_limite_da_virada_de_ano():
    atual = _observacao(
        date(2026, 1, 1),
        {"inicio_atividade": "2025-12-20", "cnae_principal": "5-70.20.00"},
    )

    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)

    assert len(eventos) == 1
    assert eventos[0].event_type == "ABERTURA_CONFIRMADA"


def test_abertura_e_primeira_observacao_sao_mutuamente_exclusivas():
    # mesma observação nunca gera as duas ao mesmo tempo
    atual = _observacao(date(2026, 8, 1), {"inicio_atividade": "2026-07-01", "cnae_principal": "X"})
    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)
    tipos = {e.event_type for e in eventos}
    assert tipos == {"ABERTURA_CONFIRMADA"}


def test_primeira_observacao_quando_inicio_no_mesmo_mes_do_snapshot():
    # inicio_atividade no MESMO mês do snapshot (não no anterior) não conta
    # como abertura confirmada - dado o dia 1º, isso seria uma coincidência
    # rara e não o sinal que a regra procura.
    atual = _observacao(date(2026, 8, 1), {"inicio_atividade": "2026-08-01", "cnae_principal": "X"})
    eventos = detectar_eventos_par(None, atual, ENTITY_TYPE)
    assert eventos[0].event_type == "PRIMEIRA_OBSERVACAO"


def test_mudanca_categoria_quando_cnae_difere():
    entidade_id = uuid.uuid4()
    anterior = _observacao(date(2026, 7, 1), {"cnae_principal": "5-70.20.00"}, entidade_id=entidade_id)
    atual = _observacao(
        date(2026, 8, 1),
        {"cnae_principal": "1-11.11.11", "territorio_id": "curitiba-bairro-centro"},
        entidade_id=entidade_id,
    )

    eventos = detectar_eventos_par(anterior, atual, ENTITY_TYPE)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.event_type == "MUDANCA_CATEGORIA"
    assert evento.confianca == "media"
    assert evento.origem_observacoes == (anterior.observacao_id, atual.observacao_id)
    assert evento.payload == {"cnae_anterior": "5-70.20.00", "cnae_atual": "1-11.11.11"}


def test_sem_evento_quando_cnae_igual():
    entidade_id = uuid.uuid4()
    anterior = _observacao(date(2026, 7, 1), {"cnae_principal": "5-70.20.00"}, entidade_id=entidade_id)
    atual = _observacao(date(2026, 8, 1), {"cnae_principal": "5-70.20.00"}, entidade_id=entidade_id)

    eventos = detectar_eventos_par(anterior, atual, ENTITY_TYPE)

    assert eventos == []


def test_sem_evento_quando_cnae_ausente_em_algum_lado():
    entidade_id = uuid.uuid4()
    anterior = _observacao(date(2026, 7, 1), {"cnae_principal": None}, entidade_id=entidade_id)
    atual = _observacao(date(2026, 8, 1), {"cnae_principal": "5-70.20.00"}, entidade_id=entidade_id)

    eventos = detectar_eventos_par(anterior, atual, ENTITY_TYPE)

    assert eventos == []


def test_desaparecimento():
    ultima = _observacao(
        date(2026, 7, 1),
        {"cnae_principal": "5-70.20.00", "territorio_id": "curitiba-bairro-centro"},
    )

    evento = detectar_desaparecimento(ultima, ENTITY_TYPE, date(2026, 8, 1))

    assert evento.event_type == "DESAPARECIMENTO"
    assert evento.confianca == "baixa"
    assert evento.entidade_id == ultima.entidade_id
    assert evento.territorio_id == "curitiba-bairro-centro"
    assert evento.data_evento == date(2026, 8, 1)
    assert evento.origem_observacoes == (ultima.observacao_id,)
