import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Modelos ORM importados aqui para que fiquem registrados em Base.metadata
# antes do autogenerate rodar.
from infrastructure.database.orm.base import Base
from infrastructure.database.orm import territorio  # noqa: F401
from infrastructure.database.orm import pipeline_run  # noqa: F401
from infrastructure.database.orm import entidade  # noqa: F401
from infrastructure.database.orm import observacao_entidade  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

load_dotenv()
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# O container postgis/postgis vem com postgis_tiger_geocoder e
# postgis_topology pré-instaladas, que criam dezenas de tabelas em
# tiger/tiger_data/topology/public. Autogenerate só deve enxergar os
# schemas que o projeto de fato gerencia.
SCHEMAS_GERENCIADOS = {"canonical", "events", "infra"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return object.schema in SCHEMAS_GERENCIADOS
    return True

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
