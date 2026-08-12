from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ContagemEventos:
    """Contagem de eventos por bairro, categoria, mês e tipo de evento.

    A primeira (e por enquanto única) feature do Radar de Comércio -
    totalmente derivada de events.fato_evento_territorial, recomputável a
    qualquer momento (não é um dado de origem, não precisa de imutabilidade
    como entidade/observação/evento).
    """

    territorio_id: str | None
    categoria_id: str | None
    mes: date
    event_type: str
    contagem: int


@dataclass(frozen=True)
class PontoMensal:
    """Um ponto de uma série temporal mensal - o valor de um indicador
    (ex.: aberturas) num mês. `mes` é sempre normalizado pro dia 1 (mesma
    convenção de ContagemEventos.mes). De propósito agnóstico à origem do
    valor: quem monta a série decide se vem de fato_evento_territorial ou
    de INICIO_ATIVIDADE bruto - ver nota em indicadores.py sobre por que
    aberturas e fechamentos usam fontes diferentes de profundidade
    histórica.
    """

    mes: date
    valor: float


@dataclass(frozen=True)
class Baseline:
    """Resultado de calcular_baseline(). `motivo_indisponivel` vem
    preenchido (e `baseline`/`variacao_pct` vêm None) sempre que a base
    histórica não é confiável o suficiente para sustentar uma média -
    nunca mostramos um número calculado sobre uma base fraca."""

    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    motivo_indisponivel: str | None


@dataclass(frozen=True)
class Tendencia:
    """Resultado de calcular_tendencia(). `classificacao` é uma de
    "acelerando"/"desacelerando"/"estavel", ou None quando indisponível."""

    classificacao: str | None
    variacao_pct: float | None
    motivo_indisponivel: str | None


@dataclass(frozen=True)
class ItemComBaseline:
    """Entrada de calcular_ranking() - um bairro (ou bairro+categoria) já
    com baseline/tendência calculados, pronto pra ser ordenado."""

    territorio_id: str | None
    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    tendencia: str | None = None


@dataclass(frozen=True)
class ItemRanking:
    """Saída de calcular_ranking() - um item elegível (variacao_pct não
    None), com posição no ranking e o total de itens elegíveis."""

    territorio_id: str | None
    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    tendencia: str | None
    posicao: int
    total: int
