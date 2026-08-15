"""lote_cadastral

Revision ID: 19b351ae137c
Revises: 61a2467444fb
Create Date: 2026-08-15 19:00:00.000000

"""
from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19b351ae137c'
down_revision: Union[str, Sequence[str], None] = '61a2467444fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'lote_cadastral',
        sa.Column('objectid_fonte', sa.Integer(), nullable=False),
        sa.Column('indicacao_fiscal', sa.Text(), nullable=True),
        sa.Column('inscricao_imobiliaria', sa.Text(), nullable=True),
        sa.Column('area_terreno', sa.Numeric(), nullable=True),
        sa.Column('nome_bairro', sa.Text(), nullable=True),
        sa.Column('territorio_id', sa.Text(), nullable=True),
        sa.Column('sigla_zoneamento', sa.Text(), nullable=True),
        sa.Column(
            'geometria',
            geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'),
            nullable=True,
        ),
        sa.Column('fonte_id', sa.Text(), nullable=False),
        sa.Column('snapshot_ref', sa.Text(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['territorio_id'], ['canonical.dim_territorio.territorio_id']),
        sa.PrimaryKeyConstraint('objectid_fonte'),
        schema='canonical',
    )
    op.create_index(
        op.f('ix_canonical_lote_cadastral_indicacao_fiscal'),
        'lote_cadastral',
        ['indicacao_fiscal'],
        unique=False,
        schema='canonical',
    )
    # NB: nenhum op.create_index explícito para 'geometria' - geoalchemy2
    # cria o índice GIST espacial automaticamente logo após o CREATE
    # TABLE (mesmo padrão já documentado nas migrações anteriores).


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_canonical_lote_cadastral_indicacao_fiscal'),
        table_name='lote_cadastral',
        schema='canonical',
    )
    op.drop_table('lote_cadastral', schema='canonical')
