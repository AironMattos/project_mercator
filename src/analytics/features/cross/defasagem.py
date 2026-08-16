"""Defasagem cruzada entre comércio e anúncio (checkpoint 12g, seção 3.1
do prompt de referência do Radar de Anúncios): "em bairro onde novos
negócios estão abrindo, aparecem também novos anúncios de imóvel? Em que
ordem, com quanto atraso?"

Puro (sem I/O) de propósito - quem monta as duas séries mensais é
responsabilidade do repositório/serviço (ver servico_defasagem.py). Vive
em `analytics/features/cross/`, não em `commerce/` nem num pacote do
Radar de Anúncios, porque é uma leitura sobre o substrato compartilhado
(dim_territorio), não uma feature de um produto só - mesmo princípio já
declarado no prompt de referência.

Implementa as duas primeiras travas obrigatórias da seção 3.1:
1. Correlação espúria por múltiplos testes - toda correlação vem com um
   intervalo de confiança **corrigido por Bonferroni** pelo número de
   testes realizados (`n_testes`, explícito - nunca inferido às
   escondidas), nunca um coeficiente solto sem IC.
3. Piso de amostra - `PISO_MINIMO_MESES_SOBREPOSTOS` (menos meses
   sobrepostos que isso não sustenta uma correlação com defasagem até
   `lag_maximo`, mesmo espírito do piso de 30 anúncios em
   analytics/features/anuncio_termometro.py).

A segunda trava ("associação, nunca causa") não é uma regra de código -
é uma regra de vocabulário que vive na interface (checkpoint 12i) e na
documentação, o dataclass aqui nunca teria como impor isso sozinho.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date

from analytics.features import PontoMensal

LAG_MAXIMO_PADRAO = 12
PISO_MINIMO_MESES_SOBREPOSTOS = 12
NIVEL_CONFIANCA = 0.95

MOTIVO_AMOSTRA_INSUFICIENTE = "amostra_insuficiente"


@dataclass(frozen=True)
class ResultadoDefasagem:
    """Um lag testado. `lag_meses > 0` significa que `serie_a` antecede
    `serie_b` (o valor de `serie_a` no mês t é pareado com `serie_b` no
    mês t+lag); `lag_meses < 0` é o inverso. `intervalo_confianca` já
    vem ajustado por Bonferroni pelo `n_testes` informado - `None`
    quando a amostra não sustenta o cálculo."""

    lag_meses: int
    coeficiente: float | None
    intervalo_confianca: tuple[float, float] | None
    n_pontos: int
    n_testes: int
    significativo: bool
    motivo_indisponivel: str | None


def _mes_mais(mes: date, n: int) -> date:
    total = (mes.year * 12 + (mes.month - 1)) + n
    return date(total // 12, total % 12 + 1, 1)


def _alinhar_series(
    serie_a: list[PontoMensal], serie_b: list[PontoMensal], lag: int
) -> tuple[list[float], list[float]]:
    valores_a = {p.mes: p.valor for p in serie_a}
    valores_b = {p.mes: p.valor for p in serie_b}

    xs: list[float] = []
    ys: list[float] = []
    for mes in sorted(valores_a):
        mes_b = _mes_mais(mes, lag)
        if mes_b in valores_b:
            xs.append(valores_a[mes])
            ys.append(valores_b[mes_b])
    return xs, ys


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    media_x = sum(xs) / n
    media_y = sum(ys) / n
    covariancia = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    variancia_x = sum((x - media_x) ** 2 for x in xs)
    variancia_y = sum((y - media_y) ** 2 for y in ys)
    if variancia_x == 0 or variancia_y == 0:
        # uma das duas séries é constante na janela - correlação
        # indefinida, não zero (zero afirmaria "sem relação", que é uma
        # informação diferente de "não dá pra medir aqui").
        return None
    return covariancia / math.sqrt(variancia_x * variancia_y)


def _intervalo_confianca_bonferroni(
    r: float, n: int, n_testes: int, nivel: float = NIVEL_CONFIANCA
) -> tuple[float, float]:
    """Transformação de Fisher (z = artanh(r)), com o erro padrão
    ajustado pelo nível de confiança dividido por `n_testes` (correção
    de Bonferroni) em vez do 95% "cru" - quanto mais testes, mais largo
    o intervalo precisa ser pra manter a taxa de falso positivo global
    em `1 - nivel`."""
    alpha = 1 - nivel
    r_limitado = max(min(r, 0.999999), -0.999999)
    z = math.atanh(r_limitado)
    erro_padrao = 1 / math.sqrt(n - 3)
    z_critico = statistics.NormalDist().inv_cdf(1 - alpha / (2 * n_testes))
    baixo = math.tanh(z - z_critico * erro_padrao)
    alto = math.tanh(z + z_critico * erro_padrao)
    return (baixo, alto)


def calcular_correlacao_cruzada(
    serie_a: list[PontoMensal],
    serie_b: list[PontoMensal],
    *,
    lag_maximo: int = LAG_MAXIMO_PADRAO,
    piso_minimo_meses: int = PISO_MINIMO_MESES_SOBREPOSTOS,
    n_testes: int | None = None,
) -> list[ResultadoDefasagem]:
    """Um `ResultadoDefasagem` por lag de `-lag_maximo` a `+lag_maximo`
    (`2*lag_maximo+1` no total). `n_testes` (correção de Bonferroni) é
    esse total por padrão - quem monta uma análise por bairro (seção
    3.1: "~75 bairros × 13 defasagens × 2 direções... mais de 1.900
    testes") deve passar o total real de testes através de todos os
    bairros, não deixar cada bairro se corrigir isoladamente."""
    lags = range(-lag_maximo, lag_maximo + 1)
    testes_reais = n_testes if n_testes is not None else len(lags)

    resultados: list[ResultadoDefasagem] = []
    for lag in lags:
        xs, ys = _alinhar_series(serie_a, serie_b, lag)
        n = len(xs)
        if n < piso_minimo_meses:
            resultados.append(
                ResultadoDefasagem(lag, None, None, n, testes_reais, False, MOTIVO_AMOSTRA_INSUFICIENTE)
            )
            continue

        r = _pearson(xs, ys)
        if r is None:
            resultados.append(
                ResultadoDefasagem(lag, None, None, n, testes_reais, False, MOTIVO_AMOSTRA_INSUFICIENTE)
            )
            continue

        intervalo = _intervalo_confianca_bonferroni(r, n, testes_reais)
        significativo = not (intervalo[0] <= 0 <= intervalo[1])
        resultados.append(
            ResultadoDefasagem(lag, r, intervalo, n, testes_reais, significativo, None)
        )
    return resultados


def defasagem_mais_forte(resultados: list[ResultadoDefasagem]) -> ResultadoDefasagem | None:
    """Entre os lags significativos (IC, já corrigido, não contém
    zero), o de maior |coeficiente| - "reporte a defasagem de
    correlação máxima" (seção 3.1). `None` quando nenhum lag é
    significativo - resultado válido, não uma falha (seção 12: "se a
    relação não se sustentar... isso é um resultado válido")."""
    significativos = [r for r in resultados if r.significativo and r.coeficiente is not None]
    if not significativos:
        return None
    return max(significativos, key=lambda r: abs(r.coeficiente))
