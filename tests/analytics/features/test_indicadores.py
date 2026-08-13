from datetime import date

import pytest

from analytics.features import (
    ACELERANDO,
    DESACELERANDO,
    ESTAVEL,
    MOTIVO_BASELINE_ZERO,
    MOTIVO_HISTORICO_INSUFICIENTE,
    ItemComBaseline,
    PontoMensal,
    calcular_baseline,
    calcular_ranking,
    calcular_tendencia,
    detectar_saldo_negativo_consecutivo,
)


def _serie_meses_seguidos(mes_final: date, valores: list[float]) -> list[PontoMensal]:
    """Monta uma série com um ponto por mês, terminando em mes_final,
    voltando len(valores) meses. Última posição de `valores` = mes_final.
    """
    pontos = []
    total = mes_final.year * 12 + (mes_final.month - 1)
    for i, valor in enumerate(reversed(valores)):
        idx = total - i
        pontos.append(PontoMensal(mes=date(idx // 12, idx % 12 + 1, 1), valor=valor))
    return list(reversed(pontos))


# --- calcular_baseline -------------------------------------------------


def test_baseline_calcula_media_movel_e_variacao():
    # 24 meses de histórico antes de 2026-08, todos com valor 10, mais o
    # mês corrente (não deve entrar na média) com valor 15.
    mes_ref = date(2026, 8, 1)
    historico = _serie_meses_seguidos(date(2026, 7, 1), [10.0] * 24)

    resultado = calcular_baseline(historico, mes_ref, valor_atual=15.0)

    assert resultado.baseline == 10.0
    assert resultado.variacao_pct == 0.5  # (15-10)/10
    assert resultado.motivo_indisponivel is None


def test_baseline_exclui_mes_corrente_mesmo_se_presente_na_serie():
    mes_ref = date(2026, 8, 1)
    historico = _serie_meses_seguidos(date(2026, 7, 1), [10.0] * 24)
    # Um ponto pro próprio mês de referência, com valor bem diferente -
    # não pode contaminar a média.
    historico_com_atual = [*historico, PontoMensal(mes=mes_ref, valor=1000.0)]

    resultado = calcular_baseline(historico_com_atual, mes_ref, valor_atual=15.0)

    assert resultado.baseline == 10.0


def test_baseline_janela_e_configuravel():
    mes_ref = date(2026, 8, 1)
    # 6 meses de histórico, valor crescente - com janela=3 só os últimos 3
    # meses antes do corrente entram na média.
    historico = _serie_meses_seguidos(date(2026, 7, 1), [1.0, 2.0, 3.0, 10.0, 10.0, 10.0])

    resultado = calcular_baseline(historico, mes_ref, valor_atual=10.0, janela_meses=3, minimo_meses=3)

    assert resultado.baseline == 10.0  # só os 3 mais recentes (10,10,10)


def test_baseline_historico_insuficiente_retorna_none_nao_zero_nem_erro():
    mes_ref = date(2026, 8, 1)
    # só 2 meses de histórico, abaixo do mínimo padrão (3)
    historico = _serie_meses_seguidos(date(2026, 7, 1), [10.0, 12.0])

    resultado = calcular_baseline(historico, mes_ref, valor_atual=20.0)

    assert resultado.baseline is None
    assert resultado.variacao_pct is None
    assert resultado.motivo_indisponivel == MOTIVO_HISTORICO_INSUFICIENTE
    assert resultado.valor_atual == 20.0  # valor atual sempre reportado, mesmo sem baseline


def test_baseline_sem_nenhum_ponto_historico():
    resultado = calcular_baseline([], date(2026, 8, 1), valor_atual=5.0)

    assert resultado.baseline is None
    assert resultado.motivo_indisponivel == MOTIVO_HISTORICO_INSUFICIENTE


def test_baseline_valor_atual_zero_com_historico_suficiente_e_negativo_valido():
    # bairro com valor zero no período - variação deve ser -100%, um número
    # real, não None (o histórico é que precisa ser insuficiente pra virar
    # None, não o valor atual ser zero).
    mes_ref = date(2026, 8, 1)
    historico = _serie_meses_seguidos(date(2026, 7, 1), [10.0] * 24)

    resultado = calcular_baseline(historico, mes_ref, valor_atual=0.0)

    assert resultado.baseline == 10.0
    assert resultado.variacao_pct == -1.0
    assert resultado.motivo_indisponivel is None


def test_baseline_media_historica_zero_nao_gera_divisao_por_zero():
    # histórico suficiente, mas o indicador nunca ocorreu nesses meses -
    # (valor_atual - 0) / 0 é indefinido, não pode virar erro nem 0.
    mes_ref = date(2026, 8, 1)
    historico = _serie_meses_seguidos(date(2026, 7, 1), [0.0] * 24)

    resultado = calcular_baseline(historico, mes_ref, valor_atual=5.0)

    assert resultado.baseline == 0.0  # baseline em si é um número real e válido
    assert resultado.variacao_pct is None
    assert resultado.motivo_indisponivel == MOTIVO_BASELINE_ZERO


def test_baseline_fechamento_com_dado_insuficiente_um_snapshot_real():
    # Caso do prompt: fechamento/saldo hoje só tem 1 mês real de evento
    # (2026-08), sem profundidade de snapshot nenhuma antes disso - tem
    # que vir marcado indisponível, nunca um número "sólido" fabricado
    # sobre essa base fraca.
    mes_ref = date(2026, 8, 1)
    historico_fechamento = [PontoMensal(mes=date(2026, 7, 1), valor=407.0)]

    resultado = calcular_baseline(historico_fechamento, mes_ref, valor_atual=407.0)

    assert resultado.baseline is None
    assert resultado.variacao_pct is None
    assert resultado.motivo_indisponivel == MOTIVO_HISTORICO_INSUFICIENTE


# --- calcular_tendencia --------------------------------------------------


def test_tendencia_acelerando_acima_do_limiar():
    mes_ref = date(2026, 8, 1)
    # janela anterior (mar,abr,mai)=10 média; janela recente (jun,jul,ago)=20 média -> +100%
    serie = _serie_meses_seguidos(mes_ref, [10.0, 10.0, 10.0, 20.0, 20.0, 20.0])

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao == ACELERANDO
    assert resultado.variacao_pct == pytest.approx(1.0)
    assert resultado.motivo_indisponivel is None


def test_tendencia_desacelerando_abaixo_do_limiar_negativo():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [20.0, 20.0, 20.0, 10.0, 10.0, 10.0])

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao == DESACELERANDO
    assert resultado.variacao_pct == pytest.approx(-0.5)


def test_tendencia_estavel_dentro_do_limiar():
    mes_ref = date(2026, 8, 1)
    # variação de +5%, dentro do limiar padrão de 10%
    serie = _serie_meses_seguidos(mes_ref, [10.0, 10.0, 10.0, 10.5, 10.5, 10.5])

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao == ESTAVEL


def test_tendencia_limiar_e_configuravel():
    mes_ref = date(2026, 8, 1)
    # +15% de variação: com limiar padrão (10%) seria "acelerando", com
    # limiar de 20% deve virar "estavel" - prova que não está hardcoded.
    serie = _serie_meses_seguidos(mes_ref, [10.0, 10.0, 10.0, 11.5, 11.5, 11.5])

    resultado_padrao = calcular_tendencia(serie, mes_ref)
    resultado_limiar_alto = calcular_tendencia(serie, mes_ref, limiar_pct=0.20)

    assert resultado_padrao.classificacao == ACELERANDO
    assert resultado_limiar_alto.classificacao == ESTAVEL


def test_tendencia_historico_insuficiente():
    # só 1 mês de dado - nem uma janela de 3 meses fecha completa
    mes_ref = date(2026, 8, 1)
    serie = [PontoMensal(mes=mes_ref, valor=10.0)]

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao is None
    assert resultado.variacao_pct is None
    assert resultado.motivo_indisponivel == MOTIVO_HISTORICO_INSUFICIENTE


def test_tendencia_fechamento_com_dado_insuficiente_um_snapshot_real():
    mes_ref = date(2026, 8, 1)
    serie_fechamento = [PontoMensal(mes=date(2026, 7, 1), valor=407.0)]

    resultado = calcular_tendencia(serie_fechamento, mes_ref)

    assert resultado.classificacao is None
    assert resultado.motivo_indisponivel == MOTIVO_HISTORICO_INSUFICIENTE


def test_tendencia_de_zero_pra_positivo_classifica_acelerando_sem_percentual():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [0.0, 0.0, 0.0, 5.0, 5.0, 5.0])

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao == ACELERANDO
    assert resultado.variacao_pct is None


def test_tendencia_zero_a_zero_e_estavel():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [0.0] * 6)

    resultado = calcular_tendencia(serie, mes_ref)

    assert resultado.classificacao == ESTAVEL
    assert resultado.variacao_pct == 0.0


