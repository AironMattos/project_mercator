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

- `canonical.entidade` — **implementado**. Quem: `entidade_id`, `tipo_entidade`,
  `identificador_fonte` (ex.: número do alvará), unique(`tipo_entidade`,
  `identificador_fonte`).
- `canonical.observacao_entidade` — **implementado**. O que sabíamos e quando: `entidade_id`,
  `observado_em`, `atributos JSONB`, `fonte_id`, `snapshot_ref`. Imutável. Constraint extra
  (não estava no DDL de referência, adicionada deliberadamente): unique(`entidade_id`,
  `fonte_id`, `observado_em`) com `ON CONFLICT DO NOTHING` no insert — reprocessar o mesmo
  snapshot não duplica a observação, mas uma observação gravada nunca é atualizada/apagada.
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

Para fontes muito grandes (ex.: `alvaras_smf`, ~545MB), `normalize()` pode ser um **gerador**
em vez de retornar uma `list` (não carregar tudo em memória) e aceitar parâmetros extras
(ex.: `territorio_id_por_slug`) além do `snapshot` — é um desvio deliberado da assinatura
exata do `Protocol`, que não é estritamente verificada em runtime.

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

### Checkpoint 2 — Entidade e observação (sem evento ainda): **concluído**

- `src/domain/entity/models.py` — dataclass `Entidade` pura. `entidade_id` é um candidato
  gerado localmente (`uuid4`); se a entidade já existir no banco pela chave de negócio
  (`tipo_entidade`, `identificador_fonte`), o id efetivamente usado é o já existente, não o
  candidato — a resolução acontece em `entidade_repository.upsert_entidades` (upsert em lote
  via `INSERT ... ON CONFLICT ... RETURNING`, deduplicado por chave de negócio dentro do
  lote).
- `src/domain/observation/models.py` — dataclass `ObservacaoEntidade` pura.
- `src/infrastructure/database/orm/entidade.py`, `orm/observacao_entidade.py`,
  `repositories/entidade_repository.py`, `repositories/observacao_repository.py`.
- Migração `905d84c028ef` cria `canonical.entidade` e `canonical.observacao_entidade`.
  `migrations/env.py` ganhou um filtro `include_object` para autogenerate ignorar as
  extensões `postgis_tiger_geocoder`/`postgis_topology` pré-instaladas pela imagem
  `postgis/postgis` (schemas `tiger`/`tiger_data`/`topology`/`public`), que não são
  gerenciadas por este projeto.
- `src/infrastructure/connectors/alvaras_smf/` — conector da Base de Alvarás (Curitiba/SMF).
  - **Divergência da fonte vs. documentado** (usuário confirmou como prosseguir): o host
    documentado originalmente (`mid.curitiba.pr.gov.br/dadosabertos/BaseAlvaras/`) não serve
    mais o arquivo (403 no diretório, 404 no arquivo do mês corrente). O catálogo oficial
    (`dadosabertos.curitiba.pr.gov.br/conjuntodado/detalhe/?chave=be211e1f-...`) aponta hoje
    para um mirror do C3SL/UFPR: `dadosabertos.c3sl.ufpr.br/curitiba/BaseAlvaras/`. Nome do
    arquivo e colunas batem exatamente com o documentado. `connector.py::_arquivo_mais_recente`
    resolve a URL do mês corrente fazendo parse da listagem desse diretório (nunca hardcoda
    data ou host).
  - Também não documentado originalmente: delimitador é `;` (não vírgula), encoding é
    **ISO-8859-1/latin-1** (não UTF-8), valores ausentes são `***` (não string vazia).
  - `fetch()` baixa em streaming (chunks de 1MB direto pro disco) — arquivo tem ~545MB, nunca
    vai inteiro pra memória. `normalize()` é um **gerador** que lê o CSV em chunks via pandas
    e resolve `BAIRRO` contra `dim_territorio` por slug (reaproveita `slugify`, agora em
    `infrastructure/connectors/text.py`, compartilhado entre conectores). Bairro sem
    correspondência: fica com `territorio_id=None` no atributo e é logado em warning agregado
    (uma vez por bairro não casado, não por linha) — não derruba o pipeline.
  - `identificador_fonte` da entidade = `NUMERO_DO_ALVARA`. `tipo_entidade = "comercio"`.
    `observado_em` da observação = data extraída do nome do arquivo (dia 1 do mês), não datas
    de linha (`INICIO_ATIVIDADE`/`DATA_EMISSAO` são atributos da entidade, não a data do
    snapshot).
