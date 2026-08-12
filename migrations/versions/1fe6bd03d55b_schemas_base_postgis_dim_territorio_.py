"""schemas base, postgis, dim_territorio, pipeline_run

Revision ID: 1fe6bd03d55b
Revises:
Create Date: 2026-08-11 22:34:20.429858

"""
from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1fe6bd03d55b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SCHEMA IF NOT EXISTS canonical")
    op.execute("CREATE SCHEMA IF NOT EXISTS events")
    op.execute("CREATE SCHEMA IF NOT EXISTS infra")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "dim_territorio",
        sa.Column("territorio_id", sa.Text(), nullable=False),
        sa.Column("nivel", sa.Text(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column(
            "nome_alternativo",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "geometria",
            geoalchemy2.Geometry(geometry_type="MULTIPOLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("territorio_pai_id", sa.Text(), nullable=True),
        sa.Column(
            "cidade_id", sa.String(), nullable=False, server_default="curitiba"
        ),
        sa.PrimaryKeyConstraint("territorio_id"),
        sa.ForeignKeyConstraint(
            ["territorio_pai_id"], ["canonical.dim_territorio.territorio_id"]
        ),
        schema="canonical",
    )

    op.create_table(
        "pipeline_run",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("conector_id", sa.Text(), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("registros_lidos", sa.Integer(), server_default="0"),
        sa.Column("registros_gravados", sa.Integer(), server_default="0"),
        sa.Column("registros_com_falha", sa.Integer(), server_default="0"),
        sa.CheckConstraint(
            "status IN ('sucesso','falha','parcial')", name="pipeline_run_status_check"
        ),
        sa.PrimaryKeyConstraint("run_id"),
        schema="infra",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("pipeline_run", schema="infra")
    op.drop_table("dim_territorio", schema="canonical")
    op.execute("DROP SCHEMA IF EXISTS infra")
    op.execute("DROP SCHEMA IF EXISTS events")
    op.execute("DROP SCHEMA IF EXISTS canonical")
