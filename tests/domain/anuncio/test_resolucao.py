import uuid
from datetime import date, timedelta

from domain.anuncio.resolucao import CandidatoResolucao, resolver_imoveis


def _candidato(fonte_id, impressao_digital, dias_apos_referencia, entidade_id=None):
    referencia = date(2026, 8, 1)
    return CandidatoResolucao(
        entidade_id=entidade_id or uuid.uuid4(),
        fonte_id=fonte_id,
        impressao_digital=impressao_digital,
        primeira_observado_em=referencia + timedelta(days=dias_apos_referencia),
    )


def test_coincidencia_dentro_da_janela_funde_em_um_cluster():
    candidatos = [
        _candidato("apolar_anuncios", "fp-1", 0),
        _candidato("chavesnamao_anuncios", "fp-1", 10),
    ]
    clusters = resolver_imoveis(candidatos, janela_dias=30)

    assert len(clusters) == 1
    assert clusters[0].multiplas_fontes is True
    assert set(clusters[0].fontes) == {"apolar_anuncios", "chavesnamao_anuncios"}


def test_coincidencia_fora_da_janela_nao_funde():
    candidatos = [
        _candidato("apolar_anuncios", "fp-1", 0),
        _candidato("chavesnamao_anuncios", "fp-1", 45),
    ]
    clusters = resolver_imoveis(candidatos, janela_dias=30)

    assert len(clusters) == 2
    assert all(not c.multiplas_fontes for c in clusters)


def test_nenhuma_coincidencia_impressoes_diferentes_ficam_separadas():
    candidatos = [
        _candidato("apolar_anuncios", "fp-1", 0),
        _candidato("chavesnamao_anuncios", "fp-2", 0),
    ]
    clusters = resolver_imoveis(candidatos, janela_dias=30)

    assert len(clusters) == 2
    assert {c.impressao_digital for c in clusters} == {"fp-1", "fp-2"}


def test_cluster_unico_sem_par_fica_singleton():
    candidatos = [_candidato("apolar_anuncios", "fp-1", 0)]
    clusters = resolver_imoveis(candidatos, janela_dias=30)

    assert len(clusters) == 1
    assert clusters[0].multiplas_fontes is False


def test_tres_candidatos_janela_encadeada_ancora_na_primeira():
    # 0 -> 25 -> 50: a segunda entra na janela da âncora (0+25<=30), mas a
    # terceira NÃO está dentro de 30 dias da âncora original (0), então
    # abre um cluster novo ancorado nela mesma - mesmo padrão "ancora
    # fixa" documentado em resolucao.py, não uma janela deslizante.
    candidatos = [
        _candidato("apolar_anuncios", "fp-1", 0),
        _candidato("chavesnamao_anuncios", "fp-1", 25),
        _candidato("apolar_anuncios", "fp-1", 50),
    ]
    clusters = resolver_imoveis(candidatos, janela_dias=30)

    assert len(clusters) == 2
    tamanhos = sorted(len(c.entidade_ids) for c in clusters)
    assert tamanhos == [1, 2]


def test_lista_vazia_devolve_lista_vazia():
    assert resolver_imoveis([], janela_dias=30) == []
