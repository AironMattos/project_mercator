from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.anuncio import ObservacaoAnuncio
from infrastructure.database.orm.fato_evento_territorial import (
    FatoEventoTerritorial as FatoEventoTerritorialORM,
)
from infrastructure.database.orm.observacao_anuncio import (
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)

# Prefixo usado pelos conectores quando não há área útil suficiente pra
# calcular uma impressão digital de verdade (ver connector.py de
# apolar_anuncios) - esses anúncios nunca participam de resolução entre
# fontes nem de detecção de REANUNCIO, mesmo tratamento nos dois lugares.
PLACEHOLDER_SEM_FINGERPRINT = "sem-fp:"


def _linha(o: ObservacaoAnuncio) -> dict:
    return {
        "observacao_id": o.observacao_id,
        "entidade_id": o.entidade_id,
        "observado_em": o.observado_em,
        "operacao": o.operacao,
        "tipologia": o.tipologia,
        "territorio_id": o.territorio_id,
        "preco": o.preco,
        "tipo_valor": o.tipo_valor,
        "condominio": o.condominio,
        "iptu": o.iptu,
        "area_util_m2": o.area_util_m2,
        "quartos": o.quartos,
        "banheiros": o.banheiros,
        "vagas": o.vagas,
        "andar": o.andar,
        "ofertante_hash": o.ofertante_hash,
        "impressao_digital": o.impressao_digital,
        "fonte_id": o.fonte_id,
        "snapshot_ref": o.snapshot_ref,
    }


def _from_row(o) -> ObservacaoAnuncio:
    return ObservacaoAnuncio(
        observacao_id=o.observacao_id,
        entidade_id=o.entidade_id,
        observado_em=o.observado_em,
        operacao=o.operacao,
        tipologia=o.tipologia,
        territorio_id=o.territorio_id,
        preco=float(o.preco) if o.preco is not None else None,
        tipo_valor=o.tipo_valor,
        condominio=float(o.condominio) if o.condominio is not None else None,
        iptu=float(o.iptu) if o.iptu is not None else None,
        area_util_m2=float(o.area_util_m2) if o.area_util_m2 is not None else None,
        quartos=o.quartos,
        banheiros=o.banheiros,
        vagas=o.vagas,
        andar=o.andar,
        ofertante_hash=o.ofertante_hash,
        impressao_digital=o.impressao_digital,
        fonte_id=o.fonte_id,
        snapshot_ref=o.snapshot_ref,
    )


def insert_observacoes_anuncio(session: Session, observacoes: list[ObservacaoAnuncio]) -> int:
    """Grava observações de anúncio. Nunca atualiza uma observação
    existente - mesma idempotência de observacao_entidade (ON CONFLICT DO
    NOTHING em entidade_id+observado_em)."""
    if not observacoes:
        return 0

    stmt = insert(ObservacaoAnuncioORM).values([_linha(o) for o in observacoes])
    stmt = stmt.on_conflict_do_nothing(index_elements=["entidade_id", "observado_em"])
    resultado = session.execute(stmt)
    return resultado.rowcount or 0


def iter_grupos_por_entidade_anuncio(
    session: Session,
    fonte_id: str,
    data_anterior: date,
    data_atual: date,
) -> Iterator[tuple[uuid.UUID, list[ObservacaoAnuncio]]]:
    """Para cada anúncio com observação em pelo menos uma das duas datas,
    gera (entidade_id, [observações ordenadas por observado_em]) - mesmo
    padrão de observacao_repository.iter_grupos_por_entidade (cursor
    server-side, nunca carrega o snapshot inteiro em memória)."""
    tabela = ObservacaoAnuncioORM
    stmt = (
        select(tabela)
        .where(
            tabela.fonte_id == fonte_id,
            tabela.observado_em.in_([data_anterior, data_atual]),
        )
        .order_by(tabela.entidade_id, tabela.observado_em)
        .execution_options(yield_per=2000)
    )

    grupo_id: uuid.UUID | None = None
    grupo: list[ObservacaoAnuncio] = []
    for row in session.execute(stmt):
        o = row[0]
        if grupo_id is not None and o.entidade_id != grupo_id:
            yield grupo_id, grupo
            grupo = []
        grupo_id = o.entidade_id
        grupo.append(_from_row(o))
    if grupo:
        yield grupo_id, grupo


