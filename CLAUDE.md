# Project Mercator

Plataforma de eventos territoriais para Curitiba. Primeiro produto: **Radar de Comércio**
(mapeamento de abertura/fechamento de estabelecimentos por bairro e categoria, com séries
temporais). Dono do projeto é solo e não-técnico full-time no código — a arquitetura já foi
decidida; o trabalho aqui é implementá-la fielmente, não redesenhá-la. Se uma decisão já
tomada parecer problemática, pare e explique o trade-off antes de desviar.

## Princípios não-negociáveis

1. Todo produto futuro (Radar Imobiliário, Expansão Urbana, etc.) é uma leitura sobre o
   mesmo substrato de eventos — nenhum produto tem banco ou pipeline isolado.
2. Fonte de dado é plugável, nunca hardcoded no núcleo — `src/domain/` **não pode** importar
   nada de `src/infrastructure/connectors/`. Isso é um erro de design, não um detalhe.
3. Território é uma dimensão de primeira classe, com identidade, geometria e histórico —
   nunca uma string solta.
4. O evento é imutável; o estado é derivado. Nunca se apaga ou sobrescreve um evento ou uma
   observação já gravada.
5. Comece simples; desenhe para evoluir, não para escalar hoje. Nada de Kafka, filas de
   mensagem ou tempo real nesta fase — as fontes atualizam uma vez por mês.
6. Entidade ("quem"), Observação ("o que sabíamos, e quando" — imutável, uma por snapshot) e
   Evento ("o que foi inferido" comparando duas observações) são três conceitos diferentes,
   nunca colapsados em um só. Um evento sempre aponta de volta para as observações que o
   sustentam.

## Stack decidida

Python (3.14 no ambiente atual — todas as libs geoespaciais têm wheels compatíveis).
PostgreSQL + PostGIS (local via `docker-compose.yml`; hospedado em Supabase/Neon para
produção/piloto, ainda não provisionado). Alembic para migrações. pandas/geopandas/DuckDB só
como ferramenta de transformação em lote na ingestão, não como banco canônico. FastAPI em
`apps/api/` (ainda não iniciado). `src/` empacotado via `pyproject.toml` (layout src, modo
editável) — `apps/api` importará de `src/` como biblioteca quando existir.

## Schema (resumo — DDL completo era o de referência do prompt original)

- `canonical.entidade` — quem: `entidade_id`, `tipo_entidade`, `identificador_fonte`
  (ex.: número do alvará), unique(`tipo_entidade`, `identificador_fonte`). **Ainda não
  implementado.**
- `canonical.observacao_entidade` — o que sabíamos e quando: `entidade_id`, `observado_em`,
  `atributos JSONB`, `fonte_id`, `snapshot_ref`. Imutável. **Ainda não implementado.**
- `canonical.dim_territorio` — **implementado**. `territorio_id TEXT PK`, `nivel` (só
  `'bairro'` populado até agora), `nome`, `nome_alternativo TEXT[]`, `geometria
  GEOMETRY(MultiPolygon, 4326)`, `territorio_pai_id` (auto-FK), `cidade_id`.
- `canonical.dim_cnae`, `canonical.dim_categoria`, `canonical.cnae_categoria_map` — **ainda
  não implementados** (checkpoint 4).
- `events.fato_evento_territorial` — o que foi inferido: `evento_id`, `entity_type`,
  `event_type`, `entidade_id`, `territorio_id`, `data_evento`, `confianca`
  (`alta`/`media`/`baixa`), `origem_observacoes UUID[]` (aponta de volta para as
  observações), `payload JSONB`. **Ainda não implementado.**
- `infra.pipeline_run` — **implementado**. Log de execução de conector: `conector_id`,
  `iniciado_em`/`finalizado_em`, `status` (`sucesso`/`falha`/`parcial`), contadores de
  registros lidos/gravados/com falha.

Catálogo de eventos do Radar de Comércio (checkpoint 3, ainda não implementado):
`PRIMEIRA_OBSERVACAO`, `ABERTURA_CONFIRMADA`, `DESAPARECIMENTO`, `MUDANCA_CATEGORIA`. Não
implementar `FECHAMENTO_CONFIRMADO` (depende de uma segunda fonte que ainda não existe).

## Contrato de conector

`src/infrastructure/connectors/base.py` define `Connector` (Protocol) e `RawSnapshot`
(dataclass): `fetch() -> RawSnapshot` busca o bruto e grava na Raw Zone (local, em
`data/raw/<fonte_id>/`, gitignored); `normalize(snapshot) -> list[...]` transforma em
registros canônicos. **Nunca detecta evento aqui** — isso é responsabilidade de
`src/domain/event/` (regra pura) orquestrada por `src/pipelines/event_detection/`.

