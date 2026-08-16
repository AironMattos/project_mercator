import uuid
from datetime import date

import pytest

from domain.anuncio import ClusterImovel, ObservacaoAnuncio


def _observacao(**overrides):
    base = dict(
        entidade_id=uuid.uuid4(),
        observado_em=date(2026, 8, 1),
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


def test_observacao_anuncio_valida_cria_normalmente():
    obs = _observacao()
    assert obs.tipo_valor == "anuncio"
    assert obs.ofertante_hash is None


def test_operacao_invalida_rejeitada():
    with pytest.raises(ValueError, match="operacao inválida"):
        _observacao(operacao="permuta")


def test_tipologia_invalida_rejeitada():
    with pytest.raises(ValueError, match="tipologia inválida"):
        _observacao(tipologia="mansao")


def test_preco_negativo_rejeitado():
    with pytest.raises(ValueError, match="preco não pode ser negativo"):
        _observacao(preco=-100.0)


def test_preco_none_e_aceito_anuncio_sem_preco_publicado():
    obs = _observacao(preco=None)
    assert obs.preco is None


def test_impressao_digital_vazia_rejeitada():
    with pytest.raises(ValueError, match="impressao_digital"):
        _observacao(impressao_digital="")


def test_fonte_id_vazio_rejeitado():
    with pytest.raises(ValueError, match="fonte_id"):
        _observacao(fonte_id="")


def test_tipo_valor_nunca_pode_ser_outra_grandeza():
    with pytest.raises(ValueError, match="sempre 'anuncio'"):
        _observacao(tipo_valor="transacao")


# --- ClusterImovel ---


def test_cluster_imovel_multiplas_fontes():
    cluster = ClusterImovel(
        entidade_ids=(uuid.uuid4(), uuid.uuid4()),
        fontes=("apolar_anuncios", "chavesnamao_anuncios"),
        impressao_digital="abc123",
    )
    assert cluster.multiplas_fontes is True


def test_cluster_imovel_fonte_unica():
    cluster = ClusterImovel(
        entidade_ids=(uuid.uuid4(),),
        fontes=("apolar_anuncios",),
        impressao_digital="abc123",
    )
    assert cluster.multiplas_fontes is False


def test_cluster_imovel_tamanhos_incompativeis_rejeitado():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        ClusterImovel(
            entidade_ids=(uuid.uuid4(), uuid.uuid4()),
            fontes=("apolar_anuncios",),
            impressao_digital="abc123",
        )


def test_cluster_imovel_vazio_rejeitado():
    with pytest.raises(ValueError, match="não pode ser vazio"):
        ClusterImovel(entidade_ids=(), fontes=(), impressao_digital="abc123")