def listar_identificadores_fonte_com_observacao(
    session: Session, fonte_id: str, observado_em: date
) -> set[str]:
    """Identificadores de fonte (hash) de entidades que já têm observação
    gravada para este snapshot - usado pra retomar uma coleta parcial
    (checkpoint 12d) sem re-baixar página nenhuma: o pipeline de ingestão
    calcula o mesmo hash pra cada URL do sitemap e pula as que já
    aparecem aqui."""
    from infrastructure.database.orm.entidade import Entidade as EntidadeORM

    tabela = ObservacaoAnuncioORM
    stmt = (
        select(EntidadeORM.identificador_fonte)
        .join(tabela, tabela.entidade_id == EntidadeORM.entidade_id)
        .where(tabela.fonte_id == fonte_id, tabela.observado_em == observado_em)
    )
    return {row[0] for row in session.execute(stmt)}


def iter_observacoes_anuncio_por_fonte(
    session: Session, fonte_id: str, observado_em: date | None = None
) -> Iterator[ObservacaoAnuncio]:
    """Todas as observações de anúncio de uma fonte, opcionalmente
    filtradas por snapshot. Cursor server-side."""
    tabela = ObservacaoAnuncioORM
    stmt = select(tabela).where(tabela.fonte_id == fonte_id)
    if observado_em is not None:
        stmt = stmt.where(tabela.observado_em == observado_em)
    stmt = stmt.execution_options(yield_per=2000)

    for row in session.execute(stmt):
        yield _from_row(row[0])


def buscar_encerrados_recentes_por_impressao(
    session: Session,
    impressoes_digitais: set[str],
    janela_dias: int,
    antes_de: date,
) -> dict[str, tuple[uuid.UUID, float | None]]:
    """Para cada impressão digital candidata (de um anúncio recém-visto,
    sem observação anterior), o `ANUNCIO_ENCERRADO` mais recente dentro
    da janela cuja observação de origem tenha essa mesma impressão -
    usado pra decidir `REANUNCIO` vs `ANUNCIO_PUBLICADO` (seção 5 do
    prompt de referência do Radar de Anúncios: "o mesmo imóvel volta à
    oferta em janela curta"). Nunca considera impressões
    `PLACEHOLDER_SEM_FINGERPRINT` (mesma exclusão de
    `domain.anuncio.resolucao`).

    Join via `origem_observacoes[1]` (1-indexado no Postgres) - mesmo
    padrão já usado por `construcao_repository` pra ler a observação de
    origem de um evento sem duplicar o dado no próprio evento."""
    if not impressoes_digitais:
        return {}
    candidatas = {
        i for i in impressoes_digitais if not i.startswith(PLACEHOLDER_SEM_FINGERPRINT)
    }
    if not candidatas:
        return {}

    evento = FatoEventoTerritorialORM
    obs = ObservacaoAnuncioORM
    limite_inferior = antes_de - timedelta(days=janela_dias)

    stmt = (
        select(obs.impressao_digital, evento.entidade_id, obs.preco)
        .select_from(evento)
        .join(obs, obs.observacao_id == evento.origem_observacoes[1])
        .where(
            evento.entity_type == "anuncio_imovel",
            evento.event_type == "ANUNCIO_ENCERRADO",
            evento.data_evento >= limite_inferior,
            evento.data_evento < antes_de,
            obs.impressao_digital.in_(candidatas),
        )
        .order_by(obs.impressao_digital, evento.data_evento.desc())
    )

    resultado: dict[str, tuple[uuid.UUID, float | None]] = {}
    for impressao, entidade_id_anterior, preco in session.execute(stmt):
        # primeira linha por impressão = a mais recente (ORDER BY ... desc)
        if impressao not in resultado:
            resultado[impressao] = (
                entidade_id_anterior,
                float(preco) if preco is not None else None,
            )
    return resultado
