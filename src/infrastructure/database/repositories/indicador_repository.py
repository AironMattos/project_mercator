from __future__ import annotations

from datetime import date

from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session

from analytics.features import PontoMensal
from commerce.cnae import normalizar_codigo_cnae
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade

FONTE_ID = "alvaras_smf"

# Quantos meses pra trás materializamos com zero-fill. Precisa cobrir não
# só a janela de baseline (24 meses) como também o caso de
# servico_indicadores.indicadores_aberturas_por_mes_bairro, que busca a
# série UMA vez pro mês mais recente de uma lista (ex.: os até 12 meses do
# preset "últimos 12 meses" do frontend) e reusa pra calcular baseline de
# cada mês dessa lista - o mês mais antigo da lista ainda precisa de 24
# meses de janela ANTES dele. 24 (janela) + 12 (maior preset) + folga.
MESES_HISTORICO_PADRAO = 40


def _mes_seguinte(mes: date, n: int) -> date:
    total = (mes.year * 12 + (mes.month - 1)) + n
    return date(total // 12, total % 12 + 1, 1)


def _zero_fill(
    contagens: dict[date, float], mes_referencia: date, meses_historico: int
) -> list[PontoMensal]:
    """Preenche com 0 os meses sem nenhum registro de INICIO_ATIVIDADE
    dentro da janela - ausência aqui é informação real ("nenhuma entidade
    conhecida abriu nesse mês"), não "não sabemos". Diferente do histórico
    de fechamento (ver serie_desaparecimentos_bairro), que não é zero-
    preenchido porque ausência lá significa "não processamos essa
    comparação de snapshot", não "zero fechamentos".
    """
    inicio = _mes_seguinte(mes_referencia, -meses_historico)
    pontos = []
    mes = inicio
    while mes <= mes_referencia:
        pontos.append(PontoMensal(mes=mes, valor=contagens.get(mes, 0.0)))
        mes = _mes_seguinte(mes, 1)
    return pontos


def _contagens_inicio_atividade_por_territorio_mes(
    session: Session,
    *,
    categoria_id: str | None,
    categoria_por_codigo: dict[str, str],
    territorio_id: str | None = None,
) -> dict[str, dict[date, float]]:
    """Agrupa INICIO_ATIVIDADE (data real por registro, não a data do
    evento de detecção) por bairro e mês, deduplicado por entidade - o
    mesmo alvará aparece em mais de um snapshot com o mesmo
    INICIO_ATIVIDADE (é um fato histórico fixo do registro, não muda), e
    contá-lo mais de uma vez infla a série. Usa DISTINCT ON pra ficar só
    com a observação mais recente de cada entidade.

    Retorna {territorio_id: {mes: contagem}} - só bairros/meses com pelo
    menos 1 ocorrência aparecem aqui (não zero-preenchido, ver _zero_fill).
    """
    tabela = ObservacaoEntidade
    territorio_expr = tabela.atributos["territorio_id"].astext
    inicio_expr = tabela.atributos["inicio_atividade"].astext
    cnae_expr = tabela.atributos["cnae_principal"].astext

    ultima_observacao = (
        select(
            tabela.entidade_id,
            territorio_expr.label("territorio_id"),
            inicio_expr.label("inicio_atividade"),
            cnae_expr.label("cnae_principal"),
        )
        .distinct(tabela.entidade_id)
        .where(tabela.fonte_id == FONTE_ID, inicio_expr.isnot(None))
        .order_by(tabela.entidade_id, tabela.observado_em.desc())
        .subquery()
    )

    mes_expr = func.date_trunc("month", ultima_observacao.c.inicio_atividade.cast(Date))
    stmt = (
        select(
            ultima_observacao.c.territorio_id,
            mes_expr.label("mes"),
            ultima_observacao.c.cnae_principal,
            func.count().label("contagem"),
        )
        .where(ultima_observacao.c.territorio_id.isnot(None))
        .group_by(ultima_observacao.c.territorio_id, mes_expr, ultima_observacao.c.cnae_principal)
    )
    if territorio_id is not None:
        stmt = stmt.where(ultima_observacao.c.territorio_id == territorio_id)

    resultado: dict[str, dict[date, float]] = {}
    for row in session.execute(stmt):
        if categoria_id is not None:
            codigo = normalizar_codigo_cnae(row.cnae_principal)
            if categoria_por_codigo.get(codigo) != categoria_id:
                continue
        mes = row.mes.date() if hasattr(row.mes, "date") else row.mes
        por_mes = resultado.setdefault(row.territorio_id, {})
        por_mes[mes] = por_mes.get(mes, 0.0) + row.contagem

    return resultado


def serie_aberturas_bairro(
    session: Session,
    *,
    territorio_id: str,
    categoria_id: str | None,
    categoria_por_codigo: dict[str, str],
    mes_referencia: date,
    meses_historico: int = MESES_HISTORICO_PADRAO,
) -> list[PontoMensal]:
    """Série mensal de aberturas de um bairro, baseada em INICIO_ATIVIDADE
    - tem profundidade real de anos mesmo só com os 2 snapshots de evento
    já processados, porque a data em si é um atributo fixo do registro, não
    depende de quantas vezes comparamos snapshots. Zero-preenchida dentro
    da janela solicitada.
    """
    contagens = _contagens_inicio_atividade_por_territorio_mes(
        session,
        categoria_id=categoria_id,
        categoria_por_codigo=categoria_por_codigo,
        territorio_id=territorio_id,
    )
    return _zero_fill(contagens.get(territorio_id, {}), mes_referencia, meses_historico)


def series_aberturas_todos_bairros(
    session: Session,
    *,
    categoria_id: str | None,
    categoria_por_codigo: dict[str, str],
    mes_referencia: date,
    meses_historico: int = MESES_HISTORICO_PADRAO,
) -> dict[str, list[PontoMensal]]:
    """Mesma série de serie_aberturas_bairro, mas pra todos os bairros de
    uma vez (uma query só) - usado pelo ranking, que precisa da série de
    75 bairros; evitar 75 idas ao banco.
    """
    contagens = _contagens_inicio_atividade_por_territorio_mes(
        session, categoria_id=categoria_id, categoria_por_codigo=categoria_por_codigo
    )
    return {
        territorio_id: _zero_fill(por_mes, mes_referencia, meses_historico)
        for territorio_id, por_mes in contagens.items()
    }


def quebra_categoria_aberturas_bairro(
    session: Session,
    *,
    territorio_id: str,
    mes_referencia: date,
    categoria_por_codigo: dict[str, str],
    limite: int = 5,
) -> list[tuple[str | None, int]]:
    """As categorias que mais contribuíram pra aberturas (INICIO_ATIVIDADE)
    de um bairro num mês específico - as top `limite`, não o catálogo
    inteiro. Retorna [(categoria_id, contagem), ...] desc; categoria_id
    None agrupa CNAEs não resolvidos (não descartados silenciosamente).
    """
    tabela = ObservacaoEntidade
    territorio_expr = tabela.atributos["territorio_id"].astext
    inicio_expr = tabela.atributos["inicio_atividade"].astext
    cnae_expr = tabela.atributos["cnae_principal"].astext

    ultima_observacao = (
        select(
            tabela.entidade_id,
            inicio_expr.label("inicio_atividade"),
            cnae_expr.label("cnae_principal"),
        )
        .distinct(tabela.entidade_id)
        .where(
            tabela.fonte_id == FONTE_ID,
            inicio_expr.isnot(None),
            territorio_expr == territorio_id,
        )
        .order_by(tabela.entidade_id, tabela.observado_em.desc())
        .subquery()
    )
    mes_expr = func.date_trunc("month", ultima_observacao.c.inicio_atividade.cast(Date))
    stmt = (
        select(ultima_observacao.c.cnae_principal, func.count().label("contagem"))
        .where(mes_expr == mes_referencia)
        .group_by(ultima_observacao.c.cnae_principal)
    )

    por_categoria: dict[str | None, int] = {}
    for row in session.execute(stmt):
        codigo = normalizar_codigo_cnae(row.cnae_principal)
        categoria_id = categoria_por_codigo.get(codigo)
        por_categoria[categoria_id] = por_categoria.get(categoria_id, 0) + row.contagem

    return sorted(por_categoria.items(), key=lambda item: item[1], reverse=True)[:limite]
