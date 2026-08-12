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
`apps/api/` — **iniciado no checkpoint 6a**, rotas finas em `apps/api/routers/` chamando
repositórios de `src/infrastructure/database/repositories/`, sem lógica de negócio própria.
`src/` empacotado via `pyproject.toml` (layout src, modo editável) — `apps/api` importa
`domain`/`commerce`/`analytics`/`infrastructure` de `src/` como biblioteca (pacote `mercator`
instalado em modo editável no `.venv`). Next.js (App Router) + TypeScript + Tailwind +
shadcn/ui + MapLibre GL JS + Recharts em `apps/web/` — ainda não iniciado (checkpoint 7).

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
- `canonical.dim_cnae` — **implementado**. `codigo_cnae TEXT PK` (7 dígitos, padrão do
  "id" da API do IBGE), `descricao`, `secao`, `divisao`, `grupo`, `classe`, `subclasse`.
- `canonical.dim_categoria` — **implementado**. `categoria_id TEXT PK`, `nome`. 26 categorias.
- `canonical.cnae_categoria_map` — **implementado**. `(codigo_cnae, categoria_id)` PK
  composta, ambos FK. 79 mapeamentos (lista pequena e explícita, de propósito).
- `events.fato_evento_territorial` — **implementado**. O que foi inferido: `evento_id`,
  `entity_type`, `event_type`, `entidade_id`, `territorio_id`, `data_evento`, `confianca`
  (`alta`/`media`/`baixa`), `origem_observacoes UUID[]` (aponta de volta para as
  observações), `payload JSONB`. Constraint extra (adicionada deliberadamente, mesmo padrão
  de `observacao_entidade`): unique(`entidade_id`, `event_type`, `data_evento`) com
  `ON CONFLICT DO NOTHING` — reprocessar o mesmo par de snapshots não duplica o mesmo evento.
- `infra.pipeline_run` — **implementado**. Log de execução de conector: `conector_id`,
  `iniciado_em`/`finalizado_em`, `status` (`sucesso`/`falha`/`parcial`), contadores de
  registros lidos/gravados/com falha.
- `analytics.contagem_eventos` — **implementado** (checkpoint 5, schema `analytics` novo).
  `territorio_id`/`categoria_id` (FK, nullable), `mes DATE`, `event_type`, `contagem INT`.
  Sem PK de negócio (território/categoria podem ser nulos) - é 100% derivada de
  `fato_evento_territorial`, recomputada do zero (`DELETE` + `INSERT`) a cada execução, nunca
  atualizada linha a linha.

Catálogo de eventos do Radar de Comércio (`entity_type = "comercio"`) — **implementado**:
`PRIMEIRA_OBSERVACAO`, `ABERTURA_CONFIRMADA`, `DESAPARECIMENTO`, `MUDANCA_CATEGORIA`.
`FECHAMENTO_CONFIRMADO` fica reservado no catálogo (`TIPOS_EVENTO_VALIDOS`), sem regra que o
gere (depende de uma segunda fonte que ainda não existe).

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

### Checkpoint 3 — Detecção de evento: **concluído**

- Segundo snapshot ingerido: `2026-07-01_Alvaras_-_Base_de_Dados.csv` (mesmo mirror
  C3SL/UFPR), via `python -m pipelines.ingestion.run_alvaras_smf
  "2026-07-01_Alvaras_-_Base_de_Dados.csv"` — `AlvarasSmfConnector.fetch()` ganhou um
  parâmetro opcional `nome_arquivo` para buscar um mês histórico específico (por padrão
  continua resolvendo o mês mais recente) e reaproveita o arquivo local se já baixado.
- `src/domain/event/models.py` — dataclass `Evento` pura. `TIPOS_EVENTO_VALIDOS` inclui
  `FECHAMENTO_CONFIRMADO` como valor reservado (validação aceita, nenhuma regra o gera).
- `src/domain/event/regras.py` — duas funções puras, sem I/O:
  - `detectar_eventos_par(anterior, atual, entity_type)`: sem `anterior`, decide entre
    `ABERTURA_CONFIRMADA` (alta) e `PRIMEIRA_OBSERVACAO` (baixa) - **mutuamente exclusivos**;
    com `anterior`, gera `MUDANCA_CATEGORIA` (media) se o CNAE principal mudou.
  - `detectar_desaparecimento(ultima_observacao_conhecida, entity_type, data_snapshot_atual)`:
    constrói o evento a partir da premissa (já estabelecida pelo pipeline, via diferença de
    conjunto entre os dois snapshots) de que a entidade não aparece mais.
  - **Interpretação de design que exigiu julgamento** (catálogo original não especifica isso):
    quando uma entidade aparece pela primeira vez E o `INICIO_ATIVIDADE` cai no período
    coberto pelo snapshot, emitimos só `ABERTURA_CONFIRMADA` (alta), não as duas — tratado
    como uma leitura mais específica do mesmo fato, não um evento adicional.
  - **Achado ao validar contra dado real, corrigido antes de consolidar**: o arquivo é datado
    no dia 1º do mês (ex.: `2026-08-01`) mas reflete o estado consolidado até o fim do mês
    ANTERIOR (julho) — confirmado comparando os dois snapshots: entidades que aparecem pela
    primeira vez no arquivo de agosto têm `INICIO_ATIVIDADE` concentrado em julho, não agosto.
    A regra de `ABERTURA_CONFIRMADA` compara `INICIO_ATIVIDADE` contra o mês **anterior** ao
    `observado_em` do snapshot, não o mesmo mês (a primeira versão comparava o mesmo mês e
    nunca disparava - 0 eventos).
