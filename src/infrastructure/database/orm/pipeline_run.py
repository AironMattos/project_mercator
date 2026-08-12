from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"
    __table_args__ = (
        CheckConstraint(
            "status IN ('sucesso','falha','parcial')", name="pipeline_run_status_check"
        ),
        {"schema": "infra"},
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    conector_id: Mapped[str] = mapped_column(Text, nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    registros_lidos: Mapped[int] = mapped_column(Integer, server_default="0")
    registros_gravados: Mapped[int] = mapped_column(Integer, server_default="0")
    registros_com_falha: Mapped[int] = mapped_column(Integer, server_default="0")
