from __future__ import annotations

from collections.abc import Iterable

from geoalchemy2.shape import from_shape
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from infrastructure.connectors.geocuritiba_cadastro.lote_connector import RegistroLote
from infrastructure.database.orm.lote_cadastral import LoteCadastral

TAMANHO_LOTE_INSERT = 5000


def upsert_lotes(session: Session, registros: Iterable[RegistroLote]) -> int:
    """Grava lotes em lotes de TAMANHO_LOTE_INSERT (upsert por
    objectid_fonte, mesmo padrão de dim_territorio) - registros vem de um
    gerador (normalize() streama do disco), nunca materializado por
    inteiro em memória antes de gravar."""
    total = 0
    buffer: list[dict] = []

    for r in registros:
        buffer.append(
            {
                "objectid_fonte": r.objectid_fonte,
                "indicacao_fiscal": r.indicacao_fiscal,
                "inscricao_imobiliaria": r.inscricao_imobiliaria,
                "area_terreno": r.area_terreno,
                "nome_bairro": r.nome_bairro,
                "territorio_id": r.territorio_id,
                "sigla_zoneamento": r.sigla_zoneamento,
                "geometria": from_shape(r.geometria, srid=4326) if r.geometria else None,
                "fonte_id": r.fonte_id,
                "snapshot_ref": r.snapshot_ref,
            }
        )
        if len(buffer) >= TAMANHO_LOTE_INSERT:
            total += _gravar_lote(session, buffer)
            buffer = []

    if buffer:
        total += _gravar_lote(session, buffer)

    return total


def _gravar_lote(session: Session, rows: list[dict]) -> int:
    stmt = insert(LoteCadastral).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[LoteCadastral.objectid_fonte],
        set_={
            "indicacao_fiscal": stmt.excluded.indicacao_fiscal,
            "inscricao_imobiliaria": stmt.excluded.inscricao_imobiliaria,
            "area_terreno": stmt.excluded.area_terreno,
            "nome_bairro": stmt.excluded.nome_bairro,
            "territorio_id": stmt.excluded.territorio_id,
            "sigla_zoneamento": stmt.excluded.sigla_zoneamento,
            "geometria": stmt.excluded.geometria,
            "fonte_id": stmt.excluded.fonte_id,
            "snapshot_ref": stmt.excluded.snapshot_ref,
        },
    )
    session.execute(stmt)
    session.commit()
    return len(rows)


def territorio_id_por_indicacao_fiscal(
    session: Session, indicacoes_fiscais: list[str]
) -> dict[str, str]:
    """Lookup em lote: indicacao_fiscal -> territorio_id, para o
    conector smu_alvaras_construcao resolver bairro sem geocodificação."""
    if not indicacoes_fiscais:
        return {}
    rows = (
        session.query(LoteCadastral.indicacao_fiscal, LoteCadastral.territorio_id)
        .filter(LoteCadastral.indicacao_fiscal.in_(indicacoes_fiscais))
        .filter(LoteCadastral.territorio_id.isnot(None))
        .all()
    )
    return {r.indicacao_fiscal: r.territorio_id for r in rows}