- `src/infrastructure/database/orm/fato_evento_territorial.py`,
  `repositories/evento_repository.py` (insert em lote, idempotente).
  `observacao_repository.iter_grupos_por_entidade`: cursor server-side (`yield_per`) que
  agrupa por entidade as observações de duas datas, sem carregar os ~500 mil registros de
  cada snapshot em memória de uma vez.
- Migração `df04a47294e3` cria `events.fato_evento_territorial`.
- `src/pipelines/event_detection/run_comercio.py` — orquestra a comparação, grava em lotes
  de 5000. Uso: `python -m pipelines.event_detection.run_comercio 2026-07-01 2026-08-01`.
- **Rodado contra dado real** (2026-07-01 vs 2026-08-01, ~515 mil entidades): 6.697 eventos —
  `DESAPARECIMENTO` 3.757, `ABERTURA_CONFIRMADA` 1.440, `PRIMEIRA_OBSERVACAO` 1.421,
  `MUDANCA_CATEGORIA` 79. Ordem de grandeza plausível (churn mensal ~0,7%, abertura ~0,3%)
  frente às ~510 mil observações por snapshot.
- 16 novos testes automatizados (`tests/domain/event/`) — um por `event_type` implementado,
  caso de mutualidade exclusiva `ABERTURA_CONFIRMADA`/`PRIMEIRA_OBSERVACAO`, virada de ano,
  ausência de evento quando CNAE não muda ou está incompleto, validação do domínio `Evento`.
  Total do projeto: 57 testes, todos passando.

### Checkpoint 4 — CNAE e categoria: **concluído**

- **Formato de CNAE da fonte decifrado** (nem o prompt original nem o "dicionário de dados"
  publicado pela própria SMF documentam esse campo). Investigando o dado real (~511 mil
  observações de 2026-08): ~97% dos códigos distintos seguem o formato
  `<seção A-U>.<divisão 2d>.<grupo 1d>.<classe 1d>-<dv 1d>/<subclasse 2d>-<sufixo "00">`
  (ex.: `"S.96.0.2-5/01-00"`); concatenando divisão+grupo+classe+dv+subclasse dá exatamente o
  código de 7 dígitos que a API do IBGE usa - **confirmado comparando três casos reais contra
  descrições oficiais conhecidas** (cabeleireiros, padaria com produção própria, padaria com
  revenda - todos bateram exatamente). Os ~3% restantes (`"5-70.20.00"`) e um placeholder óbvio
  (`"X.88.8.8-8/88-88"` - seção "X" não existe na CNAE oficial, que vai só até "U") não
  correspondem a nenhum código real; ficam como não resolvidos (`None`), mesmo tratamento dado
  a divergências de bairro no checkpoint 2. **Achado durante os testes**: a primeira versão do
  regex aceitava qualquer letra `A-Z` como seção, então o placeholder "X..." normalizava
  silenciosamente para um código inexistente (`"8888888"`) - pego por
  `test_placeholder_nao_reconhecido_retorna_none`, corrigido restringindo a seção a `A-U`. Não
  afetou nenhum resultado já gravado (esse código nunca esteve no mapeamento de categorias).
- `src/commerce/cnae/` — `Cnae` (dataclass pura) e
  `normalizar_codigo_cnae()` (regra pura, só regex, sem I/O).
- `src/infrastructure/connectors/ibge_cnae/` — conector da tabela oficial de CNAE, via API
  pública do IBGE (`servicodados.ibge.gov.br/api/v2/cnae/subclasses`, sem chave). Fonte
  estática (`cadencia = "estatica"`).
- `src/commerce/categories/` — 26 categorias legíveis (`CATEGORIAS`) e um mapeamento explícito
  de 79 códigos CNAE (`MAPEAMENTO_CNAE_CATEGORIA`) — os códigos mais frequentes nas
  observações reais de agosto/2026, cobrindo ~65% das observações com CNAE normalizável. Lista
  pequena e explícita de propósito (conforme pedido no checkpoint) - não tenta cobrir as
  ~1300 subclasses oficiais.
- `src/infrastructure/database/orm/dim_cnae.py`, `dim_categoria.py`, `cnae_categoria_map.py` +
  repositórios correspondentes. Migração `0ab71b50497e` cria as três tabelas.
- `src/pipelines/ingestion/run_ibge_cnae.py` (fetch+normalize+upsert de `dim_cnae`) e
  `run_categorias.py` (semeia `dim_categoria`/`cnae_categoria_map` a partir do mapeamento
  estático - precisa rodar depois de `run_ibge_cnae`, já que há FK para `dim_cnae`).