- `src/pipelines/ingestion/run_alvaras_smf.py` — orquestra em lotes de 5000: upsert de
  entidade (resolve id real) → remapeia `entidade_id` da observação se necessário → insert de
  observação.
- **Rodado contra o arquivo real** (`2026-08-01_Alvaras_-_Base_de_Dados.csv`, 545MB):
  513.293 linhas lidas, 511.361 observações gravadas (diferença = duplicatas de
  `NUMERO_DO_ALVARA` na mesma referência mensal, bloqueadas pela constraint de idempotência).
  94,0% das observações resolveram `territorio_id` (480.695 de 511.361); os ~6% restantes são
  variações de grafia genuínas da fonte (`"CIC"`, `"Cidade Industrial"` vs.
  `"CIDADE INDUSTRIAL DE CURITIBA"`, `"BAIRRO NAO INFORMADO"`, códigos numéricos soltos, etc.)
  — logadas, não tratadas como erro.
- **Conferência manual**: 15 registros escolhidos aleatoriamente no banco, comparados campo a
  campo contra o CSV bruto original. 0 divergências.
- 23 novos testes automatizados (`tests/domain/entity/`, `tests/domain/observation/`,
  `tests/infrastructure/connectors/alvaras_smf/`) — parsing de data/valores ausentes,
  resolução de URL do diretório, download em streaming, resolução/não-resolução de bairro,
  linha sem `NUMERO_DO_ALVARA` ignorada. Total do projeto: 41 testes, todos passando.

### Próximo checkpoint: Checkpoint 3 — Detecção de evento

- Baixar um segundo snapshot de um mês diferente do já processado (`2026-08-01`) — usar
  qualquer mês histórico ainda acessível no mirror C3SL/UFPR (`2026-07-01`, `2026-06-01`, etc.
  já confirmados existentes no diretório).
- Implementar `src/domain/event/` (regra pura: dado o histórico de observações de uma
  entidade, qual evento resulta) com teste automatizado para cada `event_type` do catálogo:
  `PRIMEIRA_OBSERVACAO`, `ABERTURA_CONFIRMADA`, `DESAPARECIMENTO`, `MUDANCA_CATEGORIA`. Não
  implementar `FECHAMENTO_CONFIRMADO` (depende de segunda fonte que não existe ainda).
- Implementar `src/pipelines/event_detection/` chamando essa regra sobre os dois snapshots.
- Confirmar que o volume de `PRIMEIRA_OBSERVACAO`/`DESAPARECIMENTO` é plausível (ordem de
  grandeza compatível com ~510 mil observações por snapshot) antes de seguir.

## Notas operacionais

- Ambiente Python único disponível na máquina é 3.14 (via `py -0p`); todas as dependências
  do projeto têm wheels compatíveis, confirmado por dry-run antes de instalar.
- Docker Desktop precisa estar rodando para `docker compose up -d` funcionar; não estava
  ativo por padrão neste ambiente.
- `data/raw/` é gitignored — nunca commitar snapshots brutos. O CSV de alvarás baixado
  (~545MB) fica em `data/raw/alvaras_smf/` e não é commitado; rodar
  `python -m pipelines.ingestion.run_alvaras_smf` de novo baixa o mês corrente outra vez.
- O repositório está conectado a um remoto GitHub (`github.com/AironMattos/project_mercator`,
  branch `main`) — aparentemente configurado via "Share on GitHub" do PyCharm durante a
  sessão do checkpoint 1. Um commit "Initial commit" feito pela IDE capturou um arquivo de
  scratch que vazou para o working directory; foi removido em commit separado
  (`chore: remove cat.html`). Cuidado ao rodar comandos de investigação (curl, etc.) que
  escrevam arquivos na raiz do projeto — preferir a pasta de scratchpad da sessão quando
  possível, ou limpar antes de qualquer commit/sync com o remoto.
- ORM: `server_default` de coluna UUID/timestamp que é uma *expressão* SQL (ex.:
  `gen_random_uuid()`, `now()`) precisa ser `sa.text("...")`, nunca uma string Python pura —
  Postgres tenta converter a string literal para o tipo da coluna e falha. Detectado e
  corrigido em `orm/entidade.py`, `orm/observacao_entidade.py`, `orm/pipeline_run.py`.
