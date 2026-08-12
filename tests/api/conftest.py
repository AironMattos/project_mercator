from __future__ import annotations

import os
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
from infrastructure.database.orm.territorio import DimTerritorio

# Modelos ORM importados aqui só para registrar em Base.metadata antes do
# create_all - a API não usa entidade/observação/evento/cnae diretamente,
# mas as tabelas precisam existir por causa das foreign keys.
from infrastructure.database.orm import cnae_categoria_map  # noqa: F401
from infrastructure.database.orm import dim_cnae  # noqa: F401
from infrastructure.database.orm import entidade  # noqa: F401
from infrastructure.database.orm import fato_evento_territorial  # noqa: F401
from infrastructure.database.orm import observacao_entidade  # noqa: F401
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
        ]
    )
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