- **Payload dos eventos de comércio enriquecido com categoria**: `pipelines/event_detection/
  run_comercio.py` resolve `categoria_id` (via `normalizar_codigo_cnae` + o mapeamento
  carregado do banco) e injeta no `payload` de todo evento, não só `MUDANCA_CATEGORIA` — usa
  o CNAE da observação atual (ou da última observação conhecida, para `DESAPARECIMENTO`). A
  resolução acontece na orquestração do pipeline, não em `domain/event/regras.py`, que
  continua puro e sem depender de `commerce/`.
- **Rodado contra dado real**: 1.332 subclasses CNAE gravadas (IBGE), 26 categorias + 79
  mapeamentos gravados. Eventos reprocessados: dos 511.361 registros de agosto, 66,4% têm CNAE
  normalizável e 44,4% têm categoria resolvida; dos 6.697 eventos gravados, 4.212 (63%)
  carregam `categoria_id` no payload.
- 22 novos testes automatizados (`tests/commerce/cnae/`, `tests/commerce/categories/`,
  `tests/infrastructure/connectors/ibge_cnae/`) — normalização com casos reais validados
  contra descrições oficiais, rejeição do formato legado e do placeholder, consistência do
  mapeamento categoria↔código, conector com sessão HTTP falsa. Total do projeto: 77 testes,
  todos passando.

### Checkpoint 5 — Primeira feature: **concluído**

- `src/analytics/features/models.py` — dataclass `ContagemEventos` (territorio_id,
  categoria_id, mes, event_type, contagem). `contagem_eventos.py` —
  `calcular_contagem_por_bairro_categoria_mes(eventos: Iterable[Evento]) -> list[ContagemEventos]`,
  regra pura (recebe `Evento` já carregados, sem I/O), agrupa por
  (`territorio_id`, `payload["categoria_id"]`, mês de `data_evento`, `event_type`), só para
  `PRIMEIRA_OBSERVACAO` e `DESAPARECIMENTO` — nada de quociente locacional, nada de Signal
  Engine ainda, exatamente como pedido.
- `infrastructure/database/orm/contagem_eventos.py` + `repositories/feature_repository.py`
  (`substituir_contagem_eventos`: `DELETE` + `INSERT` completo a cada execução - seguro porque
  a tabela é 100% derivada, não é fonte de verdade) + `evento_repository.iter_eventos`
  (lê `fato_evento_territorial` de volta como `Evento` de domínio).
- Migração `52bae9c35c69` cria o schema `analytics` e `analytics.contagem_eventos`.
- `src/analytics/features/run_contagem_eventos.py` — carrega eventos, calcula, grava, e
  imprime um resumo (top 10 bairros/categorias por tipo de evento) para conferência visual.
- **Rodado contra dado real**: 6.697 eventos → 1.605 linhas de contagem. **A história é
  coerente**: CENTRO lidera tanto `PRIMEIRA_OBSERVACAO` (216) quanto `DESAPARECIMENTO` (407) -
  esperado, é o bairro de maior densidade comercial de Curitiba - seguido por bairros
  comerciais conhecidos (Água Verde, Batel, Bigorrilho, Portão, Juvevê). Por categoria, "Saúde
  e clínicas" e "Bares, restaurantes e lanchonetes" lideram aberturas; "Apoio administrativo"
  e "Seguros e serviços financeiros" lideram desaparecimentos - plausível para setores de alto
  turnover. ~40-55% dos eventos ficam sem bairro/categoria resolvido (herda a cobertura
  parcial dos checkpoints 2 e 4) - aparece como "(sem bairro)"/"(sem categoria)" no resumo, não
  é descartado silenciosamente.
- 6 novos testes automatizados (`tests/analytics/features/`). Total do projeto: **83 testes,
  todos passando**.

Os 5 checkpoints da sequência original (fundação até a primeira feature) estão concluídos.
Depois de uma revisão, a sequência seguiu para uma segunda fase: API (FastAPI) + frontend
(Next.js/MapLibre/Recharts) servindo o Radar de Comércio, dividida em checkpoints 6a-7d
(ver prompt de referência da fase 2 para o detalhe completo de cada um).

### Checkpoint 6a — API local: **concluído**

- `apps/api/` inicializado. `main.py` (app FastAPI + CORS), `dependencies.py`
  (`get_db`, adapta `infrastructure.database.session.get_session` para o `Depends` do
  FastAPI), `schemas.py` (modelos Pydantic de resposta), `routers/` (um módulo por recurso:
  `territorios.py`, `categorias.py`, `metricas.py`). Rotas finas de propósito — cada handler
  só chama um repositório de `src/infrastructure/database/repositories/` e reformata o
  resultado; nenhuma regra de negócio nova mora em `apps/api/`.