# --- calcular_ranking ------------------------------------------------


def test_ranking_ordena_por_variacao_pct_nao_por_valor_absoluto():
    itens = [
        ItemComBaseline(territorio_id="grande-estavel", valor_atual=1000.0, baseline=990.0, variacao_pct=0.01),
        ItemComBaseline(territorio_id="pequeno-crescendo", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        ItemComBaseline(territorio_id="medio-caindo", valor_atual=50.0, baseline=100.0, variacao_pct=-0.5),
    ]

    resultado = calcular_ranking(itens)

    assert [r.territorio_id for r in resultado] == ["pequeno-crescendo", "grande-estavel", "medio-caindo"]
    assert resultado[0].posicao == 1
    assert resultado[1].posicao == 2
    assert resultado[2].posicao == 3
    assert all(r.total == 3 for r in resultado)


def test_ranking_exclui_itens_sem_variacao_pct_do_total():
    itens = [
        ItemComBaseline(territorio_id="a", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        ItemComBaseline(territorio_id="sem-baseline", valor_atual=3.0, baseline=None, variacao_pct=None),
        ItemComBaseline(territorio_id="b", valor_atual=8.0, baseline=10.0, variacao_pct=-0.2),
    ]

    resultado = calcular_ranking(itens)

    assert len(resultado) == 2
    assert all(r.total == 2 for r in resultado)
    assert "sem-baseline" not in [r.territorio_id for r in resultado]


def test_ranking_lista_vazia_quando_nenhum_item_elegivel():
    itens = [
        ItemComBaseline(territorio_id="a", valor_atual=1.0, baseline=None, variacao_pct=None),
    ]

    resultado = calcular_ranking(itens)

    assert resultado == []


def test_ranking_desempata_por_territorio_id():
    itens = [
        ItemComBaseline(territorio_id="zebra", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        ItemComBaseline(territorio_id="alfa", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
    ]

    resultado = calcular_ranking(itens)

    assert [r.territorio_id for r in resultado] == ["alfa", "zebra"]


def test_ranking_carrega_tendencia_associada():
    itens = [
        ItemComBaseline(
            territorio_id="a", valor_atual=20.0, baseline=10.0, variacao_pct=1.0, tendencia=ACELERANDO
        ),
    ]

    resultado = calcular_ranking(itens)

    assert resultado[0].tendencia == ACELERANDO


# --- calcular_ranking: piso mínimo de volume (checkpoint 10d) -----------


def test_ranking_exclui_baseline_abaixo_do_piso_minimo_de_volume():
    itens = [
        ItemComBaseline(territorio_id="volume-real", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        # variacao_pct alto, mas sobre um baseline de 2 - ruído estatístico
        # de baixo volume, exatamente o padrão observado em produção
        # (bairros pequenos com poucas aberturas reais no histórico).
        ItemComBaseline(territorio_id="ruido-baixo-volume", valor_atual=6.0, baseline=2.0, variacao_pct=2.0),
    ]

    resultado = calcular_ranking(itens)

    assert [r.territorio_id for r in resultado] == ["volume-real"]
    assert resultado[0].total == 1


def test_ranking_baseline_exatamente_no_piso_e_elegivel():
    itens = [
        ItemComBaseline(territorio_id="no-piso", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
    ]

    resultado = calcular_ranking(itens)

    assert [r.territorio_id for r in resultado] == ["no-piso"]


def test_ranking_piso_e_configuravel():
    itens = [
        ItemComBaseline(territorio_id="baseline-8", valor_atual=16.0, baseline=8.0, variacao_pct=1.0),
    ]

    assert calcular_ranking(itens) == []
    assert [r.territorio_id for r in calcular_ranking(itens, baseline_minimo=5)] == ["baseline-8"]


# --- calcular_ranking: ordem asc/desc (checkpoint 11b) -------------------


def test_ranking_ordem_asc_traz_maiores_retracoes_primeiro():
    itens = [
        ItemComBaseline(territorio_id="crescendo", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        ItemComBaseline(territorio_id="caindo-muito", valor_atual=10.0, baseline=100.0, variacao_pct=-0.9),
        ItemComBaseline(territorio_id="caindo-pouco", valor_atual=90.0, baseline=100.0, variacao_pct=-0.1),
    ]

    resultado = calcular_ranking(itens, ordem="asc")

    assert [r.territorio_id for r in resultado] == ["caindo-muito", "caindo-pouco", "crescendo"]
    assert resultado[0].posicao == 1


def test_ranking_ordem_desc_e_o_padrao_e_nao_muda_com_a_mudanca():
    itens = [
        ItemComBaseline(territorio_id="a", valor_atual=20.0, baseline=10.0, variacao_pct=1.0),
        ItemComBaseline(territorio_id="b", valor_atual=8.0, baseline=10.0, variacao_pct=-0.2),
    ]

    assert calcular_ranking(itens) == calcular_ranking(itens, ordem="desc")


# --- detectar_saldo_negativo_consecutivo (checkpoint 11b) -----------------


def test_sinal_saldo_negativo_consecutivo_detecta_quando_todos_meses_negativos():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [-5.0, -3.0, -1.0, -2.0])

    assert detectar_saldo_negativo_consecutivo(serie, mes_ref) is True


def test_sinal_saldo_negativo_consecutivo_falso_se_um_mes_e_positivo():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [-5.0, -3.0, 1.0, -2.0])

    assert detectar_saldo_negativo_consecutivo(serie, mes_ref) is False


def test_sinal_saldo_negativo_consecutivo_falso_se_mes_faltando_na_janela():
    # série não é zero-preenchida - mês ausente não conta como "não
    # negativo", invalida o sinal (mesma convenção de saldo em
    # feature_repository: ausência = não processado, não zero).
    mes_ref = date(2026, 8, 1)
    serie = [
        PontoMensal(mes=date(2026, 8, 1), valor=-5.0),
        PontoMensal(mes=date(2026, 7, 1), valor=-3.0),
        # 2026-06 ausente
        PontoMensal(mes=date(2026, 5, 1), valor=-1.0),
    ]

    assert detectar_saldo_negativo_consecutivo(serie, mes_ref) is False


def test_sinal_saldo_negativo_consecutivo_minimo_meses_configuravel():
    mes_ref = date(2026, 8, 1)
    serie = _serie_meses_seguidos(mes_ref, [-5.0, -3.0])

    assert detectar_saldo_negativo_consecutivo(serie, mes_ref, minimo_meses=2) is True
    assert detectar_saldo_negativo_consecutivo(serie, mes_ref, minimo_meses=4) is False
