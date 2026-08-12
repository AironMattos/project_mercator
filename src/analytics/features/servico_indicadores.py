"""Orquestra repositório + cálculo puro (analytics.features.indicadores)
pra responder às perguntas que a API expõe: baseline/tendência de um
bairro, ranking de crescimento, resumo completo de um bairro. Faz I/O
(recebe uma Session) - ao lado de run_contagem_eventos.py, que já faz o
mesmo dentro deste pacote; a diferença é que aqui é sob demanda (uma
request HTTP), não um pipeline em lote.

Mora aqui, não em apps/api/routers/, pra manter as rotas finas (só
parseiam query param e devolvem o schema Pydantic) - ver o princípio do
projeto de rotas sem lógica de negócio própria.
"""

from __future__ import annotations

import time
from datetime import date

from sqlalchemy.orm import Session

from analytics.features.indicadores import (
    Baseline,
    ItemComBaseline,
    ItemRanking,
    PontoMensal,
    Tendencia,
    calcular_baseline,
    calcular_ranking,
    calcular_tendencia,
)
from infrastructure.database.repositories.categoria_repository import (
    categoria_id_por_codigo_cnae,
)
from infrastructure.database.repositories.feature_repository import (
    consultar_cobertura_temporal,
    consultar_metricas_comercio,
)
from infrastructure.database.repositories.indicador_repository import (
    quebra_categoria_aberturas_bairro,
    serie_aberturas_bairro,
    series_aberturas_todos_bairros,
)

# Distinto de MOTIVO_HISTORICO_INSUFICIENTE (que é sobre profundidade de
# passado): esse é sobre o mês em si ainda não estar coberto por
# INICIO_ATIVIDADE. Ver periodo_padrao_aberturas() - o snapshot rotulado
# "2026-08-01" não tem NENHUMA entrada real de INICIO_ATIVIDADE em agosto
# ainda (cobre só até o fim de julho). Sem esse motivo dedicado,
# GET /metricas/comercio?territorio_id=... mostraria, pra esse mês
# específico, algo como "aberturas: 798, variacao_pct: -100%" - o -100%
# viria de comparar um valor_atual=0 (mês ainda sem cobertura) contra um
# baseline real, parecendo uma queda dramática que não existe.
MOTIVO_MES_INCOMPLETO = "mes_incompleto"