- Três endpoints implementados, todos `GET`, sem autenticação (deliberado, conforme escopo
  desta fase):
  - `/territorios` — `dim_territorio` (nível `bairro`) como GeoJSON `FeatureCollection`
    (`shapely.geometry.mapping` sobre a geometria já em EPSG:4326).
  - `/categorias` — `dim_categoria` (`categoria_id`, `nome`).
  - `/metricas/comercio` — filtros `territorio_id`, `categoria_id`, `data_inicio`,
    `data_fim` (todos opcionais via query param). **Sem `territorio_id`**: agregado por
    bairro (soma o período inteiro) — para colorir o mapa. **Com `territorio_id`**: agrupado
    por mês — a série temporal completa daquele bairro, para o painel de detalhe. Formato do
    item: `{ territorio_id, categoria_id, mes, aberturas, desaparecimentos, saldo }`
    (`saldo = aberturas - desaparecimentos`).
  - `/health` — checagem simples para o health check da plataforma de deploy (checkpoint 6b).
- Duas funções novas de leitura, na mesma camada de repositório já existente (dado que a
  reformatação de linhas de `analytics.contagem_eventos` em `aberturas`/`desaparecimentos`/
  `saldo` é reshape de dado já calculado, não uma regra nova — por isso vive em
  `infrastructure/`, não em `domain/` nem em `apps/api/`):
  `categoria_repository.listar_categorias` e
  `feature_repository.consultar_metricas_comercio` (agregação via SQL —
  `SUM(CASE WHEN event_type = ...)` agrupado por bairro ou por bairro+mês, conforme
  `territorio_id` esteja ausente ou presente).
- CORS: `CORSMiddleware` com origens configuráveis via `CORS_ORIGINS` (env var, lista separada
  por vírgula) — `http://localhost:3000` sempre incluído por padrão. A URL de produção do
  Vercel ainda não existe (checkpoint 7d não rodou) — falta setar `CORS_ORIGINS` na plataforma
  de deploy da API assim que o domínio do Vercel existir; documentado em `.env.example`.
- **Rodado localmente contra o Postgres real** (dado dos checkpoints 1-5): `/categorias`
  devolve as 26 categorias, `/territorios` devolve os 75 bairros como GeoJSON válido,
  `/metricas/comercio` sem filtro devolve 1 linha por bairro (ex.: CENTRO — 216 aberturas, 407
  desaparecimentos, saldo -191, coerente com o resumo do checkpoint 5), com `territorio_id`
  devolve a série (hoje só agosto/2026 tem eventos gravados — 1 ponto na série; mais meses vão
  aparecer automaticamente conforme mais snapshots forem processados, sem mudança de código).
- Testes automatizados: `tests/api/conftest.py` recria um banco `mercator_test` do zero
  (schemas + extensão PostGIS + `Base.metadata.create_all`) e semeia um cenário mínimo e
  conhecido (2 bairros, 2 categorias, contagens em jul/ago-2026) a cada sessão de teste — a
  API é toda leitura, então a sessão semeada é reaproveitada entre os testes sem necessidade de
  rollback por teste. `tests/api/test_endpoints.py` cobre os três endpoints (geojson bem
  formado, agregação por bairro, série por mês, filtro de categoria, filtro de intervalo de
  data, bairro sem dado, CORS, health). 9 novos testes, todos passando. Total do projeto: **92
  testes, todos passando**.
- `pyproject.toml`: `httpx` adicionado a `dev` (dependência do `TestClient` do FastAPI);
  `apps/api` adicionado a `pythonpath` do pytest (para os testes importarem `main`/
  `dependencies` sem hack de `sys.path`).

**Checkpoint 6b (deploy da API) e 7d (deploy do frontend) adiados por decisão do dono**: nesta
fase inicial não há necessidade de nenhuma URL pública — API e frontend rodam localmente
(`uvicorn` local + Next.js `dev`, API local apontada via `NEXT_PUBLIC_API_URL`). Não é uma
omissão, é a mesma decisão de "comece simples" do princípio 5, estendida ao deploy: sem banco
hospedado (Supabase/Neon) provisionado ainda, sem Render/Vercel configurados. Retomar 6b/7d é
trabalho futuro condicional, não bloqueia o restante da sequência (7a-7c seguem localmente).

### Checkpoint 7a — Esqueleto do frontend: **concluído**

- `apps/web/` inicializado via `create-next-app` (Next.js **16.3.0**, App Router, TypeScript,
  Tailwind v4, `src/` layout) + `shadcn/ui` (`components.json`, estilo `base-nova`, base color
  `neutral`) — componentes adicionados: `select`, `sheet`, `card`, `skeleton`, `alert`,
  `badge`, `popover`, `command`, `calendar`, `button`. **Nota de versão**: Next.js 16 é mais
  novo que o conhecimento do modelo (o próprio scaffold gera um `AGENTS.md` avisando disso,
  mantido no repo) — convenções checadas contra `node_modules/next/dist/docs/` antes de
  escrever código; nada de relevante mudou para o que foi construído aqui (Server/Client
  Components, `"use client"`, `next/font` funcionam como esperado).
