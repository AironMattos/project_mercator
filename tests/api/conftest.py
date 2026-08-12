from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from infrastructure.database.orm.base import Base
from infrastructure.database.orm.contagem_eventos import ContagemEventos
from infrastructure.database.orm.dim_categoria import DimCategoria
from infrastructure.database.orm.entidade import Entidade
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade
from infrastructure.database.orm.territorio import DimTerritorio

# Modelos ORM importados aqui só para registrar em Base.metadata antes do
# create_all - a API não usa evento/cnae diretamente, mas as tabelas
# precisam existir por causa das foreign keys.
from infrastructure.database.orm import cnae_categoria_map  # noqa: F401
from infrastructure.database.orm import dim_cnae  # noqa: F401
from infrastructure.database.orm import fato_evento_territorial  # noqa: F401
from infrastructure.database.orm import pipeline_run  # noqa: F401

ADMIN_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://mercator:mercator@localhost:5432/mercator",
)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://mercator:mercator@localhost:5432/mercator_test",
)


def _nome_banco(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def _recriar_banco_teste() -> None:
    admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    dbname = _nome_banco(TEST_DATABASE_URL)
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :dbname AND pid <> pg_backend_pid()"
            ),
            {"dbname": dbname},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def test_engine():
    _recriar_banco_teste()
    engine = create_engine(TEST_DATABASE_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        for schema in ("canonical", "events", "infra", "analytics"):
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _multi(*coords: tuple[float, float]) -> MultiPolygon:
    return MultiPolygon([Polygon(coords)])


@pytest.fixture(scope="session")
def seeded_session(test_engine):
    """Popula um cenário mínimo e conhecido: dois bairros, duas categorias,
    e contagens espalhadas em dois meses - o suficiente para exercitar
    agregação por bairro (mapa) e série temporal (painel de detalhe).
    """
    session_factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = session_factory()

    centro_geom = _multi(
        (-49.28, -25.44), (-49.27, -25.44), (-49.27, -25.43), (-49.28, -25.43), (-49.28, -25.44)
    )
    batel_geom = _multi(
        (-49.29, -25.45), (-49.28, -25.45), (-49.28, -25.44), (-49.29, -25.44), (-49.29, -25.45)
    )

    session.add_all(
        [
            DimTerritorio(
                territorio_id="curitiba-bairro-centro",
                nivel="bairro",
                nome="Centro",
                nome_alternativo=[],
                geometria=from_shape(centro_geom, srid=4326),
                cidade_id="curitiba",
            ),
            DimTerritorio(
                territorio_id="curitiba-bairro-batel",
                nivel="bairro",
                nome="Batel",
                nome_alternativo=[],
                geometria=from_shape(batel_geom, srid=4326),
                cidade_id="curitiba",
            ),
        ]
    )
    session.add_all(
        [
            DimCategoria(categoria_id="bares_restaurantes", nome="Bares, restaurantes e lanchonetes"),
            DimCategoria(categoria_id="saude_clinicas", nome="Saúde e clínicas"),
        ]
    )
    session.flush()

    session.add_all(
        [
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="bares_restaurantes",
                mes=date(2026, 7, 1),
                event_type="PRIMEIRA_OBSERVACAO",
                contagem=5,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="bares_restaurantes",
                mes=date(2026, 7, 1),
                event_type="DESAPARECIMENTO",
                contagem=2,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="PRIMEIRA_OBSERVACAO",
                contagem=3,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="DESAPARECIMENTO",
                contagem=4,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="saude_clinicas",
                mes=date(2026, 8, 1),
                event_type="PRIMEIRA_OBSERVACAO",
                contagem=1,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-batel",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="PRIMEIRA_OBSERVACAO",
                contagem=2,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-batel",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="DESAPARECIMENTO",
                contagem=1,
            ),
            # ABERTURA_CONFIRMADA (confiança alta) - até a correção de
            # 2026-08-12, esse tipo nunca chegava aqui (ver TIPOS_CONSIDERADOS
            # em analytics/features/contagem_eventos.py), então "aberturas"
            # media só PRIMEIRA_OBSERVACAO (confiança baixa).
            ContagemEventos(
                territorio_id="curitiba-bairro-centro",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="ABERTURA_CONFIRMADA",
                contagem=6,
            ),
            ContagemEventos(
                territorio_id="curitiba-bairro-batel",
                categoria_id="bares_restaurantes",
                mes=date(2026, 8, 1),
                event_type="ABERTURA_CONFIRMADA",
                contagem=3,
            ),
        ]
    )

    # entidade/observacao_entidade com INICIO_ATIVIDADE real - exercita o
    # indicador de aberturas (analytics.features.servico_indicadores), que
    # lê essa data em vez de fato_evento_territorial (ver checkpoint 8a/8b:
    # INICIO_ATIVIDADE tem profundidade real mesmo com poucos snapshots).
    # CENTRO tem 3 meses de histórico dentro da janela de 24 meses antes de
    # 2026-07 (o "período padrão" derivado do mes_fim de ContagemEventos
    # acima, 2026-08, menos 1 mês) + 1 mês "atual" -> baseline confiável.
    # BATEL só tem o mês "atual", sem histórico -> historico_insuficiente,
    # de propósito (testa o caminho de bairro inelegível pro ranking).
    def _entidade_com_inicio_atividade(
        identificador: str, territorio_id: str, inicio_atividade: str
    ) -> tuple[Entidade, ObservacaoEntidade]:
        entidade_id = uuid.uuid4()
        ent = Entidade(
            entidade_id=entidade_id, tipo_entidade="comercio", identificador_fonte=identificador
        )
        obs = ObservacaoEntidade(
            entidade_id=entidade_id,
            observado_em=date(2026, 8, 1),
            fonte_id="alvaras_smf",
            snapshot_ref="teste",
            atributos={
                "territorio_id": territorio_id,
                "inicio_atividade": inicio_atividade,
                "cnae_principal": "G.47.1.1-1/00-00",
            },
        )
        return ent, obs

    entidades_observacoes = [
        _entidade_com_inicio_atividade("CENTRO-001", "curitiba-bairro-centro", "2024-08-15"),
        _entidade_com_inicio_atividade("CENTRO-002", "curitiba-bairro-centro", "2025-03-10"),
        _entidade_com_inicio_atividade("CENTRO-003", "curitiba-bairro-centro", "2025-11-20"),
        _entidade_com_inicio_atividade("CENTRO-004", "curitiba-bairro-centro", "2026-07-05"),
        _entidade_com_inicio_atividade("BATEL-001", "curitiba-bairro-batel", "2026-07-12"),
    ]
    for ent, obs in entidades_observacoes:
        session.add(ent)
        session.add(obs)

    session.commit()

    yield session
    session.close()


@pytest.fixture()
def client(seeded_session):
    from dependencies import get_db
    from main import app

    def _override_get_db():
        yield seeded_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
