"""O termômetro do Radar de Anúncios (checkpoint 12f, seção 2 do prompt
de referência) - métricas de aquecimento por bairro × tipologia ×
operação × mês. Cada função é pequena e pura de propósito (mesmo
espírito de analytics/features/indicadores.py) - a montagem de uma
célula completa (consultas SQL, agrupamento) é responsabilidade do
repositório/pipeline, não deste módulo.

Nenhuma função aqui produz um score composto - cada métrica é isolada,
com fórmula publicável em /metodologia quando a interface existir
(checkpoint 12i). O quadrante de aquecimento (seção 2.1) é a única
"classificação" e é derivado de duas métricas visíveis, nunca um número
oculto.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

# Seção 2.2 do prompt de referência: célula com menos de 30 anúncios não
# exibe mediana, não entra em ranking e não recebe classificação de
# quadrante - mas a contagem crua (novos_anuncios, estoque) continua
# visível, "amostra insuficiente" nunca vira "célula vazia sem explicação".
PISO_MINIMO_AMOSTRA = 30

MOTIVO_AMOSTRA_INSUFICIENTE = "amostra_insuficiente"

# O quadrante de aquecimento usa o mesmo motivo "historico_insuficiente"
# de analytics.features.indicadores quando a baseline de preço/permanência
# não existe ainda (ver classificar_quadrante_aquecimento) - não inventa
# um terceiro motivo, mas quem monta a célula completa (repositório) é
# responsável por propagar esse motivo, não este módulo.

AQUECENDO = "aquecendo"
OTIMISMO_NAO_VALIDADO = "otimismo_nao_validado"
AJUSTANDO = "ajustando"
DESACELERANDO_QUADRANTE = "desacelerando"


@dataclass(frozen=True)
class EstatisticaPreco:
    """Mediana e quartis de uma lista de preços - None quando a amostra
    (n < PISO_MINIMO_AMOSTRA) não sustenta uma mediana confiável."""

    mediana: float | None
    p25: float | None
    p75: float | None
    n: int
    motivo_indisponivel: str | None


@dataclass(frozen=True)
class PressaoPreco:
    """% de anúncios ativos que tiveram PRECO_ALTERADO pra cima vs. pra
    baixo no período, e a mediana da variação - seção 2 do prompt de
    referência ("quem está reajustando, e para onde")."""

    pct_subiu: float | None
    pct_desceu: float | None
    variacao_mediana_pct: float | None
    n: int
    motivo_indisponivel: str | None


def amostra_e_suficiente(n: int, piso: int = PISO_MINIMO_AMOSTRA) -> bool:
    return n >= piso


def contar_novos_anuncios(tipos_evento: list[str]) -> int:
    """"Novos anúncios" (entrada de oferta) soma ANUNCIO_PUBLICADO e
    REANUNCIO - os dois representam uma entidade nova aparecendo na
    oferta ativa. Mesmo raciocínio já aplicado a `aberturas` no Radar de
    Comércio (checkpoint 8: ABERTURA_CONFIRMADA e PRIMEIRA_OBSERVACAO
    somados, não só um dos dois) - REANUNCIO é uma leitura mais específica
    do mesmo fato "apareceu na oferta", não uma categoria à parte."""
    return sum(1 for t in tipos_evento if t in ("ANUNCIO_PUBLICADO", "REANUNCIO"))


def calcular_novos_por_mil_domicilios(
    novos_anuncios: int, domicilios: int | None
) -> float | None:
    """None quando não há domicílios do Censo pro bairro (bairro não
    resolvido, ou célula sem território - nunca dividir por zero nem
    inventar um denominador)."""
    if not domicilios:
        return None
    return novos_anuncios / (domicilios / 1000)


def calcular_rotacao_oferta(
    encerrados_no_mes: int, estoque_inicio_mes: int | None
) -> float | None:
    """Encerrados no mês ÷ estoque no início do mês - "quão rápido a
    oferta se renova". None quando não há um estoque de início de mês
    conhecido (precisa de um snapshot do início do mês, não só do fim) ou
    quando esse estoque é zero (rotação indefinida sobre uma base vazia,
    mesmo tratamento de baseline_zero em indicadores.py)."""
    if not estoque_inicio_mes:
        return None
    return encerrados_no_mes / estoque_inicio_mes


def calcular_renovacao(
    novos_anuncios: int, encerrados_no_mes: int, estoque_medio: float | None
) -> float | None:
    """(novos + encerrados) ÷ estoque médio - "intensidade de movimento,
    independente da direção" (seção 2). None sobre estoque médio
    ausente/zero, mesma disciplina de calcular_rotacao_oferta."""
    if not estoque_medio:
        return None
    return (novos_anuncios + encerrados_no_mes) / estoque_medio


def calcular_permanencia_mediana(dias_ate_encerrar: list[float]) -> float | None:
    """Mediana de dias entre publicação e encerramento - "melhor
    indicador isolado de aquecimento" (seção 2). Precisa de pelo menos 1
    ciclo de vida completo conhecido (publicação E encerramento, os dois
    observados) - lista vazia (nenhum ciclo completo no período) vira
    None, não zero."""
    if not dias_ate_encerrar:
        return None
    return statistics.median(dias_ate_encerrar)


def calcular_pressao_preco(variacoes_pct: list[float]) -> PressaoPreco:
    """`variacoes_pct` é uma variação por anúncio com PRECO_ALTERADO no
    período (positiva = subiu, negativa = desceu). Amostra abaixo do piso
    não calcula % nem mediana - mesma disciplina da seção 2.2, aplicada
    aqui porque pressão de preço é tão sensível a amostra pequena quanto
    preço mediano."""
    n = len(variacoes_pct)
    if not amostra_e_suficiente(n):
        return PressaoPreco(
            pct_subiu=None,
            pct_desceu=None,
            variacao_mediana_pct=None,
            n=n,
            motivo_indisponivel=MOTIVO_AMOSTRA_INSUFICIENTE,
        )
    subiu = sum(1 for v in variacoes_pct if v > 0)
    desceu = sum(1 for v in variacoes_pct if v < 0)
    return PressaoPreco(
        pct_subiu=subiu / n,
        pct_desceu=desceu / n,
        variacao_mediana_pct=statistics.median(variacoes_pct),
        n=n,
        motivo_indisponivel=None,
    )


def calcular_estatistica_preco(precos: list[float]) -> EstatisticaPreco:
    """Mediana + P25/P75 do preço pedido (ou preço/m², a mesma função
    serve pras duas métricas da seção 2) - None em amostra abaixo do
    piso mínimo (seção 2.2), nunca uma mediana frágil sobre poucos
    pontos."""
    n = len(precos)
    if not amostra_e_suficiente(n):
        return EstatisticaPreco(
            mediana=None, p25=None, p75=None, n=n, motivo_indisponivel=MOTIVO_AMOSTRA_INSUFICIENTE
        )
    ordenados = sorted(precos)
    mediana = statistics.median(ordenados)
    # statistics.quantiles com method="inclusive" casa com a definição
    # usual de P25/P75 (percentil, não quartil exclusivo) - n=100 pra
    # pegar exatamente os cortes 25/75.
    cortes = statistics.quantiles(ordenados, n=100, method="inclusive")
    p25, p75 = cortes[24], cortes[73]
    return EstatisticaPreco(mediana=mediana, p25=p25, p75=p75, n=n, motivo_indisponivel=None)


def classificar_quadrante_aquecimento(
    variacao_preco_pct: float | None, variacao_permanencia_pct: float | None
) -> str | None:
    """O quadrante de aquecimento (seção 2.1) - duas dimensões medidas
    (variação do preço pedido, variação da permanência mediana, cada uma
    contra a própria baseline do bairro), nunca um score composto. As
    quatro leituras nomeadas:

    - preço sobe + permanência cai  -> "aquecendo" (sobe preço e ainda
      assim sai rápido)
    - preço sobe + permanência sobe -> "otimismo_nao_validado" (pede
      mais, mercado não acompanha)
    - preço cai  + permanência cai  -> "ajustando" (cedeu no preço e
      destravou)
    - preço cai  + permanência sobe -> "desacelerando" (cede no preço e
      ainda assim demora)

    None quando qualquer uma das duas variações não está disponível
    (baseline insuficiente) - nunca um palpite classificando com metade
    da informação."""
    if variacao_preco_pct is None or variacao_permanencia_pct is None:
        return None
    preco_subiu = variacao_preco_pct > 0
    permanencia_caiu = variacao_permanencia_pct < 0
    if preco_subiu and permanencia_caiu:
        return AQUECENDO
    if preco_subiu and not permanencia_caiu:
        return OTIMISMO_NAO_VALIDADO
    if not preco_subiu and permanencia_caiu:
        return AJUSTANDO
    return DESACELERANDO_QUADRANTE