- Tipografia e paleta de tinta da seção 4.2 do prompt de referência já aplicadas globalmente em
  `src/app/globals.css` (sobrescrevendo os tokens default do shadcn, não só os do mapa/gráfico):
  fonte `system-ui, -apple-system, "Segoe UI", sans-serif` (removido o Geist do scaffold —
  spec pede explicitamente sem fonte display nesta fase), `--background #ffffff`,
  `--foreground #0b0b0b`, `--muted-foreground #52514e`, `--border #e1e0d9`. Modo escuro
  **não** implementado nesta fase (opcional pela spec) - os tokens `.dark` ficaram como
  default do shadcn, mas inertes (sem toggle, sem media query automática).
- `src/lib/api.ts` — cliente HTTP tipado para os três endpoints de `apps/api/`
  (`getTerritorios`, `getCategorias`, `getMetricasComercio`), lendo a URL da API de
  `NEXT_PUBLIC_API_URL` (`.env.local`, gitignored; `.env.example` documenta a variável -
  default `http://localhost:8000`, a API local do checkpoint 6a).
- `src/components/dashboard.tsx` (`"use client"`) — layout base: cabeçalho, linha de filtros
  (combobox de categoria já populado pela API real; período com os presets da seção 4.3 do
  prompt, ainda não ligado a nenhum request) e área de conteúdo. Os três estados exigidos pela
  seção 4.1 já existem aqui, antes mesmo do mapa existir: **carregando** (`Skeleton`), **erro**
  (`Alert` destructive, com a URL da API configurada na mensagem) e **vazio** (`Alert` neutro se
  a API responder sem território nenhum) — meta é nunca deixar a tela em um spinner infinito ou
  uma tela quebrada. Estado "pronto" mostra 3 cards de conferência (contagem de territórios,
  categorias e linhas de métrica) - um placeholder deliberado, substituído pelo mapa no
  checkpoint 7b.
- **Rodado localmente**: `npm run build` compila e type-checa sem erro; `npm run lint` sem
  avisos; `npm run dev` (porta 3000) consumindo `uvicorn` local (porta 8000) - confirmado via
  `curl` que as respostas de `/territorios`, `/categorias` e `/metricas/comercio` carregam o
  header CORS certo para `http://localhost:3000` (não só o preflight `OPTIONS`, a resposta real
  também), e que os dados batem com o esperado (75 territórios, 26 categorias, 73 linhas de
  métrica agregada - 72 bairros com pelo menos um evento + 1 linha agregada de eventos sem
  bairro resolvido). **Verificação visual no navegador não foi feita por mim** - a extensão
  Claude em Chrome foi recusada nesta sessão, e não há outra forma de rodar JS no browser
  disponível; os três estados (carregando/erro/vazio) e os 3 cards de conferência não foram
  vistos renderizados de fato. Pedir para o dono abrir `http://localhost:3000` (com a API
  rodando) e confirmar visualmente antes de considerar o checkpoint fechado de verdade.

### Checkpoint 7b — Mapa coroplético: **concluído**

- `src/lib/palette.ts` — a codificação divergente da seção 4.2 do prompt de referência.
  Braço azul (saldo positivo) é literal da spec. **Braço vermelho não estava na spec** (só o
  degrau intermediário `#e34948` estava fixado) - construído com o skill `dataviz`: mesma
  contagem de degraus do azul (9), hue único (~21-28°), luminosidade estritamente monotônica
  claro→escuro, degrau 5 pinado no hex exato `#e34948`. Validado com
  `validate_palette.js --ordinal` (checa monotonicidade de L, que é o que importa para uma
  rampa sequencial/divergente - o skill documenta que os outros checks do modo ordinal, feitos
  pra marcas discretas lado a lado, falham "by design" numa rampa contínua e não são o
  critério aqui; a própria rampa azul de referência do skill falha os mesmos checks). Nenhum
  degrau fora do gamute sRGB (checado explicitamente - a primeira tentativa estourava gamute
  nos dois degraus mais claros, corrigido reduzindo o chroma alvo desses dois pontos).
  `expressaoCorPorSaldo(min, max)` gera a expressão MapLibre `interpolate`/`linear` com os 18
  degraus (9+9) mais o cinza neutro no zero, escalados pelos extremos reais do período
  filtrado (nunca um domínio fixo).
- `src/components/choropleth-map.tsx` — MapLibre GL JS (`maplibre-gl` v6; a API atual não tem
  mais export default, é `import { Map, NavigationControl, Popup, LngLatBounds } from
  "maplibre-gl"`, diferente de versões mais antigas). Estilo base:
  `https://demotiles.maplibre.org/style.json` (demo tiles oficiais do próprio MapLibre - sem
  token, mas é uma dependência de rede externa; se isso for um problema no futuro, dá pra
  trocar por um estilo em branco ou auto-hospedado). Uma fonte GeoJSON (`/territorios`) com o
  `saldo`/`aberturas`/`desaparecimentos` de `/metricas/comercio` (sem `territorio_id`,
  agregado por bairro) injetados nas `properties` de cada feature antes do `setData` -
  bairro sem nenhum evento no período vira `saldo=0` (cai exatamente no cinza neutro da
  expressão, sem precisar de um caso especial) e fica marcado com `temDado=false` só para o
  texto do popup ("sem evento no período" em vez de "saldo 0"). Popup no hover (nome do
  bairro + saldo/aberturas/fechamentos), clique emite `territorio_id` via callback
  (`onSelecionarTerritorio`, ainda sem consumidor - é o gancho para o painel de detalhe do
  checkpoint 7c). `fitBounds` calculado a partir da geometria real dos 75 bairros, não um
  centro/zoom chumbado.
