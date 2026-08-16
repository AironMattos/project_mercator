from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.anuncio import ObservacaoAnuncio
from infrastructure.database.orm.observacao_anuncio import (
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)


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
