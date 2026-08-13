from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from infrastructure.database.orm.pipeline_run import PipelineRun


def ultima_execucao_com_sucesso(session: Session) -> datetime | None:
    """Quando o último pipeline (de qualquer conector) terminou com sucesso -
    usado como "última atualização" nos indicadores de qualidade de dado
    (seção "QUALIDADE DOS DADOS" do prompt de referência da fase de
    inteligência territorial). `None` se nenhum run de sucesso foi
    registrado ainda.
    """
    stmt = select(func.max(PipelineRun.finalizado_em)).where(PipelineRun.status == "sucesso")
    return session.execute(stmt).scalar()