- `src/components/saldo-legend.tsx` — gradiente simples (vermelho escuro → cinza → azul
  escuro) com os extremos reais do período, sempre visível acima do mapa (a recomendação do
  skill `dataviz` de legenda sempre presente, adaptada pra uma rampa contínua em vez de
  categórica).
- `dashboard.tsx`: as 3 cards de conferência do checkpoint 7a foram substituídas pelo mapa de
  verdade. Filtros de categoria/período continuam na tela mas **ainda não ligados** ao mapa -
  isso é trabalho do checkpoint 7c por definição do prompt de referência, não esquecimento (a
  UI mostra um aviso "filtros ainda não ligados ao mapa" enquanto isso).
- **Rodado localmente**: `npm run build` compila e type-checa sem erro; `npm run lint` sem
  avisos; confirmado via `curl` que `/territorios` devolve ~1,87MB de GeoJSON (75 bairros,
  aceitável para carregar uma vez no cliente) e que `demotiles.maplibre.org` (a fonte do
  estilo base) está acessível. **Verificação visual de novo não foi feita por mim** - mesma
  limitação do checkpoint 7a (sem Chrome disponível nesta sessão). Pedir para o dono abrir
  `http://localhost:3000` (com a API local rodando) e confirmar visualmente: bairros com mais
  aberturas tendendo ao azul, bairros com mais fechamentos tendendo ao vermelho, hover
  mostrando popup com o nome do bairro.

### Checkpoint 7c — Painel de detalhe: **concluído**

- `src/lib/periodo.ts` — `intervaloUltimosMeses(meses)` calcula `dataInicio`/`dataFim` a
  partir do relógio real (mês atual menos N-1 meses até o fim do mês atual), sem hardcode de
  data. Presets 1/3/6/12 meses.
- `src/components/detail-panel.tsx` — `Sheet` lateral (shadcn), abre quando um bairro é
  selecionado no mapa. Busca `/metricas/comercio?territorio_id=...` (com o `categoria_id` e
  intervalo de data correntes) e desenha a série mensal em Recharts: duas linhas categóricas
  fixas da seção 4.2 (aberturas azul `#2a78d6`, desaparecimentos laranja `#eb6834`), 2px,
  `strokeLinecap="round"`, marcadores `r=4` (8px de diâmetro), legenda sempre presente,
  tooltip com cursor de crosshair. Estados carregando/erro/vazio tratados (bairro sem nenhum
  evento no período mostra um alerta neutro, não gráfico em branco).
- `dashboard.tsx` reescrito para separar dado "estável" (território + categoria, um único
  fetch) de dado "dependente de filtro" (métrica do mapa, refeita a cada mudança de categoria
  ou período - efeito próprio, sem recarregar geometria). Filtros agora ligados de verdade:
  combobox de categoria (`categoria_id` ou "todas"), presets de período, e um **intervalo
  customizado** via `Popover` + `Calendar` (`mode="range"`, shadcn) - o requisito da seção 4.2
  que não tinha entrado em nenhum checkpoint anterior. Clique num bairro no mapa
  (`onSelecionarTerritorio`, o gancho deixado no checkpoint 7b) resolve o nome do bairro contra
  o GeoJSON já carregado e abre o painel de detalhe com os mesmos filtros de categoria/período
  aplicados ao mapa.
- **Atrito de stack encontrado e resolvido**: os componentes `shadcn/ui` deste projeto usam
  `@base-ui/react` (não Radix, que é o que a maior parte do conhecimento geral sobre shadcn
  assume) - `Select.onValueChange` recebe `string | null` (não só `string`), e composição de
  trigger customizado não usa `asChild`/`Slot` do Radix, usa a prop `render` do Base UI (aqui,
  resolvido de forma mais simples aplicando `buttonVariants(...)` como `className` direto no
  `PopoverTrigger`, sem precisar de um `<Button>` filho). Nenhuma decisão de arquitetura
  mudou por causa disso - é só a API real da lib instalada, diferente da assumida.
- **Novo lint bloqueante encontrado**: a versão do `eslint-plugin-react-hooks` deste projeto
  (React Compiler / Next 16) tem a regra `react-hooks/set-state-in-effect`, que reclama do
  padrão comum "seta `status: carregando` no início do efeito, antes do fetch". É o padrão
  correto para mostrar um indicador de carregamento num refetch disparado por mudança de
  filtro - não há como derivar isso do render. Silenciado com
  `eslint-disable-next-line` pontual nos dois lugares (`dashboard.tsx`, `detail-panel.tsx`),
  com comentário explicando o motivo.
