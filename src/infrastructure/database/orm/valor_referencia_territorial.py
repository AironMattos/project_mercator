from __future__ import annotations

import uuid
from datetime import date

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ValorReferenciaTerritorial(Base):
    """Um valor de referência territorial - nunca um "preço" genérico.
    tipo_valor distingue as quatro grandezas monetárias que o mercado
    imobiliário produz (venal/avaliação/anúncio/transação); componente
    distingue terreno de construção. Nenhuma leitura deste registro pode
    descartar essas duas dimensões (ver domain/valuation).

    Geometria genérica (não fixada em Point nem em Polygon): a fonte
    inicial confirmada (PGV/IPPUC, checkpoint 11a) é por microrregião
    (polígono), mas o desenho contempla também face de quadra/ponto de
    outras fontes futuras.

    vigencia_inicio/vigencia_fim em vez de sobrescrita: quando um valor
    de referência for revisado, a versão anterior continua consultável -
    mesma disciplina de imutabilidade de observacao_entidade/evento.
    """

    __tablename__ = "valor_referencia_territorial"
    __table_args__ = (
        CheckConstraint(
            "tipo_valor IN ('venal','avaliacao','anuncio','transacao')",
            name="valor_referencia_territorial_tipo_valor_check",
        ),
        CheckConstraint(
            "componente IN ('terreno','construcao','total')",
            name="valor_referencia_territorial_componente_check",
        ),
        # Reprocessar o mesmo snapshot de uma fonte não deve duplicar o
        # mesmo valor de referência - mesmo padrão de idempotência de
        # observacao_entidade/zoneamento_territorial (ON CONFLICT DO
        # NOTHING no insert). A chave usa objectid_fonte (identidade do
        # registro na fonte), não territorio_id: uma fonte comum tem
        # várias geometrias dentro do mesmo bairro (ex.: várias
        # microrregiões da PGV por bairro), cada uma com seu próprio
        # valor - usar território como parte da chave colapsaria todas
        # elas numa só. Bug real, encontrado rodando o conector ippuc_pgv
        # contra dado real (checkpoint 11c): 1.011 valores normalizados
        # viraram 74 linhas gravadas até ser corrigido.
        UniqueConstraint("objectid_fonte", "fonte_id", "vigencia_inicio"),
        {"schema": "canonical"},
    )

    valor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    geometria: Mapped[str] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False
    )
    objectid_fonte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    tipo_valor: Mapped[str] = mapped_column(Text, nullable=False)
    componente: Mapped[str] = mapped_column(Text, nullable=False)
    valor_m2: Mapped[float] = mapped_column(Numeric, nullable=False)
    moeda_data: Mapped[date] = mapped_column(Date, nullable=False)
    # Texto simples, sem FK - mesmo padrão de fonte_id em
    # observacao_entidade/geolocalizacao_entidade. O prompt de referência
    # deste checkpoint sugere `REFERENCES canonical.dim_fonte(fonte_id)`,
    # mas essa tabela nunca existiu no projeto: todo fonte_id/conector_id
    # já gravado (checkpoints 1-9) é texto livre, validado só pelo
    # conector que o grava. Criar dim_fonte agora, sem nenhum outro lugar
    # do sistema referenciá-la, seria uma abstração nova sem uso real -
    # documentado aqui como desvio deliberado, não descuido.
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    metodologia: Mapped[str | None] = mapped_column(Text, nullable=True)
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