def _mes_anterior(mes: date) -> date:
    total = (mes.year * 12 + (mes.month - 1)) - 1
    return date(total // 12, total % 12 + 1, 1)


def periodo_padrao_aberturas(session: Session) -> date:
    """O "último mês fechado" pra fins de aberturas - um mês antes do
    último mês de evento processado (cobertura.mes_fim), não o mês em si.

    Motivo: o snapshot rotulado "2026-08-01" reflete o estado consolidado
    até o fim de JULHO (achado do checkpoint 3, o mesmo vale aqui) -
    INICIO_ATIVIDADE praticamente não tem entrada real pro mês do rótulo
    ainda. Sem essa correção, o "período padrão" mostraria aberturas=0 pra
    todo mundo, não porque não houve abertura, mas porque o mês do rótulo
    ainda não foi coberto pela fonte.
    """
    _, mes_fim = consultar_cobertura_temporal(session)
    if mes_fim is None:
        hoje = date.today()
        return date(hoje.year, hoje.month, 1)
    return _mes_anterior(mes_fim)


def _valor_no_mes(serie: list[PontoMensal], mes: date) -> float:
    return next((p.valor for p in serie if p.mes == mes), 0.0)


def motivo_indisponivel_combinado(baseline: Baseline, tendencia: Tendencia) -> str | None:
    """Combina os motivos de indisponibilidade de baseline e tendência num
    único motivo pro nível de exibição da API.

    Só marca o indicador inteiro como indisponível quando um dos sinais
    PRINCIPAIS (o valor do baseline em si, ou a classificação de
    tendência) está ausente. Um `variacao_pct=None` isolado - caso de
    baseline zero (ver MOTIVO_BASELINE_ZERO em indicadores.py), onde
    baseline/classificação continuam sendo números/rótulos reais e só a
    razão percentual é que não é representável - não conta como "o
    indicador é indisponível": baseline=0.125 e tendência="acelerando" são
    informação real, mesmo que a tendência não tenha um percentual exato
    pra mostrar junto.
    """
    if baseline.baseline is None:
        return baseline.motivo_indisponivel
    if tendencia.classificacao is None:
        return tendencia.motivo_indisponivel
    if baseline.variacao_pct is None:
        return baseline.motivo_indisponivel
    return None


def indicador_aberturas_bairro(
    session: Session,
    *,
    territorio_id: str,
    categoria_id: str | None,
    mes_referencia: date,
    categoria_por_codigo: dict[str, str] | None = None,
) -> tuple[Baseline, Tendencia]:
    """Reaproveita o cache de série citywide (_series_aberturas_cached) em
    vez de chamar serie_aberturas_bairro diretamente - essa query, mesmo
    pedindo só um bairro, faz DISTINCT ON sobre TODAS as ~515 mil
    observações antes de filtrar (o dedup por entidade tem que considerar
    a cidade inteira), então custa quase o mesmo que buscar todos os
    bairros de uma vez. Sem isso, abrir o painel de detalhe de um bairro
    reconsultava do zero mesmo depois do ranking já ter aquecido o cache -
    achado ao medir o tempo real de resposta (~1,8s mesmo com o ranking em
    cache, contra ~0,25s depois dessa mudança).
    """
    series = _series_aberturas_cached(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia
    )
    if territorio_id in series:
        serie = series[territorio_id]
    else:
        # Bairro sem nenhuma ocorrência citywide (não aparece no dict
        # cacheado) - cai pro caminho direto pra manter o zero-fill
        # correto (baseline=0.0/"baseline_zero", não uma série vazia que
        # daria "historico_insuficiente" incorretamente).
        categoria_por_codigo = categoria_por_codigo or categoria_id_por_codigo_cnae(session)
        serie = serie_aberturas_bairro(
            session,
            territorio_id=territorio_id,
            categoria_id=categoria_id,
            categoria_por_codigo=categoria_por_codigo,
            mes_referencia=mes_referencia,
        )
    valor_atual = _valor_no_mes(serie, mes_referencia)
    baseline = calcular_baseline(serie, mes_referencia, valor_atual)
    tendencia = calcular_tendencia(serie, mes_referencia)
    return baseline, tendencia


def indicador_saldo_bairro(
    session: Session,
    *,
    territorio_id: str,
    categoria_id: str | None,
) -> tuple[Baseline, Tendencia, date | None]:
    """Baseline/tendência de saldo (aberturas de evento - desaparecimentos)
    - ao contrário de aberturas, usa o próprio mes_fim de
    fato_evento_territorial como referência (não o corrigido de
    periodo_padrao_aberturas), porque saldo só existe nos meses em que uma
    comparação de snapshot realmente rodou - não tem o mesmo "atraso de
    cobertura" que INICIO_ATIVIDADE tem. Hoje isso deve vir indisponível
    (só 1 mês real de fato_evento_territorial) - é o comportamento
    correto, não um bug a corrigir aqui.
    """
    _, mes_fim = consultar_cobertura_temporal(session)
    if mes_fim is None:
        vazio = Baseline(valor_atual=0.0, baseline=None, variacao_pct=None, motivo_indisponivel="historico_insuficiente")
        vazia = Tendencia(classificacao=None, variacao_pct=None, motivo_indisponivel="historico_insuficiente")
        return vazio, vazia, None

    linhas = consultar_metricas_comercio(session, territorio_id=territorio_id, categoria_id=categoria_id)
    serie = [
        PontoMensal(mes=linha["mes"], valor=float(linha["aberturas"] - linha["desaparecimentos"]))
        for linha in linhas
        if linha["mes"] is not None
    ]
    valor_atual = _valor_no_mes(serie, mes_fim)
    baseline = calcular_baseline(serie, mes_fim, valor_atual)
    tendencia = calcular_tendencia(serie, mes_fim)
    return baseline, tendencia, mes_fim


def indicadores_aberturas_por_mes_bairro(
    session: Session,
    *,
    territorio_id: str,
    categoria_id: str | None,
    meses: list[date],
) -> dict[date, tuple[Baseline, Tendencia]]:
    """Baseline/tendência de aberturas pra cada mês em `meses` de uma vez -
    busca a série de INICIO_ATIVIDADE do bairro uma única vez (evita N
    idas ao banco pra série temporal de N meses, ver uso em
    GET /metricas/comercio). O mais recente de `meses` vira a referência
    da janela de zero-fill (os anteriores já ficam cobertos por ela).
    """
    if not meses:
        return {}
    categoria_por_codigo = categoria_id_por_codigo_cnae(session)
    mes_mais_recente = max(meses)
    serie = serie_aberturas_bairro(
        session,
        territorio_id=territorio_id,
        categoria_id=categoria_id,
        categoria_por_codigo=categoria_por_codigo,
        mes_referencia=mes_mais_recente,
    )
    ultimo_mes_completo = periodo_padrao_aberturas(session)

    resultado = {}
    for mes in meses:
        if mes > ultimo_mes_completo:
            resultado[mes] = (
                Baseline(valor_atual=0.0, baseline=None, variacao_pct=None, motivo_indisponivel=MOTIVO_MES_INCOMPLETO),
                Tendencia(classificacao=None, variacao_pct=None, motivo_indisponivel=MOTIVO_MES_INCOMPLETO),
            )
            continue
        valor_atual = _valor_no_mes(serie, mes)
        baseline = calcular_baseline(serie, mes, valor_atual)
        tendencia = calcular_tendencia(serie, mes)
        resultado[mes] = (baseline, tendencia)
    return resultado


MESES_SPARKLINE = 12


def _ultimos_meses(serie: list[PontoMensal], mes_referencia: date, n: int) -> list[PontoMensal]:
    inicio = _meses_atras(mes_referencia, n - 1)
    return [p for p in serie if inicio <= p.mes <= mes_referencia]


def _meses_atras(mes: date, n: int) -> date:
    total = (mes.year * 12 + (mes.month - 1)) - n
    return date(total // 12, total % 12 + 1, 1)


# Cache de processo (dict simples, sem dependência nova) - a query de
# origem (DISTINCT ON sobre ~515 mil observações) leva vários segundos pra
# rodar pra cidade inteira, e custa quase o mesmo mesmo quando só um bairro
# é pedido (o dedup por entidade tem que considerar todo mundo antes de
# filtrar). Sem isso, abrir o painel de detalhe de um bairro (que precisa
# tanto da série daquele bairro quanto da posição no ranking completo)
# ficava tão lento quanto montar tudo do zero a cada clique - 12s reais,
# medido via Playwright, caindo pra ~0,25s depois do cache aquecido. TTL
# curto: o dado subjacente só muda quando um novo snapshot é processado
# (mensal) - isso é só pra suavizar cliques em sequência (ranking ->
# detalhe de bairro), não uma garantia de atualização em tempo real; não
# tem invalidação manual porque não existe um endpoint de escrita que
# mudaria esse dado no meio de uma sessão de uso.
_CACHE_SERIES: dict[tuple[str | None, date], tuple[dict[str, list[PontoMensal]], float]] = {}
_CACHE_RANKING: dict[tuple[str | None, date], tuple[list[ItemRanking], dict[str, list[PontoMensal]], float]] = {}
_CACHE_TTL_SEGUNDOS = 300


def _series_aberturas_cached(
    session: Session, *, categoria_id: str | None, mes_referencia: date
) -> dict[str, list[PontoMensal]]:
    chave = (categoria_id, mes_referencia)
    agora = time.monotonic()
    em_cache = _CACHE_SERIES.get(chave)
    if em_cache is not None and (agora - em_cache[1]) < _CACHE_TTL_SEGUNDOS:
        return em_cache[0]

    categoria_por_codigo = categoria_id_por_codigo_cnae(session)
    series = series_aberturas_todos_bairros(
        session,
        categoria_id=categoria_id,
        categoria_por_codigo=categoria_por_codigo,
        mes_referencia=mes_referencia,
    )
    _CACHE_SERIES[chave] = (series, agora)
    return series


def _montar_ranking_aberturas_completo(
    session: Session, *, categoria_id: str | None, mes_referencia: date
) -> tuple[list[ItemRanking], dict[str, list[PontoMensal]]]:
    """O ranking inteiro (sem limite) + as séries completas de cada bairro
    - a parte cara e cacheável de montar_ranking_aberturas().
    """
    chave = (categoria_id, mes_referencia)
    agora = time.monotonic()
    em_cache = _CACHE_RANKING.get(chave)
    if em_cache is not None and (agora - em_cache[2]) < _CACHE_TTL_SEGUNDOS:
        return em_cache[0], em_cache[1]

    series = _series_aberturas_cached(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia
    )

    itens = []
    for territorio_id, serie in series.items():
        valor_atual = _valor_no_mes(serie, mes_referencia)
        baseline = calcular_baseline(serie, mes_referencia, valor_atual)
        tendencia = calcular_tendencia(serie, mes_referencia)
        itens.append(
            ItemComBaseline(
                territorio_id=territorio_id,
                valor_atual=valor_atual,
                baseline=baseline.baseline,
                variacao_pct=baseline.variacao_pct,
                tendencia=tendencia.classificacao,
            )
        )

    ranking = calcular_ranking(itens)
    sparklines = {
        item.territorio_id: _ultimos_meses(series[item.territorio_id], mes_referencia, MESES_SPARKLINE)
        for item in ranking
        if item.territorio_id in series
    }
    _CACHE_RANKING[chave] = (ranking, sparklines, agora)
    return ranking, sparklines


def montar_ranking_aberturas(
    session: Session,
    *,
    categoria_id: str | None,
    mes_referencia: date,
    limite: int | None = None,
) -> tuple[list[ItemRanking], dict[str, list[PontoMensal]]]:
    """Devolve o ranking e, junto, os últimos MESES_SPARKLINE pontos da
    série de cada bairro elegível - o formato de resposta pedido no
    prompt de referência ({territorio_id, nome, valor_atual, baseline,
    variacao_pct, tendencia, posicao, total}) não incluía uma série pro
    sparkline do checkpoint 8c/3.1, então estendi a resposta da API com um
    campo `serie` a mais (ver resumo do checkpoint 8c) - devolver a série
    aqui evita reconsultar o banco no router só pra montar o sparkline.
    """
    ranking, sparklines = _montar_ranking_aberturas_completo(
        session, categoria_id=categoria_id, mes_referencia=mes_referencia
    )
    if limite is not None:
        ranking = ranking[:limite]
    return ranking, sparklines


def quebra_categoria_bairro(
    session: Session,
    *,
    territorio_id: str,
    mes_referencia: date,
    limite: int = 5,
) -> list[tuple[str | None, int]]:
    categoria_por_codigo = categoria_id_por_codigo_cnae(session)
    return quebra_categoria_aberturas_bairro(
        session,
        territorio_id=territorio_id,
        mes_referencia=mes_referencia,
        categoria_por_codigo=categoria_por_codigo,
        limite=limite,
    )
