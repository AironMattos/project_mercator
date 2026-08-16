"""Consultas reais que alimentam analytics/features/pressao_especulativa.py
(checkpoint 12h, seção 5 do prompt de referência)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.anuncio.resolucao import JANELA_PADRAO_DIAS
from infrastructure.database.orm.fato_evento_territorial import (
    FatoEventoTerritorial as FatoEventoTerritorialORM,
)
from infrastructure.database.orm.observacao_anuncio import (
    ImovelResolvidoMembro,
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)

TIPOS_EVENTO_OBRA_CONTRAPARTIDA = ("ALVARA_APROVADO", "OBRA_CONCLUIDA", "ZONEAMENTO_ALTERADO")


def contar_reanuncios_e_encerrados(
    session: Session, *, janela_dias: int = JANELA_PADRAO_DIAS
) -> tuple[int, int, list[float]]:
    """(n_reanuncios, n_encerrados, variacoes_pct_dos_reanuncios) nos
    últimos `janela_dias` - mesma janela usada pra detectar REANUNCIO em
    si (domain.anuncio.resolucao.JANELA_PADRAO_DIAS), não um número
    novo. `variacoes_pct` vem do payload do evento (só quem tem preço
    anterior conhecido - ver domain.anuncio.regras.detectar_reanuncio)."""
    evento = FatoEventoTerritorialORM
    corte = date.today() - timedelta(days=janela_dias)

    n_encerrados = session.execute(
        select(func.count()).where(
            evento.entity_type == "anuncio_imovel",
            evento.event_type == "ANUNCIO_ENCERRADO",
            evento.data_evento >= corte,
        )
    ).scalar() or 0

    stmt_reanuncios = select(evento.payload["variacao_pct"]).where(
        evento.entity_type == "anuncio_imovel",
        evento.event_type == "REANUNCIO",
        evento.data_evento >= corte,
    )
    linhas = list(session.execute(stmt_reanuncios))
    n_reanuncios = len(linhas)
    variacoes = [float(v) for (v,) in linhas if v is not None]

    return n_reanuncios, n_encerrados, variacoes


def consultar_estoque_total_por_bairro(session: Session) -> dict[str, int]:
    """Estoque de anúncios ativos por bairro, somado sobre
    tipologia/operação - mesma base de cluster resolvido ainda ativo de
    `termometro_repository.consultar_estoque_e_precos_ativos`, mas sem
    quebrar por tipologia/operação (o indicador 3 da seção 5 é por
    bairro só)."""
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
            func.row_number()
            .over(partition_by=membro.cluster_id, order_by=obs.observado_em.desc())
            .label("posicao"),
        )
        .select_from(membro)
        .join(obs, obs.entidade_id == membro.entidade_id)
        .where(membro.entidade_id.not_in(encerrados))
        .subquery()
    )
    stmt = (
        select(linha_por_cluster.c.territorio_id, func.count())
        .where(linha_por_cluster.c.posicao == 1, linha_por_cluster.c.territorio_id.isnot(None))
        .group_by(linha_por_cluster.c.territorio_id)
    )
    return {territorio_id: n for territorio_id, n in session.execute(stmt)}


def consultar_contagem_por_ofertante(session: Session) -> list[int]:
    """Contagem de anúncios ativos por `ofertante_hash` distinto (nunca o
    hash em si na saída) - achado real, registrado explicitamente: os
    conectores `apolar_anuncios`/`chavesnamao_anuncios` nunca populam
    `ofertante_hash` (checkpoint 12d/12h - o campo existe no schema
    desde o domínio, mas o parsing de HTML nunca extraiu/hasheou o nome
    do anunciante). Esta consulta sempre devolve lista vazia até isso
    ser corrigido em conectores, não é um bug desta consulta."""
    obs = ObservacaoAnuncioORM
    evento = FatoEventoTerritorialORM
    encerrados = select(evento.entidade_id).where(
        evento.entity_type == "anuncio_imovel", evento.event_type == "ANUNCIO_ENCERRADO"
    )
    stmt = (
        select(obs.ofertante_hash, func.count())
        .where(obs.ofertante_hash.isnot(None), obs.entidade_id.not_in(encerrados))
        .group_by(obs.ofertante_hash)
    )
    return [n for _hash, n in session.execute(stmt)]


def consultar_preco_pedido_m2_mediano_cidade(session: Session, operacao: str) -> list[float]:
    """Todos os preços/m² de anúncios ativos da cidade inteira para uma
    operação ('aluguel' ou 'venda') - lista bruta (não a mediana em si),
    quem chama decide o piso mínimo via
    analytics.features.anuncio_termometro.calcular_estatistica_preco."""
    membro = ImovelResolvidoMembro
    obs = ObservacaoAnuncioORM
    evento = FatoEventoTerritorialORM
    encerrados = select(evento.entidade_id).where(
        evento.entity_type == "anuncio_imovel", evento.event_type == "ANUNCIO_ENCERRADO"
    )
    linha_por_cluster = (
        select(
            membro.cluster_id,
            obs.operacao,
            obs.preco,
            obs.area_util_m2,
            func.row_number()
            .over(partition_by=membro.cluster_id, order_by=obs.observado_em.desc())
            .label("posicao"),
        )
        .select_from(membro)
        .join(obs, obs.entidade_id == membro.entidade_id)
        .where(membro.entidade_id.not_in(encerrados))
        .subquery()
    )
    stmt = select(linha_por_cluster.c.preco, linha_por_cluster.c.area_util_m2).where(
        linha_por_cluster.c.posicao == 1,
        linha_por_cluster.c.operacao == operacao,
        linha_por_cluster.c.preco.isnot(None),
        linha_por_cluster.c.area_util_m2.isnot(None),
        linha_por_cluster.c.area_util_m2 > 0,
    )
    return [float(preco) / float(area) for preco, area in session.execute(stmt)]


def houve_contrapartida_fisica_no_bairro(
    session: Session, territorio_id: str, *, meses: int
) -> bool:
    """True se houve `ALVARA_APROVADO`/`OBRA_CONCLUIDA`/`ZONEAMENTO_ALTERADO`
    (Radar Imobiliário, checkpoint 11b) no bairro nos últimos `meses` -
    "aqui o Checkpoint 11 finalmente vira insumo analítico" (seção 5)."""
    evento = FatoEventoTerritorialORM
    corte = date.today() - timedelta(days=30 * meses)
    stmt = select(func.count()).where(
        evento.territorio_id == territorio_id,
        evento.event_type.in_(TIPOS_EVENTO_OBRA_CONTRAPARTIDA),
        evento.data_evento >= corte,
    )
    return (session.execute(stmt).scalar() or 0) > 0
