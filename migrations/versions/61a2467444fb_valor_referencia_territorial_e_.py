"""valor_referencia_territorial e zoneamento_territorial

Revision ID: 61a2467444fb
Revises: dfaa8754a195
Create Date: 2026-08-15 18:00:00.000000

"""
from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61a2467444fb'
down_revision: Union[str, Sequence[str], None] = 'dfaa8754a195'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'valor_referencia_territorial',
        sa.Column('valor_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column(
            'geometria',
            geoalchemy2.types.Geometry(geometry_type='GEOMETRY', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'),
            nullable=False,
        ),
        sa.Column('objectid_fonte', sa.Integer(), nullable=True),
        sa.Column('territorio_id', sa.Text(), nullable=True),
        sa.Column('tipo_valor', sa.Text(), nullable=False),
        sa.Column('componente', sa.Text(), nullable=False),
        sa.Column('valor_m2', sa.Numeric(), nullable=False),
        sa.Column('moeda_data', sa.Date(), nullable=False),
        sa.Column('fonte_id', sa.Text(), nullable=False),
        sa.Column('metodologia', sa.Text(), nullable=True),
        sa.Column('vigencia_inicio', sa.Date(), nullable=False),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('snapshot_ref', sa.Text(), nullable=False),
        sa.CheckConstraint(
            "tipo_valor IN ('venal','avaliacao','anuncio','transacao')",
            name='valor_referencia_territorial_tipo_valor_check',
        ),
        sa.CheckConstraint(
            "componente IN ('terreno','construcao','total')",
            name='valor_referencia_territorial_componente_check',
        ),
        sa.ForeignKeyConstraint(['territorio_id'], ['canonical.dim_territorio.territorio_id']),
        sa.PrimaryKeyConstraint('valor_id'),
        sa.UniqueConstraint('objectid_fonte', 'fonte_id', 'vigencia_inicio'),
        schema='canonical',
    )
    # NB: nenhum op.create_index explícito para 'geometria' - geoalchemy2
    # cria o índice GIST espacial automaticamente logo após o CREATE
    # TABLE (mesmo padrão de dim_territorio.geometria e
    # geolocalizacao_entidade.ponto); um op.create_index aqui colide com
    # esse índice autogerado (DuplicateTable).

    op.create_table(
        'zoneamento_territorial',
        sa.Column('zoneamento_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column(
            'geometria',
            geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'),
            nullable=False,
        ),
        sa.Column('territorio_id', sa.Text(), nullable=True),
        sa.Column('objectid_fonte', sa.Integer(), nullable=False),
        sa.Column('cd_zona', sa.Text(), nullable=False),
        sa.Column('sg_zona', sa.Text(), nullable=False),
        sa.Column('nm_zona', sa.Text(), nullable=False),
        sa.Column('nm_grupo', sa.Text(), nullable=True),
        sa.Column('legislacao', sa.Text(), nullable=True),
        sa.Column('data_versao', sa.Text(), nullable=True),
        sa.Column('data_atualizacao', sa.Text(), nullable=True),
        sa.Column('fonte_id', sa.Text(), nullable=False),
        sa.Column('snapshot_ref', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['territorio_id'], ['canonical.dim_territorio.territorio_id']),
        sa.PrimaryKeyConstraint('zoneamento_id'),
        sa.UniqueConstraint('objectid_fonte', 'fonte_id', 'data_versao'),
        schema='canonical',
    )
    # NB: mesma observação de índice espacial automático acima, para
    # zoneamento_territorial.geometria.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('zoneamento_territorial', schema='canonical')
    op.drop_table('valor_referencia_territorial', schema='canonical')
