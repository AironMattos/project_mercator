from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from infrastructure.database.orm.pipeline_run import PipelineRun


def ultima_execucao_com_sucesso(
    session: Session, conector_id: str | None = None
) -> datetime | None:
    """Quando o último pipeline terminou com sucesso - usado como "última
    atualização" nos indicadores de qualidade de dado (seção "QUALIDADE
    DOS DADOS" do prompt de referência). `None` se nenhum run de sucesso
    foi registrado ainda.

    Sem `conector_id`: qualquer conector (uso original, checkpoint 11a,
    comércio). Com `conector_id`: só aquele conector - checkpoint 11e
    precisa da data por fonte (8 conectores do Radar Imobiliário), não
    de um "último de qualquer um" só.
    """
    stmt = select(func.max(PipelineRun.finalizado_em)).where(PipelineRun.status == "sucesso")
    if conector_id is not None:
        stmt = stmt.where(PipelineRun.conector_id == conector_id)
    return session.execute(stmt).scalar()
