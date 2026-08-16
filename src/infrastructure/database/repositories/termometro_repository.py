from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import Date, cast, func, not_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.database.orm.fato_evento_territorial import (
    FatoEventoTerritorial as FatoEventoTerritorialORM,
)
from infrastructure.database.orm.observacao_anuncio import (
    ImovelResolvidoMembro,
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)
from infrastructure.database.orm.termometro_anuncio import TermometroAnuncio


def consultar_estoque_e_precos_ativos(session: Session) -> list[dict]:
    """Uma linha por cluster resolvido (`imovel_resolvido_membro`) ainda
    ativo - a observação mais recente entre seus membros, desde que essa
    entidade não tenha um `ANUNCIO_ENCERRADO` gravado (nesse caso o
    cluster não conta como estoque, mesmo que outro membro mais antigo
    ainda "pareça" ativo). Esta é a base de "estoque anunciado" e "preço
    pedido" da seção 2 do prompt de referência - nunca conta o mesmo
    imóvel físico duas vezes (seção 8.1)."""
    membro = ImovelResolvidoMembro
    obs = ObservacaoAnuncioORM
    evento = FatoEventoTerritorialORM

    encerrados = select(evento.entidade_id).where(
        evento.entity_type == "anuncio_imovel", evento.event_type == "ANUNCIO_ENCERRADO"
    )

    linha_por_cluster = (
        select(
            membro.cluster_id,
            obs.territorio_id,
            obs.tipologia,
            obs.operacao,
            obs.preco,
            obs.area_util_m2,
            func.row_number()
            .over(partition_by=membro.cluster_id, order_by=obs.observado_em.desc())
            .label("posicao"),
        )
        .select_from(membro)
        .join(obs, obs.entidade_id == membro.entidade_id)
        .where(not_(membro.entidade_id.in_(encerrados)))
        .subquery()
    )

    stmt = select(
        linha_por_cluster.c.territorio_id,
        linha_por_cluster.c.tipologia,
        linha_por_cluster.c.operacao,
        linha_por_cluster.c.preco,
        linha_por_cluster.c.area_util_m2,
    ).where(linha_por_cluster.c.posicao == 1)

    return [
        {
            "territorio_id": row.territorio_id,
            "tipologia": row.tipologia,
            "operacao": row.operacao,
            "preco": float(row.preco) if row.preco is not None else None,
            "area_util_m2": float(row.area_util_m2) if row.area_util_m2 is not None else None,
        }
        for row in session.execute(stmt)
    ]


def consultar_contagem_eventos_por_celula(
    session: Session, tipos_evento: tuple[str, ...]
) -> dict[tuple[str | None, str, str, date], list[str]]:
    """Tipos de evento de anúncio (ANUNCIO_PUBLICADO/REANUNCIO/
    ANUNCIO_ENCERRADO) agrupados por (territorio_id, tipologia, operacao,
    mês) - devolve a lista bruta de event_type por célula (não só a
    contagem) pra quem chama decidir como somar (ex.: novos_anuncios soma
    dois tipos, ver contar_novos_anuncios). Tipologia/operação vêm do
    payload do evento (gravado por domain.anuncio.regras), não exigem
    voltar em observacao_anuncio."""
    evento = FatoEventoTerritorialORM
    mes_expr = cast(func.date_trunc("month", evento.data_evento), Date)

    stmt = select(
        evento.territorio_id,
        evento.payload["tipologia"].astext.label("tipologia"),
        evento.payload["operacao"].astext.label("operacao"),
        mes_expr.label("mes"),
        evento.event_type,
    ).where(evento.entity_type == "anuncio_imovel", evento.event_type.in_(tipos_evento))

    resultado: dict[tuple[str | None, str, str, date], list[str]] = defaultdict(list)
    for row in session.execute(stmt):
        chave = (row.territorio_id, row.tipologia, row.operacao, row.mes)
        resultado[chave].append(row.event_type)
    return resultado


def substituir_termometro(session: Session, linhas: list[dict]) -> int:
    """100% derivada de fato_evento_territorial/observacao_anuncio -
    DELETE + INSERT completo a cada execução, mesmo padrão de
    analytics.contagem_eventos (checkpoint 5) - seguro porque esta
    tabela nunca é fonte de verdade."""
    session.execute(TermometroAnuncio.__table__.delete())
    if not linhas:
        return 0
    stmt = insert(TermometroAnuncio).values(linhas)
    session.execute(stmt)
    return len(linhas)