- **Rodado localmente**: `npm run build` compila e type-checa sem erro; `npm run lint` sem
  avisos; confirmado via `curl` que `/metricas/comercio` responde certo para os três casos que
  o frontend agora dispara (agregado por bairro com filtro de categoria/data, série por bairro
  com os mesmos filtros, e o payload puro do checkpoint 6a sem filtro nenhum). **Verificação
  visual novamente não foi feita por mim** - mesma limitação dos checkpoints 7a/7b. Pedir para
  o dono abrir `http://localhost:3000` e confirmar: trocar categoria/período recolore o mapa,
  clicar num bairro abre o painel com o gráfico de duas linhas (azul/laranja) com legenda, e o
  intervalo personalizado funciona.

**Bug encontrado na checagem visual do checkpoint 7c, corrigido**: o mapa não renderizava nada
- filtros e legenda apareciam (React), mas a área do MapLibre ficava em branco. Causa: o
  estilo base do checkpoint 7b (`https://demotiles.maplibre.org/style.json`, ver nota daquele
  checkpoint) não estava acessível a partir do navegador real do dono (rede/proxy/firewall -
  respondia 200 do shell deste ambiente, mas não do navegador), e não havia `map.on("error",
  ...)` nenhum - a falha em buscar o estilo nunca dispara `"load"`, então fonte/camadas nunca
  são adicionadas, e nada aparece, sem nenhum aviso. Corrigido em duas frentes:
  `choropleth-map.tsx` agora usa um estilo MapLibre **em branco, embutido no código** (sem
  nenhuma fonte externa - só uma camada `background` com a cor de fundo do produto), eliminando
  de vez essa dependência de rede (o coroplético nunca precisou de ruas/rótulos de basemap); e
  um handler de erro (`map.on("error", ...)`) agora mostra um `Alert` visível por cima do mapa
  em vez de falhar calado - mesmo princípio de nunca deixar tela quebrada em silêncio que já
  valia pro resto do produto, só não tinha sido aplicado dentro do próprio MapLibre ainda.
  `npm run build`/`lint` seguem limpos.

### Sessão de 2026-08-12 — dois bugs reais encontrados e corrigidos (mapa + métrica)

Pedido do dono: abrir `localhost:3000` e checar o mapa. A checagem automatizada (Playwright
headless, já que a extensão Claude em Chrome segue indisponível nesta máquina) achou o mapa
**em branco de novo**, apesar do checkpoint 7c acima já ter corrigido um bug de mapa em branco
- causa raiz diferente dessa vez, não o `demotiles.maplibre.org`.

**Bug 1 - altura CSS colapsada.** `apps/web/src/app/layout.tsx` (`<body>`) e o wrapper raiz de
`dashboard.tsx` usavam `min-h-full`/`min-h-screen` em vez de `h-full`/`h-screen`. `min-height`
nunca é tratado como tamanho CSS "definido" (mesmo quando o valor renderizado bate com o
esperado) - toda a cadeia de `flex-1` até o container do MapLibre ficava sem altura resolvível
pra propósito de resolução de porcentagem, e os `<div className="h-full w-full">` do mapa
colapsavam pra 0px, silenciosamente (confirmado isolando o problema com `getComputedStyle`/
`getBoundingClientRect` num elemento sintético injetado na própria árvore da página - até
`height: 100% !important` inline não resolvia contra aquele container). Corrigido trocando os
dois pra `h-full`/`h-screen`.

**Bug 2 - worker do MapLibre nunca carregava.** Corrigida a altura, o mapa aparecia mas sem
nenhum bairro colorido - só o `background`. MapLibre GL JS v6 localiza seu worker de
processamento de GeoJSON via `import.meta.url` do próprio chunk (`new Worker(url, {type:
"module"})`); isso não resolve pra uma URL http(s) real sob o bundler do Next.js/Turbopack -
confirmado interceptando o construtor `Worker` no navegador: a URL passada era `""` (string
vazia), then reproduzido tanto em `next dev` quanto em `next build && next start` (não é
limitação só de dev). Sem o worker, o GeoJSON dos 75 bairros nunca é "tilado" -
`map.isSourceLoaded()` fica `false` pra sempre, `queryRenderedFeatures()` devolve 0, sem
nenhum evento de erro disparado. Corrigido servindo uma cópia estática do worker (e do chunk
`maplibre-gl-shared.mjs` do qual ele importa) em `apps/web/public/` via script `postinstall`
(`apps/web/scripts/copy-maplibre-worker.mjs`, copia de `node_modules/maplibre-gl/dist/` -
gitignored, não é código-fonte do projeto) e apontando `setWorkerUrl("/maplibre-gl-worker.mjs")`
antes de criar o `Map`.