## Estado da implementação

### Checkpoint 1 — Fundação e território: **concluído**

- Repositório git inicializado; estrutura completa de `apps/`, `src/`, `tests/`,
  `migrations/`, `docs/` criada (exceto `pipelines/normalization/geocoding`, que
  propositalmente não existe ainda).
- `pyproject.toml` com layout src, instalado em modo editável (`pip install -e ".[dev]"`).
  Pacotes top-level: `domain`, `commerce`, `pipelines`, `analytics`, `infrastructure`
  (todos sob `src/`, sem um pacote-raiz `mercator` intermediário).
- `docker-compose.yml` sobe `postgis/postgis:16-3.4` local (usuário/senha/db `mercator`,
  porta 5432). `.env` (não commitado) e `.env.example` com `DATABASE_URL`.
- Alembic inicializado em `migrations/`, `env.py` lê `DATABASE_URL` do `.env` e usa
  `Base.metadata` de `src/infrastructure/database/orm/`. Migração `1fe6bd03d55b` cria os
  schemas `canonical`/`events`/`infra`, a extensão `postgis`, `canonical.dim_territorio` e
  `infra.pipeline_run`.
- `src/domain/territory/models.py` — dataclass `Territorio` (pura, sem dependência de
  infraestrutura; usa `shapely` como tipo de valor para geometria, não como infra).
- `src/infrastructure/database/` — `engine.py`, `session.py` (`get_session()` context
  manager), `orm/` (SQLAlchemy: `DimTerritorio`, `PipelineRun`), `repositories/
  territorio_repository.py` (upsert idempotente + list).
- `src/infrastructure/connectors/geocuritiba_bairro/` — conector da camada Bairro do
  GeoCuritiba (IPPUC), ArcGIS REST, sem token.
  - `geometry.py` — reprojeção EPSG:31982 → 4326 (`pyproj`), conversão de anéis Esri
    (respeitando orientação horário/anti-horário para buracos e múltiplas partes) para
    `shapely.MultiPolygon`.
  - `text.py` — `slugify` para gerar `territorio_id` a partir do nome (ex.:
    `curitiba-bairro-campo-comprido`).
  - `connector.py` — pagina via `resultOffset`/`resultRecordCount` até
    `exceededTransferLimit` ser falso; salva o snapshot bruto em
    `data/raw/geocuritiba_bairro/<timestamp>.json`.
- `src/pipelines/ingestion/run_geocuritiba_bairro.py` — orquestra fetch → normalize →
  upsert, registrando o run em `infra.pipeline_run`.
- **Rodado contra a API real**: 75 bairros gravados em `canonical.dim_territorio`, todas as
  geometrias válidas (`ST_IsValid`) em `ST_SRID = 4326`, `ids` únicos.
- 18 testes automatizados (`tests/domain/territory/`,
  `tests/infrastructure/connectors/geocuritiba_bairro/`) cobrindo validação do domínio,
  reprojeção, orientação de anéis/buracos/múltiplas partes, e paginação do conector
  (sessão HTTP falsa, sem depender da API real). Todos passando.

### Próximo checkpoint: Checkpoint 2 — Entidade e observação (sem evento ainda)

- Implementar `src/domain/entity/` e `src/domain/observation/`.
- Implementar `src/infrastructure/connectors/alvaras_smf/`: fetch de um snapshot mensal
  (streaming — arquivo tem centenas de MB, não pode ir para memória inteira nem para o
  git), normalize para `Entidade` + `ObservacaoEntidade`, resolvendo `BAIRRO` contra
  `canonical.dim_territorio` (usar `nome`/slug já gravado; divergências de grafia devem ser
  **registradas**, não devem falhar o pipeline inteiro).
- Confirmar uma amostra de 10–20 registros manualmente contra o CSV original antes de
  considerar o checkpoint concluído.
- Confirmar a URL exata do mês corrente no catálogo de dados abertos antes do fetch — não
  hardcodar uma data.

## Notas operacionais

- Ambiente Python único disponível na máquina é 3.14 (via `py -0p`); todas as dependências
  do projeto têm wheels compatíveis, confirmado por dry-run antes de instalar.
- Docker Desktop precisa estar rodando para `docker compose up -d` funcionar; não estava
  ativo por padrão neste ambiente.
- `data/raw/` é gitignored — nunca commitar snapshots brutos.
