from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Point, Polygon
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from infrastructure.database.orm.base import Base
from infrastructure.database.orm.cnae_categoria_map import CnaeCategoriaMap
from infrastructure.database.orm.contagem_eventos import ContagemEventos
from infrastructure.database.orm.contagem_inicio_atividade import ContagemInicioAtividade
from infrastructure.database.orm.dim_categoria import DimCategoria
from infrastructure.database.orm.dim_cnae import DimCnae
from infrastructure.database.orm.entidade import Entidade
from infrastructure.database.orm.geolocalizacao_entidade import GeolocalizacaoEntidade
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade
from infrastructure.database.orm.territorio import DimTerritorio

# Modelos ORM importados aqui só para registrar em Base.metadata antes do
# create_all - a API não usa evento diretamente, mas a tabela precisa
# existir por causa das foreign keys.
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

    # analytics.contagem_inicio_atividade - a tabela materializada que
    # indicador_repository lê (checkpoint de otimização de 2026-08-12: a
    # query ao vivo contra observacao_entidade, usada até então, virou
    # cara demais pra rodar por request; ver
    # run_contagem_inicio_atividade.py). Semeada direto aqui, no mesmo
    # espírito de ContagemEventos acima (é uma feature derivada, não
    # rodamos o pipeline de verdade num teste). CENTRO tem 3 meses de
    # histórico dentro da janela de 24 meses antes de 2026-07 (o "período
    # padrão" derivado do mes_fim de ContagemEventos acima, 2026-08, menos
    # 1 mês) + 1 mês "atual" -> baseline confiável. BATEL só tem o mês
    # "atual", sem histórico -> baseline zero, de propósito (testa o
    # caminho de bairro inelegível pro ranking).
    session.add_all(
        [
            ContagemInicioAtividade(
                territorio_id="curitiba-bairro-centro", categoria_id=None, mes=date(2024, 8, 1), contagem=1
            ),
            ContagemInicioAtividade(
                territorio_id="curitiba-bairro-centro", categoria_id=None, mes=date(2025, 3, 1), contagem=1
            ),
            ContagemInicioAtividade(
                territorio_id="curitiba-bairro-centro", categoria_id=None, mes=date(2025, 11, 1), contagem=1
            ),
            ContagemInicioAtividade(
                territorio_id="curitiba-bairro-centro", categoria_id=None, mes=date(2026, 7, 1), contagem=1
            ),
            ContagemInicioAtividade(
                territorio_id="curitiba-bairro-batel", categoria_id=None, mes=date(2026, 7, 1), contagem=1
            ),
        ]
    )

    # Checkpoint 9 (busca por raio) - cnae/categoria mínimos pra resolver
    # categoria_id a partir do cnae_principal bruto da observação.
    session.add(
        DimCnae(codigo_cnae="5611203", descricao="Restaurantes e similares")
    )
    session.flush()
    session.add(CnaeCategoriaMap(codigo_cnae="5611203", categoria_id="bares_restaurantes"))

    # entidade/observacao/geolocalizacao - cenário conhecido pra
    # GET /busca-raio: ponto de referência (-49.275, -25.435), dentro do
    # bbox de "Centro" definido acima.
    ref_lon, ref_lat = -49.275, -25.435
    metros_por_grau_lat = 111_320.0

    def _deslocado(metros: float) -> Point:
        return Point(ref_lon, ref_lat + metros / metros_por_grau_lat)

    entidade_perto_alta = uuid.uuid4()
    entidade_media_sem_categoria = uuid.uuid4()
    entidade_baixa = uuid.uuid4()
    entidade_longe = uuid.uuid4()

    session.add_all(
        [
            Entidade(entidade_id=entidade_perto_alta, tipo_entidade="comercio", identificador_fonte="ALVARA-BUSCA-1"),
            Entidade(entidade_id=entidade_media_sem_categoria, tipo_entidade="comercio", identificador_fonte="ALVARA-BUSCA-2"),
            Entidade(entidade_id=entidade_baixa, tipo_entidade="comercio", identificador_fonte="ALVARA-BUSCA-3"),
            Entidade(entidade_id=entidade_longe, tipo_entidade="comercio", identificador_fonte="ALVARA-BUSCA-4"),
        ]
    )
    session.flush()

    observado_em = date(2026, 8, 1)
    session.add_all(
        [
            ObservacaoEntidade(
                entidade_id=entidade_perto_alta,
                observado_em=observado_em,
                atributos={
                    "nome_fantasia": "Restaurante Perto",
                    "nome_empresarial": "PERTO LTDA",
                    "cnae_principal": "I.56.1.1-2/03-00",
                    "territorio_id": "curitiba-bairro-centro",
                    "endereco": "R. X",
                    "numero": "10",
                    "bairro": "CENTRO",
                    "cep": "80000000",
                },
                fonte_id="alvaras_smf",
                snapshot_ref="teste",
            ),
            ObservacaoEntidade(
                entidade_id=entidade_media_sem_categoria,
                observado_em=observado_em,
                atributos={
                    "nome_fantasia": None,
                    "nome_empresarial": "MEDIA SEM CATEGORIA LTDA",
                    "cnae_principal": None,
                    "territorio_id": "curitiba-bairro-centro",
                    "endereco": "R. Y",
                    "numero": "20",
                    "bairro": "CENTRO",
                    "cep": "80000000",
                },
                fonte_id="alvaras_smf",
                snapshot_ref="teste",
            ),
            ObservacaoEntidade(
                entidade_id=entidade_baixa,
                observado_em=observado_em,
                atributos={
                    "nome_fantasia": "Baixa Confianca",
                    "nome_empresarial": "BAIXA LTDA",
                    "cnae_principal": "I.56.1.1-2/03-00",
                    "territorio_id": "curitiba-bairro-centro",
                    "endereco": "R. Z",
                    "numero": "30",
                    "bairro": "CENTRO",
                    "cep": "80000000",
                },
                fonte_id="alvaras_smf",
                snapshot_ref="teste",
            ),
            ObservacaoEntidade(
                entidade_id=entidade_longe,
                observado_em=observado_em,
                atributos={
                    "nome_fantasia": "Muito Longe",
                    "nome_empresarial": "LONGE LTDA",
                    "cnae_principal": "I.56.1.1-2/03-00",
                    "territorio_id": "curitiba-bairro-centro",
                    "endereco": "R. W",
                    "numero": "40",
                    "bairro": "CENTRO",
                    "cep": "80000000",
                },
                fonte_id="alvaras_smf",
                snapshot_ref="teste",
            ),
        ]
    )
    session.add_all(
        [
            GeolocalizacaoEntidade(
                entidade_id=entidade_perto_alta,
                ponto=from_shape(_deslocado(50), srid=4326),
                confianca="alta",
                fonte_primaria="geocodebr",
            ),
            GeolocalizacaoEntidade(
                entidade_id=entidade_media_sem_categoria,
                ponto=from_shape(_deslocado(300), srid=4326),
                confianca="media",
                fonte_primaria="geocodebr",
                fonte_secundaria="nominatim",
            ),
            GeolocalizacaoEntidade(
                entidade_id=entidade_baixa,
                ponto=from_shape(_deslocado(100), srid=4326),
                confianca="baixa",
                fonte_primaria="geocodebr",
                fonte_secundaria="nominatim",
            ),
            GeolocalizacaoEntidade(
                entidade_id=entidade_longe,
                ponto=from_shape(_deslocado(5000), srid=4326),
                confianca="alta",
                fonte_primaria="geocodebr",
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