**Achado à parte, motivado por uma auditoria pedida pelo dono** (o mapa mostrava saldo negativo
em todo bairro de Curitiba nos "últimos 12 meses", CENTRO em -191 - suspeita inicial do dono:
`DESAPARECIMENTO` estaria usando `DATA_EXPIRACAO` do alvará como proxy de fechamento em vez de
comparação real de snapshots). Investigação com queries brutas contra o banco real + leitura
literal do código, sem alterar nada até a causa ser confirmada:

- **Hipótese do `DATA_EXPIRACAO` como proxy: descartada.** `grep` mostra esse campo gravado só
  como atributo passivo do JSONB da observação - nenhum `if`/filtro o usa em
  `domain/event/regras.py` nem na orquestração. `DESAPARECIMENTO` é mesmo derivado de
  comparação real de snapshots (confirmado numa amostra manual de 8 entidades do Centro: todas
  têm exatamente 1 observação, datada 2026-07-01, ausente em 2026-08-01).
- **O padrão observado é real, mas o rótulo do filtro era enganoso.** Só existem 2 snapshots
  processados (`2026-07-01`, `2026-08-01`) - todo evento tem `data_evento = 2026-08-01`. O
  preset "últimos 12 meses" capturava tudo porque agosto cai dentro da janela, não porque haja
  atividade distribuída ao longo de um ano. **Corrigido**: novo endpoint `GET
  /metricas/cobertura` (`feature_repository.consultar_cobertura_temporal` - primeiro/último mês
  com evento em `analytics.contagem_eventos`); o dashboard mostra isso sempre, junto ao filtro
  de período ("Dados reais processados: ago/2026 — o período acima é só o filtro...").
- **Achado real e distinto, confirmado**: `analytics/features/contagem_eventos.py`
  (`TIPOS_CONSIDERADOS`) só incluía `PRIMEIRA_OBSERVACAO` e `DESAPARECIMENTO` desde o
  checkpoint 5 - decisão de escopo documentada naquele checkpoint, mas com um efeito colateral
  não percebido até agora: `ABERTURA_CONFIRMADA` (confiança **alta**, abertura genuína
  confirmada por `INICIO_ATIVIDADE`) nunca chegava a `analytics.contagem_eventos`, então o
  campo `aberturas` que a API expõe e o mapa colore somava só `PRIMEIRA_OBSERVACAO` (confiança
  **baixa** - "entidade nunca vista antes, sem prova de quando abriu"). **Corrigido** incluindo
  `ABERTURA_CONFIRMADA` em `TIPOS_CONSIDERADOS` e na agregação SQL de
  `feature_repository.consultar_metricas_comercio` (`aberturas` agora soma os dois tipos;
  `desaparecimentos` não mudou). Confirmado sem dupla-contagem: os dois tipos são mutuamente
  exclusivos por entidade (query `HAVING COUNT(DISTINCT event_type) > 1` devolveu 0 linhas).
  Recomputado `analytics.contagem_eventos` (`python -m analytics.features.run_contagem_eventos`)
  contra o banco real - **efeito concreto**: CENTRO vira saldo **+391** (era -191; aberturas
  798 = 216 `PRIMEIRA_OBSERVACAO` + 582 `ABERTURA_CONFIRMADA`, fechamentos 407 inalterado). O
  mapa inteiro mudou de perfil - a maioria dos bairros hoje tende a neutro/azul.

**Rodado contra o banco/API/frontend reais**: 94 testes passando (2 novos - regressão de
`aberturas` incluindo confiança alta, e o endpoint de cobertura), `npm run build`/`lint`
limpos. Verificado via Playwright headless (screenshot + inspeção do estado real do MapLibre,
não só ausência de erro): mapa renderiza os 75 bairros coloridos, hover mostra popup com
número certo, clique abre o painel de detalhe, filtro de categoria/período recolore o mapa,
CENTRO confirmado em "+391 (aberturas 798, fechamentos 407)" no popup depois da correção.

**Deploy (6b/7d) segue adiado por decisão do dono** — tudo roda local por enquanto (ver nota
acima). **Próximo checkpoint: 7d — deploy do frontend** (Vercel) - também adiado junto com o
6b; quando o dono decidir retomar, os dois andam juntos (a API precisa estar pública antes do
frontend apontar pra ela em produção). Sem próximo checkpoint pendente localmente: os
checkpoints 6a, 7a, 7b e 7c (tudo que dá pra fazer sem sair do localhost) estão completos.

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
- O console do Windows (`cp1252`/similar) exibe texto acentuado gravado no banco como lixo
  (ex.: "CÍVICO" vira "C�VICO") ao rodar `print()` direto no terminal - **é só exibição**, o
  dado em si está correto em UTF-8 (confirmado via `psql`). Não gastar tempo "corrigindo"
  acentuação que aparece quebrada só no console.
- Para explorar o banco visualmente: pgAdmin com host `localhost`, porta `5432`, banco/usuário/
  senha `mercator`/`mercator`/`mercator` (mesmos valores de `.env.example`). Os dados de
  verdade estão nos schemas `canonical`, `events`, `infra` e `analytics` - `public` é só o
  padrão do Postgres/PostGIS.
