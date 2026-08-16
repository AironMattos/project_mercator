from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.anuncio.models import ClusterImovel
from domain.anuncio.resolucao import CandidatoResolucao
from infrastructure.database.orm.observacao_anuncio import (
    ImovelResolvido,
    ImovelResolvidoMembro,
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)


def listar_candidatos_resolucao_pendentes(session: Session) -> list[CandidatoResolucao]:
    """Entidades de anúncio com pelo menos uma observação gravada, ainda
    não atribuídas a nenhum cluster (`LEFT JOIN ... IS NULL` contra
    imovel_resolvido_membro, cuja PK é entidade_id) - candidatas à próxima
    rodada de domain.anuncio.resolucao.resolver_imoveis. `primeira_observado_em`
    é o MIN por entidade: é a data que ancora a janela de resolução (ver
    resolucao.py), não a observação mais recente."""
    tabela = ObservacaoAnuncioORM
    ja_resolvidas = select(ImovelResolvidoMembro.entidade_id)

    stmt = (
        select(
            tabela.entidade_id,
            tabela.fonte_id,
            tabela.impressao_digital,
            func.min(tabela.observado_em).label("primeira_observado_em"),
        )
        .where(tabela.entidade_id.not_in(ja_resolvidas))
        .group_by(tabela.entidade_id, tabela.fonte_id, tabela.impressao_digital)
    )

    return [
        CandidatoResolucao(
            entidade_id=row.entidade_id,
            fonte_id=row.fonte_id,
            impressao_digital=row.impressao_digital,
            primeira_observado_em=row.primeira_observado_em,
        )
        for row in session.execute(stmt)
    ]


def gravar_clusters(session: Session, clusters: list[ClusterImovel]) -> int:
    """Persiste os clusters resolvidos - uma entidade nunca migra de
    cluster depois de gravada (ON CONFLICT DO NOTHING na PK de
    imovel_resolvido_membro, que é entidade_id)."""
    if not clusters:
        return 0

    linhas_cluster = [
        {"cluster_id": c.cluster_id, "impressao_digital": c.impressao_digital} for c in clusters
    ]
    session.execute(insert(ImovelResolvido).values(linhas_cluster))

    linhas_membro = [
        {"entidade_id": entidade_id, "cluster_id": c.cluster_id, "fonte_id": fonte_id}
        for c in clusters
        for entidade_id, fonte_id in zip(c.entidade_ids, c.fontes)
    ]
    stmt = insert(ImovelResolvidoMembro).values(linhas_membro)
    stmt = stmt.on_conflict_do_nothing(index_elements=["entidade_id"])
    resultado = session.execute(stmt)
    return resultado.rowcount or 0
