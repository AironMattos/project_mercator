import uuid
from datetime import date

import pytest

from domain.anuncio.models import ObservacaoAnuncio
from domain.anuncio.regras import (
    detectar_anuncio_encerrado,
    detectar_eventos_anuncio_par,
    detectar_reanuncio,
)


def _observacao(**overrides):
    base = dict(
        entidade_id=uuid.uuid4(),
        observado_em=date(2026, 8, 15),
        operacao="venda",
        tipologia="apartamento",
        preco=379000.0,
        condominio=450.0,
        iptu=800.0,
        area_util_m2=65.0,
        quartos=2,
        banheiros=1,
        vagas=1,
        andar=3,
        impressao_digital="abc123",
        fonte_id="chavesnamao_anuncios",
        snapshot_ref="2026-08-15",
        territorio_id="curitiba-bairro-campo-comprido",
    )
    base.update(overrides)
    return ObservacaoAnuncio(**base)


def test_sem_anterior_gera_anuncio_publicado_confianca_alta():
    atual = _observacao()
    eventos = detectar_eventos_anuncio_par(None, atual)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.event_type == "ANUNCIO_PUBLICADO"
    assert evento.confianca == "alta"
    assert evento.entity_type == "anuncio_imovel"
    assert evento.origem_observacoes == (atual.observacao_id,)


def test_preco_alterado_para_cima():
    anterior = _observacao(preco=350000.0)
    atual = _observacao(entidade_id=anterior.entidade_id, preco=379000.0)

    eventos = detectar_eventos_anuncio_par(anterior, atual)

    assert len(eventos) == 1
    evento = eventos[0]
    assert evento.event_type == "PRECO_ALTERADO"
    assert evento.confianca == "alta"
    assert evento.payload["direcao"] == "aumento"
    assert evento.payload["preco_anterior"] == 350000.0
    assert evento.payload["preco_atual"] == 379000.0


def test_preco_alterado_para_baixo():
    anterior = _observacao(preco=400000.0)
    atual = _observacao(entidade_id=anterior.entidade_id, preco=379000.0)

    eventos = detectar_eventos_anuncio_par(anterior, atual)

    assert eventos[0].payload["direcao"] == "reducao"


def test_preco_igual_nao_gera_evento():
    anterior = _observacao(preco=379000.0)
    atual = _observacao(entidade_id=anterior.entidade_id, preco=379000.0)

    assert detectar_eventos_anuncio_par(anterior, atual) == []


def test_preco_none_nos_dois_lados_nao_gera_evento():
    anterior = _observacao(preco=None)
    atual = _observacao(entidade_id=anterior.entidade_id, preco=None)

    assert detectar_eventos_anuncio_par(anterior, atual) == []


def test_anuncio_encerrado_e_sempre_confianca_baixa():
    ultima = _observacao()
    evento = detectar_anuncio_encerrado(ultima, date(2026, 9, 1))

    assert evento.event_type == "ANUNCIO_ENCERRADO"
    assert evento.confianca == "baixa"
    assert evento.data_evento == date(2026, 9, 1)
    assert evento.payload["ultimo_preco"] == ultima.preco


def test_reanuncio_com_preco_maior():
    nova = _observacao(preco=420000.0)
    anterior_id = uuid.uuid4()

    evento = detectar_reanuncio(nova, anterior_id, preco_anterior=379000.0)

    assert evento.event_type == "REANUNCIO"
    assert evento.confianca == "media"
    assert evento.payload["variacao_pct"] == pytest.approx((420000.0 - 379000.0) / 379000.0)


def test_reanuncio_sem_preco_anterior_conhecido_nao_calcula_variacao():
    nova = _observacao(preco=420000.0)
    evento = detectar_reanuncio(nova, uuid.uuid4(), preco_anterior=None)

    assert evento.payload["variacao_pct"] is None
    assert evento.payload["preco_anterior"] is None
