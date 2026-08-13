from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from analytics.features import PontoMensal
from infrastructure.database.orm.contagem_inicio_atividade import ContagemInicioAtividade

# Quantos meses pra trás materializamos com zero-fill (na leitura, não na
# tabela em si - a tabela só tem os meses com contagem > 0). Precisa
# cobrir não só a janela de baseline (24 meses) como também o caso de
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
    de fechamento (feature_repository), que não é zero-preenchido porque
    ausência lá significa "não processamos essa comparação de snapshot",
    não "zero fechamentos".
    """
    inicio = _mes_seguinte(mes_referencia, -meses_historico)
    pontos = []
    mes = inicio
    while mes <= mes_referencia:
        pontos.append(PontoMensal(mes=mes, valor=contagens.get(mes, 0.0)))
        mes = _mes_seguinte(mes, 1)
    return pontos


def serie_aberturas_bairro(
    session: Session,
    *,
    territorio_id: str,
    categoria_id: str | None,
    mes_referencia: date,
    meses_historico: int = MESES_HISTORICO_PADRAO,
) -> list[PontoMensal]:
    """Série mensal de aberturas de um bairro, lida de
    analytics.contagem_inicio_atividade (materializada - ver
    run_contagem_inicio_atividade.py; a query ao vivo contra
    observacao_entidade era cara demais pra rodar por request, achado
    medindo o tempo de resposta real de /ranking/comercio e
    /bairros/{id}/resumo). Zero-preenchida dentro da janela solicitada.
    """
    tabela = ContagemInicioAtividade
    stmt = select(tabela.mes, func.sum(tabela.contagem)).where(tabela.territorio_id == territorio_id)
    if categoria_id is not None:
        stmt = stmt.where(tabela.categoria_id == categoria_id)
    stmt = stmt.group_by(tabela.mes)

    contagens = {mes: float(soma) for mes, soma in session.execute(stmt)}
    return _zero_fill(contagens, mes_referencia, meses_historico)


def series_aberturas_todos_bairros(
    session: Session,
    *,
    categoria_id: str | None,
    mes_referencia: date,
    meses_historico: int = MESES_HISTORICO_PADRAO,
) -> dict[str, list[PontoMensal]]:
    """Mesma série de serie_aberturas_bairro, mas pra todos os bairros de
    uma vez (uma query só) - usado pelo ranking, que precisa da série de
    ~75 bairros; evita repetir a agregação por bairro.
    """
    tabela = ContagemInicioAtividade
    stmt = select(tabela.territorio_id, tabela.mes, func.sum(tabela.contagem))
    if categoria_id is not None:
        stmt = stmt.where(tabela.categoria_id == categoria_id)
    stmt = stmt.group_by(tabela.territorio_id, tabela.mes)

    contagens: dict[str, dict[date, float]] = {}
    for territorio_id, mes, soma in session.execute(stmt):
        contagens.setdefault(territorio_id, {})[mes] = float(soma)

    return {
        territorio_id: _zero_fill(por_mes, mes_referencia, meses_historico)
        for territorio_id, por_mes in contagens.items()
    }


def series_aberturas_por_categoria(
    session: Session,
    *,
    territorio_id: str | None,
    mes_referencia: date,
    meses_historico: int = MESES_HISTORICO_PADRAO,
) -> dict[str, list[PontoMensal]]:
    """Mesma série de series_aberturas_todos_bairros, mas agrupada por
    categoria_id em vez de territorio_id - cidade inteira por padrão, ou
    um bairro específico via `territorio_id` (checkpoint 11b: "categorias
    em alta/em queda" no Radar, cidade inteira; a mesma função também serve
    o perfil de um bairro específico). Categoria não resolvida
    (categoria_id IS NULL) fica de fora - não dá pra rankear "sem
    categoria".
    """
    tabela = ContagemInicioAtividade
    stmt = select(tabela.categoria_id, tabela.mes, func.sum(tabela.contagem)).where(
        tabela.categoria_id.isnot(None)
    )
    if territorio_id is not None:
        stmt = stmt.where(tabela.territorio_id == territorio_id)
    stmt = stmt.group_by(tabela.categoria_id, tabela.mes)

    contagens: dict[str, dict[date, float]] = {}
    for categoria_id, mes, soma in session.execute(stmt):
        contagens.setdefault(categoria_id, {})[mes] = float(soma)

    return {
        categoria_id: _zero_fill(por_mes, mes_referencia, meses_historico)
        for categoria_id, por_mes in contagens.items()
    }


def quebra_categoria_aberturas_bairro(
    session: Session,
    *,
    territorio_id: str,
    mes_referencia: date,
    limite: int = 5,
) -> list[tuple[str | None, int]]:
    """As categorias que mais contribuíram pra aberturas (INICIO_ATIVIDADE)
    de um bairro num mês específico - as top `limite`, não o catálogo
    inteiro. Retorna [(categoria_id, contagem), ...] desc; categoria_id
    None agrupa CNAEs não resolvidos (não descartados silenciosamente).
    """
    tabela = ContagemInicioAtividade
    stmt = (
        select(tabela.categoria_id, func.sum(tabela.contagem).label("total"))
        .where(tabela.territorio_id == territorio_id, tabela.mes == mes_referencia)
        .group_by(tabela.categoria_id)
        .order_by(func.sum(tabela.contagem).desc())
        .limit(limite)
    )
    return [(categoria_id, int(total)) for categoria_id, total in session.execute(stmt)]


def substituir_contagem_inicio_atividade(
    session: Session, linhas: list[tuple[str, str | None, date, int]]
) -> int:
    """linhas: [(territorio_id, categoria_id, mes, contagem), ...].
    Recalcula do zero (delete + insert) - seguro porque a tabela é 100%
    derivada de canonical.observacao_entidade, não é fonte de verdade.
    """
    session.execute(delete(ContagemInicioAtividade))
    if not linhas:
        return 0

    rows = [
        {"territorio_id": t, "categoria_id": c, "mes": m, "contagem": n}
        for t, c, m, n in linhas
    ]
    session.execute(ContagemInicioAtividade.__table__.insert(), rows)
    return len(rows)
