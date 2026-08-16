from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.orm.base import Base


class ObservacaoAnuncio(Base):
    """O que sabíamos sobre um anúncio, e quando (Radar de Anúncios,
    checkpoint 12c) - tabela dedicada em vez do padrão genérico
    entidade/observacao_entidade.atributos JSONB, mesmo raciocínio que já
    levou geolocalizacao_entidade e valor_referencia_territorial a serem
    tabelas próprias (dado com estrutura real que vale indexar/consultar).

    Nunca contém nome, telefone, e-mail ou CRECI do anunciante - ver
    docs/lia-anuncios.md. `ofertante_hash` é anonimizado e irreversível,
    usado só para medir concentração de ofertante (nunca reidentificação).

    Sem FK para uma `dim_fonte` (o prompt de referência sugere isso) - o
    projeto decidiu desde o Checkpoint 11b não ter essa tabela; fonte_id
    é texto livre em toda a base, mesmo padrão de observacao_entidade/
    geolocalizacao_entidade/valor_referencia_territorial (ver nota em
    docs/fontes-anuncios.md, seção 4)."""

    __tablename__ = "observacao_anuncio"
    __table_args__ = (
        CheckConstraint(
            "operacao IN ('venda','aluguel')", name="observacao_anuncio_operacao_check"
        ),
        CheckConstraint(
            "tipo_valor = 'anuncio'", name="observacao_anuncio_tipo_valor_check"
        ),
        # Reprocessar o mesmo snapshot não duplica a observação - mesmo
        # padrão de idempotência de observacao_entidade (ON CONFLICT DO
        # NOTHING no insert). Uma observação gravada nunca é
        # atualizada/apagada.
        UniqueConstraint("entidade_id", "observado_em"),
        {"schema": "canonical"},
    )

    observacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    entidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical.entidade.entidade_id"), nullable=False
    )
    observado_em: Mapped[date] = mapped_column(Date, nullable=False)
    operacao: Mapped[str] = mapped_column(Text, nullable=False)
    tipologia: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical.dim_tipologia_imovel.tipologia_id"), nullable=False
    )
    territorio_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("canonical.dim_territorio.territorio_id"), nullable=True
    )
    preco: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    tipo_valor: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'anuncio'"))
    condominio: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    iptu: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    area_util_m2: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    quartos: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    banheiros: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    vagas: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    andar: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ofertante_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    impressao_digital: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(Text, nullable=False)


class ImovelResolvido(Base):
    """Um cluster de imóvel físico único (Checkpoint 12c, seção 8.1) -
    resultado de domain.anuncio.resolucao.resolver_imoveis. Existe pra
    métricas de volume (novos anúncios, estoque, rotação) nunca contarem
    o mesmo imóvel duas vezes só porque apareceu em mais de uma fonte."""

    __tablename__ = "imovel_resolvido"
    __table_args__ = {"schema": "canonical"}

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    impressao_digital: Mapped[str] = mapped_column(Text, nullable=False)


class ImovelResolvidoMembro(Base):
    """Entidades que compõem um ImovelResolvido - uma entidade pertence a
    no máximo um cluster (entidade_id é a chave primária: uma vez
    resolvida, não migra de cluster). `fonte_id` é denormalizado aqui
    (não deriva de entidade, que não carrega fonte - só a observação
    carrega) porque é exatamente o dado que alimenta o rótulo "anunciado
    em: Apolar e Chaves na Mão" (seção 1.2 do prompt de referência) sem
    precisar voltar em observacao_anuncio a cada leitura."""

    __tablename__ = "imovel_resolvido_membro"
    __table_args__ = {"schema": "canonical"}

    entidade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical.entidade.entidade_id"), primary_key=True
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical.imovel_resolvido.cluster_id"),
        nullable=False,
    )
    fonte_id: Mapped[str] = mapped_column(Text, nullable=False)
