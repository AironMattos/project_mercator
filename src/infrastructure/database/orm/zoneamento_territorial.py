from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ZoneamentoTerritorial(Base):
    """Zoneamento por polígono, alimentado da camada "Zoneamento Lei
    15.511/2019" do GeoCuritiba (checkpoint 11a). Guarda só o que a fonte
    de fato expõe - classificação de zona (código/nome/sigla/legislação)
    e as duas datas de versionamento que a própria camada já carrega.

    Não tem campos de índice construtivo/gabarito/taxa de ocupação:
    nenhuma camada pública do GeoCuritiba expõe esses parâmetros
    numéricos (confirmado no checkpoint 11a) - inventar essas colunas
    aqui seria abrir espaço para um proxy sem fonte, o que o prompt de
    referência proíbe explicitamente.

    data_versao/data_atualizacao ficam como texto, não Date: a camada de
    origem declara os dois campos como esriFieldTypeString, não Date -
    o formato real só será confirmado lendo dado de verdade no
    checkpoint 11c (conector geocuritiba_cadastro). Guardar como texto
    agora evita presumir um formato que pode não bater.

    Linha por (objectid_fonte, fonte_id, data_versao): append-only, mesmo
    padrão de idempotência de observacao_entidade - reprocessar a mesma
    versão não duplica, mas uma nova versão sempre gera uma linha nova
    (histórico preservado), o que é o que torna possível detectar
    ZONEAMENTO_ALTERADO comparando duas linhas do mesmo objectid_fonte.
    """

    __tablename__ = "zoneamento_territorial"
    __table_args__ = (
        UniqueConstraint("objectid_fonte", "fonte_id", "data_versao"),
        {"schema": "canonical"},
    )

    zoneamento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    geometria: Mapped[str] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    objectid_fonte: Mapped[int] = mapped_column(Integer, nullable=False)
    cd_zona: Mapped[str] = mapped_column(Text, nullable=False)
    sg_zona: Mapped[str] = mapped_column(Text, nullable=False)
    nm_zona: Mapped[str] = mapped_column(Text, nullable=False)
    nm_grupo: Mapped[str | None] = mapped_column(Text, nullable=True)
    legislacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_versao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_atualizacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)
