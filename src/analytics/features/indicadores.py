from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from analytics.features.models import Baseline, ItemComBaseline, ItemRanking, PontoMensal, Tendencia

# Motivos de indisponibilidade - string curta, estável (é isso que a API
# expõe em motivo_indisponivel; não trocar os valores sem migrar o
# frontend).
MOTIVO_HISTORICO_INSUFICIENTE = "historico_insuficiente"
MOTIVO_BASELINE_ZERO = "baseline_zero"

# Configurável aqui, único lugar - nunca hardcoded de novo em outro
# arquivo. Repositório/API passam esses valores explicitamente ou usam o
# default.
MESES_JANELA_BASELINE_PADRAO = 24
MINIMO_MESES_BASELINE = 3
MINIMO_MESES_POR_JANELA_TENDENCIA = 2
LIMIAR_TENDENCIA_PCT = 0.10

# Piso mínimo de volume (checkpoint 10d - passe de polimento da identidade
# editorial): baseline abaixo disso não compete pelas primeiras posições do
# ranking - variação percentual sobre 2-5 aberturas é ruído estatístico, não
# crescimento de verdade. 10, não 15, pra não excluir o caso legítimo já
# coberto em teste (bairro pequeno com baseline=10 crescendo de verdade
# ainda deve aparecer bem posicionado - ver
# test_ranking_ordena_por_variacao_pct_nao_por_valor_absoluto).
BASELINE_MINIMO_RANKING = 10

ACELERANDO = "acelerando"
DESACELERANDO = "desacelerando"
ESTAVEL = "estavel"


def _normalizar_mes(d: date) -> date:
    return date(d.year, d.month, 1)


def _meses_antes(referencia: date, n: int) -> date:
    """referencia menos n meses, sempre normalizado pro dia 1."""
    total = (referencia.year * 12 + (referencia.month - 1)) - n
    return date(total // 12, total % 12 + 1, 1)


def calcular_baseline(
    serie: Sequence[PontoMensal],
    mes_referencia: date,
    valor_atual: float,
    *,
    janela_meses: int = MESES_JANELA_BASELINE_PADRAO,
    minimo_meses: int = MINIMO_MESES_BASELINE,
) -> Baseline:
    """Média móvel de `serie` numa janela de `janela_meses` terminando
    (exclusive) em `mes_referencia` - o próprio mês corrente nunca entra na
    média, mesmo que `serie` contenha um ponto pra ele.

    Restrição do prompt de referência: baseline só é confiável com
    profundidade real de histórico. `minimo_meses` é o piso de quantos
    meses distintos precisam existir dentro da janela pra considerar a
    média válida - abaixo disso, `baseline`/`variacao_pct` vêm None com
    `motivo_indisponivel="historico_insuficiente"`, nunca um número
    calculado sobre 1-2 pontos.
    """
    mes_referencia = _normalizar_mes(mes_referencia)
    inicio_janela = _meses_antes(mes_referencia, janela_meses)

    pontos_na_janela = [
        p.valor
        for p in serie
        if inicio_janela <= _normalizar_mes(p.mes) < mes_referencia
    ]

    if len(pontos_na_janela) < minimo_meses:
        return Baseline(
            valor_atual=valor_atual,
            baseline=None,
            variacao_pct=None,
            motivo_indisponivel=MOTIVO_HISTORICO_INSUFICIENTE,
        )

    media = sum(pontos_na_janela) / len(pontos_na_janela)

    if media == 0:
        # Histórico existe, mas a média é zero (o indicador nunca ocorreu
        # nessa janela) - (valor_atual - 0) / 0 é indefinido, não "infinito
        # positivo". baseline=0 é um número real e fica exposto; só a
        # variação percentual, que não pode ser expressa, vira None.
        return Baseline(
            valor_atual=valor_atual,
            baseline=0.0,
            variacao_pct=None,
            motivo_indisponivel=MOTIVO_BASELINE_ZERO,
        )

    variacao_pct = (valor_atual - media) / media
    return Baseline(
        valor_atual=valor_atual,
        baseline=media,
        variacao_pct=variacao_pct,
        motivo_indisponivel=None,
    )


def calcular_tendencia(
    serie: Sequence[PontoMensal],
    mes_referencia: date,
    *,
    limiar_pct: float = LIMIAR_TENDENCIA_PCT,
    minimo_meses_por_janela: int = MINIMO_MESES_POR_JANELA_TENDENCIA,
) -> Tendencia:
    """Compara a média dos últimos 3 meses fechados (mes_referencia e os
    2 anteriores) com a média dos 3 meses imediatamente anteriores a esses
    - não com o baseline de 24 meses, que mede outra coisa (nível normal,
    não momentum recente).

    Cada uma das duas janelas de 3 meses precisa ter pelo menos
    `minimo_meses_por_janela` pontos reais (não hardcoded 3/3 - permite 1
    mês faltante por janela sem invalidar tudo, mas duas janelas com só 1
    mês de profundidade real cada - o caso de fechamento hoje - ainda
    caem em indisponível).
    """
    mes_referencia = _normalizar_mes(mes_referencia)
    fim_recente = mes_referencia
    inicio_recente = _meses_antes(mes_referencia, 2)
    fim_anterior = _meses_antes(mes_referencia, 3)
    inicio_anterior = _meses_antes(mes_referencia, 5)

    pontos_recentes = [
        p.valor for p in serie if inicio_recente <= _normalizar_mes(p.mes) <= fim_recente
    ]
    pontos_anteriores = [
        p.valor for p in serie if inicio_anterior <= _normalizar_mes(p.mes) <= fim_anterior
    ]

    if (
        len(pontos_recentes) < minimo_meses_por_janela
        or len(pontos_anteriores) < minimo_meses_por_janela
    ):
        return Tendencia(
            classificacao=None,
            variacao_pct=None,
            motivo_indisponivel=MOTIVO_HISTORICO_INSUFICIENTE,
        )

    media_recente = sum(pontos_recentes) / len(pontos_recentes)
    media_anterior = sum(pontos_anteriores) / len(pontos_anteriores)

    if media_anterior == 0:
        if media_recente == 0:
            return Tendencia(classificacao=ESTAVEL, variacao_pct=0.0, motivo_indisponivel=None)
        # De zero pra algo positivo: aceleração inequívoca, mas não dá pra
        # expressar como percentual finito (mesma lógica do baseline_zero).
        return Tendencia(
            classificacao=ACELERANDO,
            variacao_pct=None,
            motivo_indisponivel=MOTIVO_BASELINE_ZERO,
        )

    variacao_pct = (media_recente - media_anterior) / media_anterior
    if variacao_pct > limiar_pct:
        classificacao = ACELERANDO
    elif variacao_pct < -limiar_pct:
        classificacao = DESACELERANDO
    else:
        classificacao = ESTAVEL

    return Tendencia(classificacao=classificacao, variacao_pct=variacao_pct, motivo_indisponivel=None)


def calcular_ranking(
    itens: Sequence[ItemComBaseline], *, baseline_minimo: float = BASELINE_MINIMO_RANKING
) -> list[ItemRanking]:
    """Ordena por variacao_pct desc - crescimento relativo, não volume
    absoluto (um bairro pequeno acelerando aparece à frente de um grande
    estável, de propósito). Itens sem variacao_pct (baseline indisponível)
    não são elegíveis - não entram na lista nem contam pro `total`.

    Piso mínimo de volume (checkpoint 10d): itens com baseline abaixo de
    `baseline_minimo` também ficam de fora do ranking principal, mesmo
    tendo variacao_pct - variação percentual sobre um baseline de 2-5
    aberturas é ruído estatístico, não sinal de crescimento real. Quem
    chama esta função e precisa saber quantos ficaram de fora por esse
    motivo (pra não escondê-los silenciosamente) deve comparar contra a
    lista de entrada - ver montar_ranking_aberturas.

    Desempate por territorio_id (determinístico, não afeta o significado
    do ranking - só evita ordem instável entre execuções quando dois
    bairros empatam exatamente na variação).
    """
    elegiveis = sorted(
        (
            item
            for item in itens
            if item.variacao_pct is not None
            and (item.baseline is None or item.baseline >= baseline_minimo)
        ),
        key=lambda item: (-item.variacao_pct, item.territorio_id or ""),
    )
    total = len(elegiveis)
    return [
        ItemRanking(
            territorio_id=item.territorio_id,
            valor_atual=item.valor_atual,
            baseline=item.baseline,
            variacao_pct=item.variacao_pct,
            tendencia=item.tendencia,
            posicao=posicao,
            total=total,
        )
        for posicao, item in enumerate(elegiveis, start=1)
    ]
