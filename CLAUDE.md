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
- `analytics.contagem_inicio_atividade` — **implementado** (checkpoint 8, otimização de
  2026-08-12). Mesmo padrão de `contagem_eventos` (100% derivada, `DELETE` + `INSERT`), mas
  fonte diferente: `INICIO_ATIVIDADE` de `canonical.observacao_entidade.atributos`, não
  `fato_evento_territorial` - dá profundidade real de anos ao indicador de aberturas mesmo com
  poucos snapshots de evento processados (ver checkpoint 8b). `territorio_id` (FK, not null),
  `categoria_id` (FK, nullable), `mes DATE`, `contagem INT`. Índice em `(territorio_id, mes)` -
  é o padrão de leitura real da API. Gerada por
  `python -m analytics.features.run_contagem_inicio_atividade` - precisa rodar de novo sempre
  que um novo snapshot de alvarás for processado (mesma exigência operacional de
  `run_contagem_eventos.py`, ver Notas operacionais).

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

### Checkpoint 8a-8d — Ranking de crescimento e detalhe de bairro: **concluído**

Um número absoluto ("234 aberturas em Batel") não diz se é muito, pouco, ou se está
acelerando - faltavam três comparações: contra o próprio passado (baseline), contra o momento
anterior (tendência), e contra os outros bairros (ranking). Implementado em 4 sub-checkpoints,
cada um parado, testado e revisado antes do próximo.

**8a - cálculo puro** (`src/analytics/features/indicadores.py`, sem I/O): `calcular_baseline`
(média móvel, janela configurável, padrão 24 meses, excluindo o mês corrente da própria
média), `calcular_tendencia` (últimos 3 meses fechados vs. os 3 anteriores, limiar de ±10%
configurável) e `calcular_ranking` (ordena por `variacao_pct` - crescimento relativo, não
volume absoluto, testado explicitamente que um bairro pequeno crescendo aparece à frente de um
grande estável). Histórico insuficiente (`< 3` meses distintos na janela) retorna `None` com
`motivo_indisponivel`, nunca `0` nem erro. Dois motivos de indisponibilidade:
`historico_insuficiente` (poucos meses de dado) e `baseline_zero` (dado suficiente, mas a
média é exatamente zero - divisão indefinida, não "infinita"). 21 testes.

**8b - API** (`GET /ranking/comercio`, `GET /bairros/{territorio_id}/resumo`, `GET
/metricas/comercio` estendido com `baseline`/`variacao_pct`/`tendencia`). Decisão de fonte de
dado: o indicador de aberturas usa uma série derivada de `INICIO_ATIVIDADE` (real por
registro, profundidade de anos mesmo com poucos snapshots), **não** o campo `aberturas`
existente (baseado em evento de detecção, só tem profundidade a partir do par de snapshots já
comparado) - os dois números podem divergir pro mesmo bairro/mês, decisão consciente, não bug.
`saldo` continua vindo do caminho de evento existente e fica `historico_insuficiente`
corretamente (limitação real de dado, 2 snapshots só). Motivo extra descoberto testando contra
dado real: `mes_incompleto` - o mês do rótulo do snapshot mais recente (ex.: "2026-08-01") não
tem cobertura real de `INICIO_ATIVIDADE` ainda (mesmo atraso de um mês do checkpoint 3); sem
esse motivo dedicado, a API mostrava `"-100%"` ao lado de um número real de verdade. 7 testes
de API (seed real de `entidade`/`observacao_entidade` em `conftest.py`).

**8c - ranking no frontend**: nova aba "Ranking de crescimento" (Tabs do shadcn) ao lado do
Mapa, reaproveitando o mesmo filtro de categoria (mesmo componente, mesmo estado). Sparkline de
12 pontos (linha 2px neutra, marcador ≥8px na cor de destaque só no ponto atual) e regra de
cor do delta implementada como função parametrizada (`corDelta(variacaoPct, cimaEBom)`) - não
uma regra fixa "positivo = azul", preparada pra inverter caso um tile isolado de fechamento
apareça algum dia. Paleta reaproveitada exatamente da do mapa (`AZUL_DESTAQUE`/
`VERMELHO_DESTAQUE` em `palette.ts`, nenhuma paleta nova).

**8d - detalhe de bairro expandido**: painel do checkpoint 7c ganhou cabeçalho com posição no
ranking, stat tiles de aberturas (sempre com baseline/variação/tendência) e saldo (estado "em
construção" explícito - *"dado de fechamento em construção — acompanhando mês a mês"* - quando
histórico insuficiente, nunca omitido nem zero), e quebra por categoria em barras horizontais.
Clique no mapa e clique numa linha do ranking levam ao mesmo painel - verificado visualmente
nos dois caminhos.

**Otimização de performance (mesmo dia, pedida pelo dono depois de usar a aba)**: abrir o
ranking ou o painel de detalhe de um bairro levava 4-12s - `/ranking/comercio` e
`/bairros/{id}/resumo` recomputavam ao vivo uma query cara (`DISTINCT ON` sobre ~515 mil
observações) a cada request. Corrigido materializando `analytics.contagem_inicio_atividade`
(mesmo padrão de `analytics.contagem_eventos` - ver Schema acima), gerada por
`run_contagem_inicio_atividade.py`. **Resultado medido**: ranking com categoria nunca vista
3,4s → 0,3s; abrir o painel de detalhe pela primeira vez 12s → 0,3s; aba Ranking no navegador
(clique → lista renderizada) 323ms. Dado idêntico ao da query ao vivo, conferido bairro a
bairro.

**Rodado contra o banco/API/frontend reais**: CENTRO lidera o ranking com +89% (582 aberturas
vs. baseline 307, "acelerando"); bairros pequenos como Ganchinho aparecem bem posicionados por
crescimento relativo mesmo com volume baixo (5 aberturas) - o comportamento que o ranking por
volume absoluto nunca mostraria. 122 testes passando, `npm run build`/`lint`/`tsc` limpos.

### Dois pilotos de geocodificação (2026-08-12, antes do checkpoint 9)

A arquitetura original não tinha geolocalização em nível de ponto - não-objetivo deliberado,
desnecessário pro Radar de Comércio em nível de bairro. Dois pilotos isolados (schema
`experimental.*`, nunca tocando `canonical.*`) mediram se valia reabrir esse não-objetivo,
usando os 1.655 endereços do bairro Lindóia (não Centro, por suspeita não confirmada de
fallback de bairro contaminando o volume de lá):

- **Piloto 1 (Nominatim público)**: 86,9% sucesso, 9,2% ambíguo, 3,8% falha. Amostra manual
  (todos os 1.439 sucessos, não só 15-20): 99,2% caem dentro do polígono do bairro esperado.
  Tempo medido: 1,36s/endereço (1s de rate limit + latência real) → extrapolado pra base
  inteira (515.118 entidades): **~8,1 dias corridos** - inviável como operação única contra o
  serviço público.
- **Piloto 2 (geocodebr/CNEFE-IBGE, offline via subprocesso R)**: resolve **100%** dos 1.655
  endereços (incluindo os 216 que o Nominatim não resolveu bem), em **2,75s** - ~700x mais
  rápido. Mas só 91,7% caem dentro do polígono esperado (vs. 99,2% do Nominatim), com 2 erros
  grosseiros de vários km (CEP do registro de origem não batendo com o bairro declarado -
  achado de qualidade de dado, não bug do pacote). Bug real encontrado: `resultado_completo=TRUE`
  quebra no geocodebr 0.6.4 (erro de binder do duckdb, "coluna empate não existe") independente
  de `resolver_empates` - por isso a coluna nativa de ambiguidade (`empate`) não pôde ser usada;
  status ambíguo é aproximado pelo prefixo de `tipo_resultado` (d=determinístico/p=probabilístico).
  Setup: CNEFE ~1,46GB, baixado em 21s (custo único).
- **Comparação cruzada**: nenhum caso onde os dois falham (união cobre 100% da amostra); nos 66
  casos de forte divergência (>500m) entre os dois serviços, Nominatim caiu dentro do polígono
  esperado 38x contra 3x do geocodebr - sinal de que Nominatim é mais confiável quando os dois
  discordam.

**Conclusão que motivou o checkpoint 9**: nenhum serviço sozinho é confiável e viável ao mesmo
tempo - geocodebr cobre rápido (mas erra mais), Nominatim corrige onde geocodebr é fraco (mas é
lento demais pra rodar sozinho na base inteira). Tabelas dos pilotos (`experimental.geocodificacao_piloto`,
`experimental.geocodificacao_piloto_geocodebr`) mantidas como registro histórico da decisão, não
apagadas.

### Checkpoint 9a-9e — Geolocalização de entidade e busca por raio: **concluído (9a-9b-9d-9e); 9c parcial por decisão pendente**

Implementa a combinação geocodebr+Nominatim dos dois pilotos como pipeline de produção -
reabre deliberadamente o não-objetivo original de geolocalização em nível de ponto.

**9a - modelo e regra de reconciliação**: `canonical.geolocalizacao_entidade` - uma linha por
`entidade_id` (não por observação), `GEOGRAPHY(Point,4326)` + índice GIST (criado
automaticamente pelo `geoalchemy2` logo após o `CREATE TABLE` - um `op.create_index` explícito
na migração colide com isso, `DuplicateTable`; mesmo padrão de `dim_territorio.geometria`,
sem índice explícito na migração dele também). `src/domain/location/` (regra pura, sem I/O):
- `avaliar_geocodebr(precisao)`: só `precisao == "numero"` (nível de número exato) dispensa a
  segunda passagem → `alta`. Qualquer outra coisa (`numero_aproximado`, `logradouro`, `cep`,
  `localidade`, `municipio`, ou `None`) → `baixa` provisória, enfileirada. Limiar mais
  conservador que uma leitura literal do prompt teria sugerido: o Piloto 2 mostrou que
  `numero_aproximado` também contribui pra pontos fora do bairro esperado, não só
  logradouro/CEP - registrado aqui por ser a interpretação de "nível de número exato" adotada,
  ajustável se a distribuição real pedir.
- `reconciliar(ponto_geocodebr, ponto_nominatim)`: concordância ≤150m → `alta` (usa ponto do
  Nominatim); 150m-1km → `media`; >1km → `baixa`, mas com ponto (não `None`) - limiares
  calibrados pelo padrão observado no Piloto 2 (mediana de 13m quando concordam; Nominatim
  ganha 38-3 nos casos de forte divergência). Dois ramos extras, não explícitos no prompt de
  referência, necessários porque a fila real mistura "geocodebr impreciso" com "geocodebr não
  achou nada": geocodebr sem nada + Nominatim resolve → `media` (só uma fonte, sem segunda
  opinião pra confirmar, não vira `alta`); geocodebr impreciso + Nominatim não resolve nem
  contesta → mantém `baixa` com o ponto do geocodebr (não regride pra `None`). 18 testes
  automatizados cobrindo os quatro ramos do prompt de referência (o quarto, "os dois
  resolvem", com um teste por limiar de distância) mais os dois ramos extras e os limiares de
  fronteira.

**9b - pipeline em lote, Etapa 1 (geocodebr)**: `src/pipelines/geocoding/etapa1_geocodebr.py` +
`geocode_batch.R` (chamado via subprocesso, `resultado_completo=FALSE`/`resolver_empates=FALSE`
- mesma configuração que contorna o bug do Piloto 2). Retomável: lotes de 5000, commitados antes
do próximo começar; a query de origem (`entidades_comercio_pendentes`, `NOT EXISTS` em
`geolocalizacao_entidade`) já exclui quem tem linha, então rodar de novo só pega o resto - sem
parâmetro extra. **Falha real encontrada rodando contra a base inteira**: o subprocesso R
crashou uma vez depois de ~44 lotes bem-sucedidos ("could not start R, exited with non-zero
status, has crashed or was killed"), sem sinal de exaustão de disco/memória - corrigido com
3 tentativas por lote e um intervalo curto entre elas; o pipeline retomou de onde parou (215.020
já gravadas) sem perder trabalho. **Rodado contra a base inteira**: 515.118 entidades - **73,2%
(376.926) `alta`** direto (número exato, sem segunda passagem), **26,8% (138.192) `baixa`**
provisória na fila.

**9c - pipeline em lote, Etapa 2 (Nominatim, resíduo)**: `src/pipelines/geocoding/etapa2_nominatim.py`.
Antes de rodar, estima o tempo a 1 req/s (1,36s/req observado, ver Piloto 1) e para pra reportar
se ultrapassar o limiar configurado (`LIMIAR_HORAS_PARA_PARAR = 7.0`). **Rodado contra a fila
real**: 138.192 entidades pendentes → estimativa de **52,2h** - muito acima do limiar. O
pipeline parou e reportou, exatamente como desenhado, recomendando avaliar uma instância própria
de Nominatim (só Brasil) em vez de rodar dias contra o serviço público. **Decisão de infra
pendente, não resolvida nesta sessão** - rodar o resíduo (`--forcar`), hospedar Nominatim
próprio, ou aceitar cobertura parcial (73,2% `alta` já é a maioria da base) é escolha do dono do
projeto. Enquanto isso não for decidido, a distribuição de confiança da base fica travada em
alta/baixa (sem nenhuma `media` ainda - essa categoria só existe depois da segunda passagem).

**9d - endpoint de busca por raio**: `GET /busca-raio` (`endereco`, `raio_m`, `categoria_id?`).
Geocodifica `endereco` com Nominatim direto (uma chamada ocasional, não geocodebr - subprocesso R
por requisição teria latência alta demais pra uso interativo); 404 se não encontrar, 422 se
ambíguo (nunca adivinha qual candidato usar). `geolocalizacao_repository.buscar_no_raio` usa
`ST_DWithin` contra `geolocalizacao_entidade`, unido com a observação mais recente de cada
entidade (nunca conta a mesma entidade duas vezes por causa de histórico). Não filtra por sinal
de fechamento/`DESAPARECIMENTO` (está sob revisão separada, de propósito). Resposta separa
`estabelecimentos` (confianca `alta`/`media`) de `excluidos_baixa_confianca` (contagem, visível,
não escondida) - o filtro de categoria se aplica aos dois igualmente, pra não mostrar "+N pouco
confiáveis" de uma categoria diferente da buscada. **Testado com endereços reais** contra a base
inteira geocodificada: `AV. PRESIDENTE WENCESLAU BRAZ, 1893` em 1km → 3.767 estabelecimentos;
filtrado por `bares_restaurantes` em 300m → 4 principais + 3 excluídos por baixa confiança,
nomes/categorias/distâncias corretos. 7 testes automatizados novos (`tests/api/test_busca_raio.py`,
Nominatim mockado).

**9e - tela de busca por raio**: nova aba "Busca por raio" (reaproveita o combobox de categoria
já existente no cabeçalho). Campo de endereço + chips de raio (250m/500m/1km/2km) +
`RadiusMap` (círculo via `@turf/circle`, marcadores azul-destaque - cor categórica existente,
não uma nova) + stat tile simples (sem baseline/tendência, de propósito - é medida pontual no
espaço). Aviso de `excluidos_baixa_confianca` discreto, separado da contagem principal, só
quando >0. Estados carregando/erro (404/422 com mensagens distintas)/vazio tratados
explicitamente. **Testado ponta a ponta no navegador contra a API/banco reais**: busca com
resultado (805 estabelecimentos em 500m, mapa com círculo+marcadores renderizando), filtro de
categoria (15→4 conforme o filtro), raio pequeno (250m, 4 resultados), endereço não encontrado
(404, alerta correto), endereço ambíguo (422, alerta correto), e resultado vazio (0
estabelecimentos de uma categoria rara num raio pequeno, alerta correto). **Achado à parte, não
corrigido por estar fora do escopo deste checkpoint**: o combobox de categoria (já existente
desde o checkpoint 7c, não tocado aqui) mostra o `categoria_id` bruto (ex.: `bares_restaurantes`)
em vez do nome legível no texto do trigger, tanto na aba Mapa quanto na de busca por raio -
bug pré-existente, confirmado reproduzindo na aba Mapa sem nenhuma mudança deste checkpoint.

**Rodado contra o banco/API/frontend reais**: 156 testes passando (122 do checkpoint 8 + 34
novos: 18 de `domain/location`, 9 de infra de geocodificação, 7 de `/busca-raio`).
`npm run build`/`lint`/`tsc` limpos.

### Checkpoint 9f-9g — Mapa-base real e lista de resultados na busca por raio: **concluído**

**9f - mapa-base real**: `apps/web/src/lib/map-style.ts` centraliza a URL do style, usada tanto
por `choropleth-map.tsx` (mapa principal) quanto por `radius-map.tsx` (busca por raio) - nunca
duplicada. Provedor usado: **OpenFreeMap** (`https://tiles.openfreemap.org/styles/positron`),
não MapTiler (a recomendação original do prompt de referência) - criar conta/API key não é algo
que a Claude possa fazer sozinha (ação proibida por política, mesma categoria de "criar contas"
documentada nas regras de segurança da sessão). OpenFreeMap foi escolhido por não precisar de
conta/chave e ser explicitamente declarado apropriado pra produção contínua (ao contrário dos
tiles brutos do OSM, que têm a mesma restrição de uso pesado já vista com o Nominatim) -
confirmado consultando a documentação do serviço antes de adotar, não presumido. Estilo
"positron": claro/neutro, POIs removidos por design, pra não competir com o coroplético/
marcadores. Troca de provedor (ex.: pra MapTiler depois) documentada como comentário no próprio
`map-style.ts` - um único lugar pra mudar. Anel de 2px na cor de superfície (`#ffffff`, o
mesmo `--background` do produto) aplicado tanto na borda dos polígonos do coroplético quanto no
contorno dos marcadores da busca por raio - contra ruas/rótulos reais agora visíveis por baixo,
o espaçamento (não uma borda escura) é o que mantém o dado legível. Verificado visualmente nas
duas telas: ruas e nomes de bairro/cidade aparecem, coroplético e marcadores continuam sendo o
elemento mais chamativo.

**9g - lista de resultados**: `GET /busca-raio` ganhou o campo `endereco` (composto via
`concat_ws` no SQL - pula partes ausentes sem deixar separador solto, ex. sem número informado
não vira "R. X, "). `nome` já priorizava `NOME_FANTASIA` sobre `NOME_EMPRESARIAL` desde o
checkpoint 9d (`COALESCE` no SQL) - não precisou mudar. Não tocou a lógica de filtragem por
confiança nem `canonical.geolocalizacao_entidade`, como pedido. `radius-results-list.tsx`:
lista lateral (`lg:flex-row`) ou abaixo (empilhado em telas estreitas) do mapa, ordenada por
distância (a mesma ordem que a API já devolve), nome + categoria (resolvida no frontend a
partir da lista de categorias já carregada pelo Dashboard, sem endpoint novo) + endereço +
distância no mesmo formato do popup do mapa (`"334m"`). Paginada em lotes de 50 com "carregar
mais" - resultado grande (2km, sem filtro de categoria) chega a *milhares* de estabelecimentos
e a lista nunca renderiza mais que 50 linhas de uma vez, verificado (`50` botões no DOM antes de
clicar "carregar mais"). Sincronização hover/clique bidirecional entre lista e mapa: hover numa
linha ou num marcador atualiza o mesmo estado `hoveredId` no componente pai
(`radius-search-panel.tsx`), que os dois lados leem - `radius-map.tsx` usa uma expressão de
estilo (`case` no `circle-radius`/`circle-stroke-width`) pra destacar o marcador correspondente,
em vez de `feature-state` (mais simples de manter sincronizada com um id vindo de fora do mapa).
Clicar numa linha centraliza o mapa (`flyTo`) no estabelecimento - um contador (`selectedNonce`)
força o `flyTo` mesmo se a mesma linha for clicada duas vezes seguidas. **Verificação da
sincronização**: confirmada via inspeção direta do fiber do React (não só visual - marcadores de
~6-10px são pequenos demais pra confirmar destaque com confiança só por screenshot) - o handler
`onMouseEnter` da lista dispara, o estado `hoveredId` propaga e a classe de destaque (`bg-muted`)
é aplicada na linha certa; o mesmo estado é a prop que `radius-map.tsx` consome, então o
destaque no mapa segue a mesma atualização.

**Achado reportado, não resolvido** (conforme pedido - "não implemente clustering... se ainda
estiver poluído, reporte como achado, não resolva sem perguntar"): com raio de 2km e "todas as
categorias" (ex.: 16.759 estabelecimentos num teste real), o mapa fica visualmente poluído - um
tapete denso de marcadores sobrepostos, mesmo com o mapa-base real e o anel de 2px ajudando a
distinguir cada ponto individualmente. O mapa-base novo por si só não resolve isso pra raios
grandes sem filtro de categoria; a lista lateral (nova, deste checkpoint) já dá uma forma
utilizável de explorar esse volume sem depender só do mapa, mas clustering de marcador (ou outra
técnica de agregação visual) é uma melhoria pendente, fora do escopo deste checkpoint - decisão
de quando/como resolver fica com o dono do projeto.

**Rodado contra o banco/API/frontend reais**: 157 testes passando (156 do checkpoint 9a-9e + 1
novo, `test_busca_raio_estabelecimento_inclui_endereco_de_exibicao`). `npm run build`/`lint`
limpos. Testado no navegador contra a API/banco reais: mapa principal e busca por raio com ruas/
nomes visíveis e coroplético/marcadores legíveis; busca por raio em 500m e 2km, lista ordenada
por distância, paginação em 50 confirmada com 805 e 16.759 resultados.

## Fase de inteligência territorial (checkpoints 11a-11e)

Depois do checkpoint 10 (identidade editorial), o dono pediu uma fase maior: transformar o
protótipo de "ferramenta de consulta de dado" em produto de inteligência territorial
demonstrável, estruturado em 4 experiências (Radar, Perfil do Território, Investigação por
Endereço, Comparação), com uma restrição central do prompt de referência dessa fase: **nenhuma
métrica proprietária/score composto** - tudo precisa ser fórmula simples, documentada e
reproduzível ("se um usuário perguntar 'como vocês chegaram nesse número?', o produto precisa
responder de forma objetiva"). Planejada em 5 checkpoints (11a-11e); decisão tomada com o dono
antes de começar: ruas/corredores dentro do perfil de bairro ficam fora de escopo (endereço
bruto do alvará não é normalizado, uma quebra por rua duplicaria corredores por variação de
grafia) - registrado como limitação de dado na Metodologia, não implementado.

### Checkpoint 11a - Credibilidade: metodologia + qualidade de dados: **concluído**

Fundação para o resto da fase - sem isso, nenhum tooltip de metodologia teria o que
referenciar.

- `GET /qualidade-dados` novo (`apps/api/routers/metodologia.py`) - reaproveita
  `geolocalizacao_repository.contar_por_confianca` (já existia, não exposto via API) +
  `feature_repository.consultar_cobertura_temporal` (já existia). Duas peças novas, pequenas:
  `geolocalizacao_repository.contar_entidades_comercio` (total de entidades tipo `comercio`,
  denominador do percentual) e `pipeline_run_repository.ultima_execucao_com_sucesso` (novo
  arquivo, primeiro repositório dedicado a `infra.pipeline_run` - só um `MAX(finalizado_em)`
  filtrado por `status='sucesso'`). Resposta: contagens cruas por confiança de geolocalização,
  `pct_localizacao_valida` (alta+media / total - mesmo corte de confiança que
  `CONFIANCAS_NA_CONTAGEM_PRINCIPAL` já usa em `busca_raio.py`), cobertura temporal, última
  atualização. Nenhum número aqui é ponderado ou combinado - são fatos diretos, seguindo a
  restrição do prompt.
- `apps/web/src/app/metodologia/page.tsx` - página nova (rota estática), com uma seção por
  fórmula usada em qualquer tela do produto (baseline, variação %, tendência, saldo,
  participação, densidade, turnover - os dois últimos definidos aqui mesmo sem uso ainda,
  fórmula documentada antes de a métrica aparecer em tela), metodologia de geocodificação
  (resumo do que já estava documentado no checkpoint 9), e limitações conhecidas (cobertura de
  2 snapshots, ~6% de bairro não resolvido, ~34% de CNAE não normalizável, ruas/corredores fora
  de escopo).
- `MethodologyTooltip` (`components/methodology-tooltip.tsx`) - componente novo do design
  system pedido pelo prompt: ícone `Info` (lucide-react) com um `Popover` (shadcn) mostrando a
  fórmula e um link pra âncora certa em `/metodologia`. `StatTile` ganhou um prop opcional
  `metodologia` que renderiza esse tooltip ao lado do rótulo, sem mudar layout existente -
  ligado nos dois tiles já em uso (`aberturas`/`saldo` do painel de detalhe de bairro).
- `DataQuality` (`components/data-quality.tsx`) - componente novo do design system, fatos crus
  de `/qualidade-dados` sem nota. `DataQualitySection` (client component separado) busca o
  dado; a página `/metodologia` em si continua um server component estático.
- Link "Metodologia" adicionado ao cabeçalho do Radar (`dashboard.tsx`), ao lado das Tabs.

**Rodado contra o banco/API/frontend reais**: `GET /qualidade-dados` real devolveu 515.118
estabelecimentos, 73,2% com localização válida (confirma o resultado do checkpoint 9b: 73,2%
`alta` direto na primeira passagem, sem nenhuma `media` ainda porque a segunda passagem via
Nominatim segue pausada por decisão pendente), última atualização 11/08/2026. Testado no
navegador (via workaround de IP de LAN - ver Notas operacionais): `/metodologia` renderiza
todas as seções com o dado real; tooltip de metodologia no painel de detalhe de bairro abre
com a fórmula certa e o link para a âncora. 2 testes novos (`tests/api/test_metodologia.py`).
`npm run build`/`lint`/`tsc` limpos. Total do projeto: **162 testes Python passando**.

### Checkpoint 11b - Radar: crescimento/retração + ranking por categoria + sinais: **concluído**

- `calcular_ranking` (`indicadores.py`) ganhou um parâmetro `ordem: "desc"|"asc"` (default
  `"desc"`, comportamento anterior intocado) - inverte o sinal da chave de ordenação em vez de
  duplicar a função. "Maiores crescimentos" e "maiores retrações" (seção "RADAR" do prompt de
  referência: nunca misturar as duas numa lista só) são a mesma mecânica, duas chamadas.
- `series_aberturas_por_categoria` (`indicador_repository.py`, novo) - mesmo padrão de
  `series_aberturas_todos_bairros`, agrupado por `categoria_id` em vez de `territorio_id`
  (cidade inteira por padrão, ou um bairro via `territorio_id` opcional; `categoria_id IS NULL`
  excluído - não dá pra rankear "sem categoria"). `montar_ranking_categorias`
  (`servico_indicadores.py`, novo) reaproveita `calcular_baseline`/`calcular_tendencia`/
  `calcular_ranking` **como estão** - o campo `territorio_id` de `ItemComBaseline`/`ItemRanking`
  é só uma chave de agrupamento opaca, aqui alimentada com `categoria_id` deliberadamente (não
  duplica as três funções puras só por causa do nome do campo).
- `GET /ranking/comercio` ganhou `ordem` (query param); `GET /ranking/categorias` novo, mesma
  forma de resposta sem o campo `serie` (a API de categoria não tem sparkline).
- Sinais: `detectar_saldo_negativo_consecutivo` (`indicadores.py`, pura) - critério fixo e
  documentado (4 meses fechados consecutivos com saldo < 0), não um score. `GET /sinais` novo,
  varre `analytics.contagem_eventos` de todos os bairros de uma vez
  (`consultar_saldo_mensal_todos_bairros`, novo em `feature_repository.py`). **Hoje a base só
  tem 1-2 meses reais de evento processado** - o critério nunca encontra ninguém elegível ainda;
  a API comunica isso (`motivo_indisponivel`/lista vazia com explicação), não esconde atrás de
  "nenhum sinal" sem contexto. Vai passar a popular sozinho conforme mais snapshots forem
  processados, sem mudança de código.
- Frontend: `RadarRankingPanel` (novo) - dois seletores independentes (escopo: Bairros/
  Categorias; ordem: Maiores crescimentos/Maiores retrações), nunca uma métrica só combinando
  os dois eixos. `CategoryRankingList` (novo, mesmo padrão visual de `RankingList`, sem
  sparkline) e `SinaisPanel` (novo) completam a aba "Ranking de crescimento". Selecionar uma
  categoria no ranking aplica ela como filtro global (mesmo combobox do cabeçalho) - efeito
  visível ao trocar pra aba Mapa. `mancheteRanking`/nova `mancheteRankingCategorias` (`lib/
  manchete.ts`) ganharam o parâmetro `ordem` pra frasear crescimento vs. retração corretamente.
- **Bug real encontrado na checagem visual, não no código**: depois de editar os arquivos do
  backend, o processo `uvicorn` que já estava rodando (iniciado no checkpoint 11a, sem
  `--reload`) continuou servindo o código antigo - `ordem=asc` no filtro do navegador mostrava a
  mesma lista de `ordem=desc`. Sintoma confirmado com `curl` direto (resposta idêntica pros dois
  valores de `ordem`) antes de suspeitar do processo, não do código - `calcular_ranking` já
  tinha 2 testes passando pra `ordem="asc"`. Corrigido matando os processos `uvicorn` órfãos
  (havia 4 escutando, remanescentes de sessões anteriores - mesmo padrão de instabilidade de
  `--reload` já registrado nas Notas operacionais, mas dessa vez sem `--reload` nenhum) e
  subindo um processo novo. Reforça a nota operacional existente: reiniciar o `uvicorn`
  manualmente depois de qualquer mudança no backend, não assumir que está atualizado.
- **Rodado contra o banco/API/frontend reais**: `/ranking/categorias?ordem=asc` real -
  "Associações e organizações religiosas" lidera a retração (-100%, categoria com poucos
  registros, mesmo padrão de ruído de baixo volume documentado no piso mínimo);
  `/ranking/comercio?ordem=asc` - ATUBA lidera com -95% (1 abertura vs. baseline ~20). Testado
  no navegador: alternar Bairros/Categorias e Crescimento/Retração recalcula a lista e a
  manchete corretamente nas 4 combinações; painel de sinais mostra o critério e a mensagem
  correta de indisponibilidade. 9 testes novos (6 em `test_indicadores.py`, 3 em
  `test_ranking_categorias_e_sinais.py`). `npm run build`/`lint`/`tsc` limpos. Total do
  projeto: **171 testes Python passando**.

### Checkpoint 11c - Comparação de territórios: **concluído**

Sem lógica de negócio nova - reaproveita `/bairros/{id}/resumo` inteiro, chamado N vezes no
backend em vez de N chamadas sequenciais do frontend.

- `apps/api/routers/bairros.py`: o corpo de `bairro_resumo` foi fatorado em
  `_montar_resumo_bairro` (mesma assinatura, devolve `None` em vez de levantar 404 - quem chama
  decide o que fazer com um id inválido). `GET /bairros/comparar?ids=a,b,c,d` novo - valida
  2-4 ids (422 fora da faixa), 404 se algum território não existir (lista todos os inválidos
  na mensagem, não só o primeiro), monta a lista chamando a função fatorada em loop.
  `ComparacaoOut` (schema novo) = `{ itens: [BairroResumoOut, ...] }`, mesmo formato do
  endpoint individual - conferido em teste que o item de `/bairros/comparar` é **byte a byte
  igual** ao de `/bairros/{id}/resumo` pro mesmo bairro.
- Frontend: `TerritorioMultiSelect` (novo) - combobox pesquisável (`Command`/`Popover`,
  primeiro uso desses componentes no projeto) + chips removíveis, máximo 4. `ComparisonTable`
  (novo, componente do design system pedido pelo prompt) - linhas = métrica, colunas = bairro,
  **nenhuma nota agregada** decidindo qual bairro é "melhor" (restrição explícita da seção
  "COMPARAÇÃO" do prompt de referência). `apps/web/src/app/comparacao/page.tsx` (rota nova) -
  seletor de bairros + filtro de categoria/período (presets apenas, sem intervalo
  personalizado - simplificação deliberada, não esquecimento) + tabela + evolução temporal +
  composição por categoria.
- **Decisão de forma pro gráfico de evolução temporal, via skill `dataviz`**: a paleta
  categórica de 8 cores do skill não tem nenhuma ordenação de 4 cores que passe a checagem
  all-pairs (`validate_palette.js --pairs all`) sem reservar azul/vermelho, que já carregam
  outro significado neste produto (saldo positivo/negativo no mapa e nos stat tiles) - usar
  essas cores pra identidade de bairro colidiria semanticamente. Em vez de forçar uma 4ª cor
  categórica arriscada, a evolução temporal virou **small multiples** (um mini-gráfico por
  bairro, grade 2 colunas) reaproveitando exatamente o par aberturas(azul)/desaparecimentos
  (laranja) já usado em `detail-panel.tsx` - elimina o problema de cor por completo, mesmo
  significado em toda tela do produto. `SerieTemporalChart` (novo,
  `components/serie-temporal-chart.tsx`) foi extraído do gráfico inline de `detail-panel.tsx`
  pra ser reaproveitado nos dois lugares sem duplicar configuração - `detail-panel.tsx`
  também foi atualizado pra usá-lo (comportamento idêntico, só a duplicação removida).
- **Bug real encontrado na checagem visual**: o combobox de categoria da página nova mostrava
  "todas" (o `categoria_id` interno usado como sentinela) em vez de "Todas as categorias" - a
  função de formatação tratava qualquer valor truthy como um id de categoria de verdade, sem
  checar o caso sentinela primeiro (mesma classe de bug do achado já registrado no checkpoint
  9e, mas dessa vez pego antes de virar dívida). Corrigido checando `valor === TODAS_CATEGORIAS`
  antes de consultar a lista de categorias.
- **Reforço da nota operacional do checkpoint 11b**: de novo o `uvicorn` precisou ser
  reiniciado manualmente depois da mudança de backend (`bairros.py` fatorado + endpoint novo) -
  virou hábito checar isso a cada checkpoint desta fase antes da verificação visual, não só
  quando algo parece errado.
- **Rodado contra o banco/API/frontend reais**: testado no navegador com CENTRO + BATEL -
  tabela mostra aberturas/saldo/posição/categoria principal lado a lado, saldo em "dado em
  construção" pros dois (mesma limitação real de histórico curto documentada em checkpoints
  anteriores), os dois mini-gráficos e as duas quebras de categoria renderizam corretamente.
  4 testes novos (`tests/api/test_bairros_comparar.py`). `npm run build`/`lint`/`tsc` limpos.
  Total do projeto: **175 testes Python passando**.

### Checkpoint 11d - Investigação por endereço evoluída: **concluído**

Maior pedaço de trabalho genuinamente novo da fase - `/busca-raio` só devolvia um censo de
estabelecimentos ativos, sem abertura/fechamento/tendência nenhuma.

- `geolocalizacao_repository.eventos_no_raio` (novo) - junta `events.fato_evento_territorial`
  (tem `entidade_id`) com `canonical.geolocalizacao_entidade` (tem `ponto`) via `entidade_id`,
  mesmo `ST_DWithin`/corte de confiança (alta/média) de `buscar_no_raio`. Tabela de eventos é
  pequena (milhares de linhas, não ~515 mil) - sem custo de performance filtrar em Python
  depois, ao contrário de uma busca contra `observacao_entidade`.
- **Densidade não depende de geometria de bairro nenhuma** - decisão de escopo do checkpoint:
  a área do círculo de busca é conhecida analiticamente (`π × raio²`), então
  `densidade_km2 = estabelecimentos_ativos / área_do_círculo`. Evita ter que calcular/armazenar
  área de bairro só para isso.
- Turnover = `(aberturas + fechamentos) / estoque`, onde estoque é o `total` que
  `buscar_no_raio` já devolve (mesma definição documentada em `/metodologia`: "estabelecimentos
  com alvará identificado no snapshot mais recente"). `None` quando não há nenhum
  estabelecimento no raio (estoque=0, mesma lógica de `baseline_zero` em `indicadores.py` - não
  é "infinito").
- Comparação com o bairro: resolve o `territorio_id` majoritário entre os estabelecimentos do
  raio e reaproveita `indicador_aberturas_bairro` (já existente, checkpoint 8b) pra mostrar a
  média histórica desse bairro ao lado do número do raio - dois fatos com o mesmo rótulo, nunca
  um score comparando os dois.
- `GET /busca-raio` estendido: `densidade_km2`, `aberturas`, `fechamentos`, `saldo`, `turnover`,
  `quebra_categoria` (top 5, mesmo formato de `quebra_categoria_bairro`), `serie_temporal`
  (mensal, sem baseline/tendência - histórico real curto demais pra isso, mesma limitação
  documentada em toda a fase), `comparacao_bairro` (`None` quando nenhum estabelecimento do raio
  tem bairro resolvido).
- Frontend: `radius-search-panel.tsx` ganhou 5 `FatoTile` (componente local novo, mais simples
  que `StatTile` - esses números não têm baseline/tendência) com `MethodologyTooltip`,
  `QuebraCategoriaBars` e `SerieTemporalChart` (o mesmo extraído no checkpoint 11c)
  reaproveitados sem mudança.
- **Achado de forma corrigido antes de finalizar**: a primeira versão exibia turnover com
  `formatarDeltaPct` (o formatador de variação percentual, que força um sinal `+`/`-`) - errado
  porque turnover é uma taxa, não uma comparação com baseline nenhum; o `+1%` sugeria uma
  "melhora" que não existe no conceito. Corrigido com `formatarTaxaPct` (novo, sem sinal
  forçado) em `lib/indicadores.ts`.
- **Rodado contra o banco/API/frontend reais**: endereço "AV. PRESIDENTE WENCESLAU BRAZ, 1893"
  (mesmo endereço testado no checkpoint 9d) - 1km: 3.767 estabelecimentos (bate com o número já
  registrado), densidade 1.199,1/km², 8 aberturas, 25 fechamentos, saldo -17, turnover 1%,
  comparação "No bairro GUAÍRA: média histórica de 12 aberturas/mês". 2km: 16.759
  estabelecimentos (bate com o checkpoint 9g), densidade 1.333,6/km². Tooltips de metodologia
  visíveis em cada tile. 5 testes novos (`tests/api/test_busca_raio.py`) cobrindo densidade,
  ausência de evento, turnover `None` sem estabelecimento no raio, e comparação com bairro.
  `npm run build`/`lint`/`tsc` limpos. Total do projeto: **180 testes Python passando**.

### Checkpoint 11e - Passe de design system e polimento: **concluído**

Consolidação depois que 11a-11d já geraram os componentes reais em uso - não feature nova.

- **Participação por categoria** (métrica explicitamente listada no prompt de referência, seção
  "TIPOS DE MÉTRICAS PERMITIDAS") estava documentada em `/metodologia#participacao` mas nunca
  aparecia calculada em tela - `QuebraCategoriaBars` só mostrava contagem bruta. Corrigido num
  único lugar (o componente é reaproveitado em 3 telas: perfil de bairro, comparação, busca por
  raio) - cada barra agora mostra `contagem (participação%)`, reaproveitando
  `formatarPercentual1` já existente.
- Auditoria do critério de sucesso #9 do prompt ("não encontrar nenhum indicador cuja
  metodologia não esteja clara"): `ComparisonTable` (aberturas/saldo/posição no ranking) e as
  legendas de `RankingList`/`CategoryRankingList` (variação %) não tinham `MethodologyTooltip` -
  adicionado nos três lugares, reaproveitando o mesmo texto de fórmula já usado no `StatTile`
  do painel de detalhe (não inventado de novo). `/comparacao` ganhou o link "Metodologia" no
  cabeçalho, pelo mesmo motivo que `/radar` já tinha (checkpoint 11a).
- Revisão de duplicação de componente: `RankingList`/`CategoryRankingList` continuam
  separados (representam dados genuinamente diferentes - um tem sparkline, o outro não; a
  duplicação é pequena e clara) - não forçada uma abstração comum só por semelhança visual,
  conforme o princípio do projeto contra abstração prematura. `SerieTemporalChart` (extraído no
  checkpoint 11c) já cobria o único caso real de duplicação de gráfico que existia.
- **Rodado contra o banco/API/frontend reais**: verificado visualmente que a participação % não
  quebra o layout das barras em nenhuma das 3 telas (ex.: JUVEVÊ - "(sem categoria) 52
  (68,4%)"), e que os tooltips novos abrem com a fórmula certa. `npm run build`/`lint`/`tsc`
  limpos, 180 testes Python passando (sem mudança de contagem - só frontend nesta etapa).

**Fase de inteligência territorial (checkpoints 11a-11e) concluída.** As 4 experiências do
prompt de referência (Radar, Perfil do Território, Investigação por Endereço, Comparação)
estão implementadas e rodando localmente; toda métrica em tela tem fórmula documentada em
`/metodologia` e a maioria tem `MethodologyTooltip` inline. Deploy (checkpoints 6b/7d) segue
adiado por decisão do dono, como documentado desde a fase 1 - tudo roda local
(`uvicorn`/`next dev`).

## Radar Imobiliário (fase seguinte, checkpoints 11a-11f próprios)

Segundo produto do projeto - reaproveita `dim_territorio`/`entidade`/`observacao_entidade`/
`fato_evento_territorial` sem alterá-los, adiciona schema/conectores novos. **Numeração de
checkpoint reinicia em 11a-11f nesta fase, independente dos checkpoints "11a-11e" da fase de
inteligência territorial do Radar de Comércio acima** - são duas sequências diferentes que só
coincidem no rótulo; não confundir as duas ao procurar contexto.

Regra não-negociável desta fase: quatro grandezas monetárias existem no mercado imobiliário
(venal/avaliação/anúncio/transação) e nunca são intercambiáveis - nenhum campo genérico
`valor`/`preco` é permitido em tabela, endpoint ou UI; todo valor monetário carrega
`tipo_valor` e `fonte_id` (`src/domain/valuation/`).

### Checkpoint 11a - Verificação de fontes: **concluído, com uma correção real registrada**

`docs/fontes-imobiliario.md` documenta as três fontes (Relatório Mensal Alvará/CVCO da SMU,
Planta Genérica de Valores/IPPUC, camada Edificação do GeoCuritiba). **A primeira passagem
desta verificação concluiu, incorretamente, que duas das três fontes estavam bloqueadas** -
erro de investigação, não da fonte, apontado pelo dono do projeto e corrigido antes de
prosseguir:
- O relatório da SMU (`www5.curitiba.pr.gov.br`) parecia fora do ar porque as duas primeiras
  tentativas foram contra HTTPS/porta 443, que não responde nesse host (timeout) - a porta 80
  responde normalmente. Confirmado ponta a ponta depois: o formulário aceita postback real
  (`__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__EVENTVALIDATION`) e devolve um `.xls` (HTML/MSO) com
  até 35 colunas por linha - **muito mais rico que o prompt de referência assumia**, incluindo
  `Quantidade Pavimentos`, `Metragem Construída Lote`, `Número CVCO`/`Data Vistoria` no próprio
  relatório de alvará, e `Indicação Fiscal`/`Inscrição Imobiliária` como chave direta de junção
  com o Lote Cadastral do GeoCuritiba (sem geocodificação nenhuma).
- A PGV (`Publico_GeoCuritiba_Planta_Generica_Valores/MapServer`) foi consultada na URL certa
  desde o início, mas a primeira passagem só leu a lista de layers do `MapServer` raiz (que não
  mostra campos) e concluiu, por suposição a partir dos nomes, que nenhuma tinha valor
  monetário. A layer 0 ("Microrregião (PGV 2025)") na verdade tem o campo `vukt` (Valor
  Unitário Característico de Terreno, R$/m²) - 1.062 polígonos, sem autenticação, CRS correto
  (`wkid 31982`, igual a todo o resto do GeoCuritiba). Um shapefile legado
  (`ippuc.org.br/geodownloads/SHAPES/PGV.zip`, 300k pontos por lote) também existe mas está
  parado em 2017 e sem CRS identificável - documentado como achado à parte, não usado.
- A camada "Edificação" (layer 23 do `MapaCadastral`) de fato não existe - confirmado
  consultando o serviço inteiro (41 layers reais, sem esse nome). "Lote Cadastral" (id 15,
  308.882 feições) e "Zoneamento Lei 15.511/2019" (id 36, 223 feições) existem exatamente como
  o prompt de referência esperava, campos batendo 1:1.

Lição registrada para não repetir: **distinguir "meu método de verificação falhou" de "a fonte
não existe"** antes de reportar um bloqueio - checar porta/protocolo alternativo e o schema de
campo por layer (não só a lista de layers), antes de concluir que uma fonte pública está fora
do ar ou incompleta.

### Checkpoint 11b - Domínio e modelo: **concluído**

- `src/domain/valuation/` - `ValorMonetario` (a regra pura das quatro grandezas:
  `tipo_valor`/`componente`/`fonte_id` obrigatórios, valida contra listas fechadas) e
  `ValorReferenciaTerritorial` (o registro completo, pronto pra persistir - geometria,
  vigência, proveniência). `media_valor_m2`/`mediana_valor_m2` recusam misturar `tipo_valor`
  OU `componente` diferentes no mesmo agregado (o teste que a seção 1 do prompt de referência
  pede explicitamente). 23 testes.
- Catálogo de eventos (`domain/event/models.py`) ganhou `ALVARA_APROVADO`, `OBRA_CONCLUIDA`,
  `ALVARA_DEMOLICAO` (entity_type="obra", fonte confirmada no 11a) e `ZONEAMENTO_ALTERADO`
  (entity_type="territorio", reservado - a regra de detecção por diff de `data_versao` é
  trabalho de pipeline, não deste checkpoint). `LANCAMENTO`/`TRANSACAO` também entraram, **só
  como reservados** (mesmo padrão de `FECHAMENTO_CONFIRMADO` já existente) - nenhuma regra os
  emite, por decisão explícita do prompt de referência (sem fonte pública confiável pra
  nenhum dos dois em Curitiba).
- `canonical.valor_referencia_territorial` e `canonical.zoneamento_territorial`
  (migração `61a2467444fb`) + `canonical.lote_cadastral` (migração `19b351ae137c`, criada
  durante o 11c como suporte de junção, não estava na seção 3 do prompt mas é necessária pra
  resolver território/zoneamento por Indicação Fiscal sem geocodificar). `fonte_id` é texto
  livre sem FK pra uma `dim_fonte` (o prompt de referência sugeria essa FK, mas nenhuma tabela
  do projeto até hoje tem `dim_fonte` - desvio deliberado, documentado no ORM, pra não
  introduzir uma abstração nova sem nenhum outro uso).
- **Achado real, corrigido antes de rodar contra dado de verdade**: a primeira versão da
  constraint de idempotência de `valor_referencia_territorial` usava
  `(territorio_id, tipo_valor, componente, fonte_id, vigencia_inicio)` - colapsava todas as
  microrregiões de um mesmo bairro numa única linha (um bairro comum tem várias microrregiões
  da PGV, cada uma com seu próprio `vukt`). Corrigido trocando pra
  `(objectid_fonte, fonte_id, vigencia_inicio)` - a identidade do registro na fonte, não o
  território derivado. Sem essa correção, rodar `ippuc_pgv` real gravava 74 linhas em vez de
  1.011 (achado rodando contra dado real do 11c, não pego pelos testes unitários - nenhum
  teste tinha duas geometrias do mesmo bairro).
- Reaproveitamento: `src/infrastructure/connectors/geocuritiba_bairro/geometry.py` (reprojeção
  EPSG:31982→4326 + conversão de anéis Esri) foi movido para
  `src/infrastructure/connectors/geometry.py` (compartilhado) - checkpoint 11c precisava dele
  em três conectores novos, mesmo padrão de reuso já estabelecido pra `text.py`/`slugify`.
- **Migração rodada contra o Postgres real**: `alembic upgrade head` limpo, `alembic check` sem
  drift novo (só o índice pré-existente já documentado desde o checkpoint 9a), índices GIST
  espaciais confirmados autogerados, `CHECK` de `tipo_valor` testado rejeitando um valor
  inválido de verdade. Total do projeto: 216 testes (antes de somar os testes de conector do
  11c) passando.

### Checkpoint 11c - Conectores do núcleo: **concluído, rodado contra as três fontes reais**

Três conectores, todos seguindo o contrato `fetch()/normalize()` já estabelecido, com desvio
documentado de assinatura igual ao já usado em `alvaras_smf` (parâmetros extras em
`normalize()` pra passar lookup de território, resolvido pela orquestração, não dentro do
conector).

- **`ippuc_pgv`** (`src/infrastructure/connectors/ippuc_pgv/`) - layer "Microrregião (PGV
  2025)". Vigência (`vigencia_inicio`/`moeda_data`) extraída do nome da layer via regex (não
  há campo de data por feição na fonte - achado do 11a) - se a IPPUC renomear pra "PGV 2026"
  no futuro, o conector acompanha sozinho, com aviso de log se o padrão não bater. **Rodado
  contra a API real**: 1.062 feições, 1.011 normalizadas (51 ignoradas - código `UC-*`, áreas
  de conservação sem VUKT atribuído, achado plausível não é bug), **100% resolvido contra
  `dim_territorio`**, 74 bairros distintos cobertos. `componente='terreno'` só, como já
  documentado no 11a.
- **`geocuritiba_cadastro`** (`src/infrastructure/connectors/geocuritiba_cadastro/`) - duas
  classes: `LoteCadastralConnector` (layer 15, ~308 mil feições - `fetch()`/`normalize()` em
  streaming via JSONL em disco, mesma disciplina de memória de `alvaras_smf`, nunca carrega o
  dataset inteiro) e `ZoneamentoConnector` (layer 36, 223 feições, sem essa necessidade de
  streaming). Zoneamento não resolve `territorio_id` (a camada não carrega nome de bairro por
  feição - resolver exigiria join espacial, fora de escopo). Quadra Cadastral **não** foi
  buscada - decisão de escopo (nenhuma tabela do checkpoint precisa dela; Lote Cadastral já
  carrega bairro/zoneamento direto por lote). **Rodado contra a API real**: 308.882 lotes
  gravados (upsert por `objectid_fonte`, só 1 bairro sem correspondência -
  "CIDADE INDUSTRIAL", mesma variação de grafia já registrada no checkpoint 2), 223
  zoneamentos gravados.
- **`smu_alvaras_construcao`** (`src/infrastructure/connectors/smu_alvaras_construcao/`) - duas
  classes finas (`AlvaraConstrucaoConnector`/`CvcoConnector`, `rblRelacao=1`/`2`) sobre uma
  base comum que replica o postback ASP.NET e faz o parsing do HTML/MSO por posição de coluna
  (`parsing.py`, `COLUNAS` - 34 no relatório de alvará, 35 no de CVCO). `tipo_entidade="obra"`,
  `identificador_fonte="Número Alvará"` - mesmo padrão de `Entidade`/`ObservacaoEntidade` do
  comércio (princípio 6), nenhum atalho.
  - **Achado real, corrigido rodando contra dado de verdade**: a primeira execução resolveu
    **0%** de território - a Indicação Fiscal do relatório da SMU vem com pontos
    (`"12.006.027"`), a de `lote_cadastral` (GeoCuritiba) vem só com dígitos (`"12006027"`).
    Sem essa normalização, a chave de junção nunca batia, apesar de ser logicamente a mesma
    informação. Corrigido com `normalizar_indicacao_fiscal()` (remove tudo que não é dígito)
    aplicado nos dois lados do lookup. Depois da correção: **90,7%** de território resolvido no
    relatório de alvará, **91,6%** no de CVCO - contra dado real de jan-jul/2026.
  - **Decisão de arquitetura, motivada por um bug real evitado antes de rodar**: a primeira
    versão do pipeline detectava evento (`ALVARA_APROVADO`/`OBRA_CONCLUIDA`) na mesma
    passagem que gravava a observação, usando o objeto de domínio recém-criado em memória.
    Isso quebra numa condição real: se a observação já existisse (reprocessamento do mesmo
    mês), o `INSERT` é ignorado (idempotência via `ON CONFLICT DO NOTHING`), mas o objeto em
    memória teria um `observacao_id` novo, nunca persistido - o evento apontaria
    (`origem_observacoes`) pra um id inexistente no banco. Corrigido separando em dois
    estágios, replicando o padrão já estabelecido pelo comércio
    (`pipelines/ingestion/run_alvaras_smf.py` só ingere; `pipelines/event_detection/
    run_comercio.py` detecta evento lendo de volta do banco): `pipelines/ingestion/
    run_smu_alvaras_construcao.py` (só fetch→normalize→grava entidade/observação) e
    `pipelines/event_detection/run_obra.py` (novo - lê observação de volta via
    `observacao_repository.iter_observacoes_por_fonte`, nova função de leitura em cursor
    server-side, e chama `domain.event.detectar_evento_obra`). `detectar_evento_obra` é regra
    pura nova (`domain/event/regras.py`) - diferente de `detectar_eventos_par` (comércio, que
    compara duas observações), deriva o evento de uma única observação porque a fonte já
    informa a data exata do fato (`Data Criação Alvará`/`Data Vistoria`), sem precisar de
    inferência por ausência/presença entre snapshots.
  - **Rodado contra a API real** (jan-jul/2026): 2.214 alvarás de construção, 1.373 CVCOs
    (1.392 lidos, 19 duplicados na mesma referência mensal, mesmo padrão de idempotência das
    outras fontes). 2.214 eventos `ALVARA_APROVADO` e 1.373 `OBRA_CONCLUIDA` gravados, **todos
    com data resolvida** (0 sem data relevante). Confirmada idempotência: rodar a ingestão e a
    detecção de evento uma segunda vez contra o mesmo período grava 0 observações e 0 eventos
    novos.
- **Rodado contra o banco/fontes reais**: 236 testes Python passando (todos os conectores
  testados com sessão HTTP falsa, sem depender de rede em CI). `alembic check` sem drift novo.

### Checkpoint 11d - Conectores de contexto: **concluído, rodado contra as três fontes reais**

Três conectores de contexto de mercado/demografia (BCB, QuintoAndar, IBGE), granularidades
diferentes e explícitas em cada schema - nenhum reaproveita `valor_referencia_territorial`
(esse é território com geometria; os três daqui são UF/cidade/setor, sem geometria nesta
fase). Verificação de fonte feita antes do código, mesma disciplina do checkpoint 11a -
resultado completo em `docs/fontes-imobiliario.md` (seção "Checkpoint 11d").

- **`bcb_mercado_imobiliario`** (`src/infrastructure/connectors/bcb_mercado_imobiliario/`) -
  serviço OData `MercadoImobiliario` do BCB, licença ODbL. **Achado que mudou o desenho**: o
  serviço não é uma tabela de mercado imobiliário estruturada - é uma tabela genérica de
  milhares de séries de crédito (`Data`/`Info`/`Valor`), e o "catálogo" de séries relevantes
  não é descobrível por consulta exploratória (listagem de `Info` distintos não é exaustiva).
  As 14 séries reais de imóveis vieram da Metodologia.pdf oficial do BCB, não de tentativa e
  erro contra o serviço. Cada série tem granularidade UF (sufixo `_pr` para Paraná) - **nunca
  rotular como Curitiba**. `domain.valuation.IndicadorMercadoImobiliarioUf` (novo, reaproveita
  `TIPOS_VALOR_VALIDOS`) distingue três naturezas de número na mesma fonte via `categoria`
  (`valor`/`area`/`contagem`) - nunca somar uma contagem de imóveis com um valor monetário.
  **Achado de metodologia**: `imoveis_valor_compra` não é uma segunda avaliação - a
  Metodologia.pdf descreve como "a mediana do valor dos imóveis **adquiridos** ... classificada
  em avaliação ou compra" (fonte ACNV1501/SCR) - "compra" é o preço efetivamente contratado,
  por isso mapeado para `tipo_valor='transacao'`, não `'avaliacao'`. Viés de amostra explícito
  (só financiamento via SCR) documentado no código e nos dados - nunca apresentar como preço de
  mercado do Paraná inteiro. **Achado técnico, corrigido rodando contra a API real**: `requests`
  codifica espaço como `+` no dict `params=`, e o parser OData do BCB trata `+` como operador de
  adição (erro real: `"types 'Edm.Boolean' and 'Edm.String' are not compatible"`) - corrigido
  montando a query com `%20` direto na URL, sem usar `params=`.
- **`quintoandar_aluguel`** (`src/infrastructure/connectors/quintoandar_aluguel/`) - CSV
  público (`publicfiles.data.quintoandar.com.br`), filtrado para `city_name='cur'` (Curitiba,
  confirmado entre os 6 códigos de cidade do arquivo). `domain.contexto.IndicadorAluguelMercado`
  (novo pacote `domain/contexto/`, deliberadamente fora de `domain/valuation` - aluguel não é
  uma das quatro grandezas de compra, nunca rotulado com `tipo_valor`). **Duas afirmações do
  prompt de referência corrigidas por achado real** (não erro do prompt, divergência real):
  a metodologia oficial descreve o índice como misturando anúncios E contratos fechados, não só
  "contratos reais"; a periodicidade real do CSV é mensal (não trimestral - os relatórios em
  PDF trimestrais são um resumo, o dado bruto é mês a mês). `est_price` tratado como R$/m²/mês
  por inferência de magnitude (cruzado contra preço de venda de `relatorio_cv.csv`), não por
  confirmação textual explícita - documentado como tal.
- **`ibge_censo_setor`** (`src/infrastructure/connectors/ibge_censo_setor/`) - arquivo "básico"
  (V0001-V0009: população, domicílios por tipo) dos Agregados por Setores Censitários do Censo
  2022, resolvido dinamicamente por regex sobre a listagem (nome do arquivo carrega uma data
  que muda a cada publicação do IBGE, mesmo padrão de `alvaras_smf._arquivo_mais_recente`).
  **Achado que simplificou o desenho original**: o arquivo já carrega `NM_BAIRRO` por setor -
  não precisa de join espacial com `dim_territorio` (o prompt de referência original previa
  precisar). `domain.contexto.IndicadorCensitarioSetor` resolve `territorio_id` por slug do
  nome do bairro, mesmo padrão de `ippuc_pgv`/`geocuritiba_cadastro`. **Achado que confirma uma
  ressalva do próprio prompt**: o dicionário de dados oficial não tem nenhuma variável de
  condição de ocupação (própria/alugada) nem valor de aluguel nos resultados do universo -
  são variáveis de amostra, publicadas em outro momento pelo IBGE (o prompt já suspeitava disso
  para aluguel; o achado real é que nem condição de ocupação está disponível).
- `src/infrastructure/database/orm/contexto_bcb_imobiliario.py`,
  `contexto_quintoandar_aluguel.py`, `contexto_censo_setor.py` +
  `repositories/contexto_bcb_repository.py`, `contexto_quintoandar_repository.py`
  (idempotência por chave natural, `ON CONFLICT DO NOTHING` - mesma disciplina de
  `observacao_entidade`), `contexto_censo_repository.py` (upsert por `setor_censitario`, fonte
  estática). Migração `fa260fcdf01b` cria as três tabelas.
- `src/pipelines/ingestion/run_bcb_mercado_imobiliario.py`, `run_quintoandar_aluguel.py`,
  `run_ibge_censo_setor.py` - mesmo padrão fetch→normalize→grava→`pipeline_run` dos conectores
  anteriores.
- **Rodado contra as três fontes reais**: BCB - 14 séries × ~100 meses = **1.400 leituras**
  gravadas (uf=PR, desde 2018-01). QuintoAndar - 1.708 linhas totais no CSV, 229 de Curitiba,
  **221 leituras gravadas** (8 ficam de fora - meses iniciais da série sem amostra suficiente,
  vêm vazios na própria fonte). IBGE - **3.190 setores censitários de Curitiba gravados**,
  **99,3% (3.169) com bairro resolvido** (só "Botiatuvinha", grafia do IBGE, não casa com
  "BUTIATUVINHA" oficial - mesma classe de variação de grafia já documentada em outros
  checkpoints).
- 35 testes novos (`tests/domain/valuation/` ampliado, `tests/domain/contexto/` novo,
  `tests/infrastructure/connectors/bcb_mercado_imobiliario/`, `quintoandar_aluguel/`,
  `ibge_censo_setor/` - sessão HTTP falsa em todos, sem depender de rede em CI). `alembic check`
  sem drift novo (só o índice pré-existente já documentado desde o checkpoint 8). Total do
  projeto: **271 testes Python passando**.

### Checkpoint 11e - Features e API: **concluído, rodado contra a API/banco reais**

Seções 5 e 6 do prompt de referência. Todas as consultas são ao vivo (sem feature
materializada nova) - volume do Radar Imobiliário é pequeno (milhares de eventos, não
centenas de milhares como comércio), mesmo raciocínio que já vale para
`geolocalizacao_repository.eventos_no_raio` (checkpoint 11d do Radar de Comércio).

**Métrica 5 do prompt de referência (razão área licenciada/área construída existente)
não implementada, de propósito** - o checkpoint 11a já havia confirmado que não existe
nenhuma camada de footprint/estoque construído publicada pelo GeoCuritiba; implementar
essa razão exigiria inventar um proxy para o denominador, o mesmo atalho que o projeto já
recusa para `TRANSACAO`/`LANCAMENTO`. Documentado como lacuna real, não escondido.

- `src/infrastructure/database/repositories/construcao_repository.py` (novo):
  - `consultar_metricas_construcao` - alvarás aprovados/CVCOs concluídos por bairro (+ mês,
    se `territorio_id` for informado), com área licenciada/concluída total. Junta
    `fato_evento_territorial` com `observacao_entidade` via `origem_observacoes[1]` (a
    única observação que sustenta um evento de obra) - `ALVARA_APROVADO` e
    `OBRA_CONCLUIDA` sempre em campos separados, nunca somados (trava metodológica).
  - `consultar_defasagem_mediana_por_bairro` - mediana em dias entre `ALVARA_APROVADO` e
    `OBRA_CONCLUIDA` do mesmo empreendimento (mesma `entidade_id`, já que
    `identificador_fonte` é o mesmo Número Alvará nos dois relatórios).
    **Achado real, rodando contra dado real**: o campo "Data Vistoria" embutido no próprio
    relatório de Alvará - citado no checkpoint 11a como um atalho possível para calcular
    a defasagem sem cruzar os dois relatórios - está vazio em **100% das 2.214**
    observações reais de `smu_alvara_construcao`. A defasagem só é calculável cruzando os
    dois eventos por `entidade_id`, nunca lendo a mesma linha do relatório de alvará.
    Piso mínimo de volume novo, `PISO_MINIMO_PARES_DEFASAGEM = 3` (mesmo espírito de
    `BASELINE_MINIMO_RANKING` do checkpoint 10d, aplicado a uma contagem de pares
    observados em vez de um baseline de série temporal) - `pares` sempre visível na
    resposta, nunca escondido.
- `valor_referencia_repository.consultar_valor_venal_mediano_por_bairro` (novo) -
  reaproveita `domain.valuation.mediana_valor_m2` (a mesma regra pura que recusa misturar
  `tipo_valor`/`componente` diferentes) agrupada por bairro em Python. Sem
  baseline/variação/tendência nenhuma no retorno - trava "PGV não é série temporal"
  (checkpoint 11a) garantida pela ausência do campo, não por uma checagem em runtime.
- `zoneamento_repository.listar_zoneamento` (novo) - leitura simples, sem filtro de
  vigência (a fonte ainda não passou por nenhuma revisão observada).
- `contexto_bcb_repository.consultar_ultimo_periodo`,
  `contexto_quintoandar_repository.consultar_ultimo_periodo`,
  `contexto_censo_repository.consultar_agregado_por_bairro` (novos) - leitura do mês mais
  recente disponível (BCB/QuintoAndar) e soma por bairro (Censo, agrupado a partir do
  setor). **Densidade construtiva (métrica 6) rotulada como "densidade domiciliar"**, não
  "densidade construtiva/footprint" como o prompt de referência original pedia - mesmo
  motivo da métrica 5 (não existe footprint publicado); usa só o que o Censo de fato tem
  (domicílios/km² por bairro), documentado como reinterpretação, não substituto
  inventado.
- `observacao_repository.contar_resolucao_territorio_por_fonte`,
  `lote_cadastral_repository.contar_lotes`, `pipeline_run_repository.
  ultima_execucao_com_sucesso` (ganhou `conector_id` opcional, retrocompatível) - suporte
  ao indicador objetivo de qualidade de dado (trava metodológica "Qualidade de dado como
  indicador objetivo").
- `apps/api/routers/imoveis.py` (novo, prefixo `/imoveis` - a interpretação real do
  "namespace novo `/api/imoveis/...`" do prompt de referência, já que nenhuma rota
  existente do projeto usa prefixo `/api/`; adicionar um prefixo global só para este
  produto seria inconsistente com o resto da API, não um desvio de escopo):
  - `GET /imoveis/construcao` - sem `territorio_id`: agregado por bairro (período inteiro)
    com defasagem mediana anexada; com `territorio_id`: série mensal, sem defasagem
    (`motivo_indisponivel_defasagem="nao_aplicavel_no_modo_serie_mensal"` - amostra mensal
    é sempre pequena demais pra mediana).
  - `GET /imoveis/valor-referencia` - `tipo_valor`/`componente`/`fonte_id`/`metodologia`/
    `vigencia_inicio` sempre explícitos (regra das quatro grandezas).
  - `GET /imoveis/zoneamento` - GeoJSON FeatureCollection, mesmo padrão de `GET
    /territorios`, com `data_versao`/`data_atualizacao` por feição.
  - `GET /imoveis/contexto` - BCB (granularidade `uf`), QuintoAndar (`cidade`), Censo
    (`setor_censitario_agregado_por_bairro`) - granularidade declarada em cada seção da
    própria resposta.
  - `GET /imoveis/qualidade-dados` - % de alvará/CVCO com território resolvido, contagem
    de lotes sem geometria/sem território, vigência da PGV, última atualização por fonte
    (8 conectores) - mesmo princípio de `GET /qualidade-dados` (comércio): fatos crus, sem
    nota nem score composto.
- `apps/api/main.py`: título trocado de "Mercator - Radar de Comércio API" para "Mercator
  API" (a partir daqui a mesma API serve os dois produtos - o título antigo sugeria que
  `/imoveis` seria secundário/fora do escopo).
- **Achado de investigação, não um bug real**: `curl | python json.tool` e `print(repr(...))`
  mostravam o campo `unidade` (`"m²"`/`"imóveis"`) como lixo de encoding duplo. Verificado
  byte a byte (`.encode('utf-8').hex()`) direto no banco: o dado está 100% correto em UTF-8
  - é o mesmo problema de exibição do console Windows já documentado nas Notas
  operacionais, desta vez alcançando também pipes de shell/`print()`, não só o terminal
  direto. Não mudou nada no código.
- **Travas metodológicas** (seção 5, verificáveis em teste): #3 (piso mínimo de volume) e
  #4 (PGV não é série temporal) testadas diretamente
  (`test_construcao_agregado_piso_minimo_de_pares_para_defasagem`,
  `test_valor_referencia_mediana_por_bairro_sem_variacao`). #6 (qualidade de dado como
  indicador objetivo) testada via `test_qualidade_dados_conta_resolucao_de_territorio_e_fontes`.
  #1 (nada de score composto) e #2 (ranking separa absoluto de percentual) satisfeitas por
  desenho - nenhum ranking novo foi construído neste checkpoint (fora do escopo dos 4
  endpoints do prompt de referência), e nenhum campo mistura contagem absoluta com
  variação percentual em `/imoveis/construcao`. #5 (linguagem de associação, não
  causalidade) é responsabilidade do texto exibido no frontend - fica para o checkpoint
  11f.
- **Rodado contra o banco/API reais**: `/imoveis/construcao` agregado devolve 73 bairros
  (Água Verde: 51 alvarás/91.962 m² licenciados, 25 CVCOs/51.249 m² concluídos); série de
  CENTRO devolve 7 meses. `/imoveis/valor-referencia` devolve 74 bairros (Capão da Imbuia:
  R$1.244,22/m² mediano sobre 10 registros). `/imoveis/zoneamento` devolve 223 feições.
  `/imoveis/contexto` devolve as 14 séries do BCB (PR, abril/2026), os 4 segmentos do
  índice QuintoAndar (Curitiba, agosto/2025) e 74 bairros agregados do Censo (Cristo Rei:
  7.460 domicílios/km², a maior densidade domiciliar da cidade). `/imoveis/qualidade-dados`
  devolve 90,7%/91,9% de resolução de território (alvará/CVCO), 1 lote sem geometria/29.530
  sem território, PGV vigente desde jan/2025 cobrindo 74 bairros (1.011 registros no
  total). 12 testes novos (`tests/api/test_imoveis.py`, seed própria em
  `tests/api/conftest.py` - 5 construções/2 bairros, cenário conhecido de piso mínimo).
  Total do projeto: **283 testes Python passando**. `alembic check` sem drift novo (só o
  já documentado desde o checkpoint 8 - nenhuma tabela nova neste checkpoint).

### Checkpoint 11f - Frontend do Radar Imobiliário: **concluído**

Não havia prompt de referência detalhado para esta etapa (diferente dos checkpoints
anteriores) - IA (arquitetura visual, agrupamento em abas, componentes reaproveitados)
inferida a partir dos 5 endpoints já prontos do checkpoint 11e e dos padrões já
estabelecidos pelo frontend do Radar de Comércio (checkpoints 6a-11e).

- Rota nova `/imoveis` (`app/imoveis/page.tsx` + `components/imoveis-dashboard.tsx`) - mesma
  forma do `Dashboard` de comércio (cabeçalho + `Tabs` + filtros + Sheet de detalhe), com
  quatro abas em vez de três, uma por fonte real do checkpoint 11c-11e, nunca combinadas numa
  métrica composta: **Construção** (`construcao-tab.tsx`), **Valor de referência**
  (`valor-referencia-tab.tsx`), **Zoneamento** (`zoneamento-tab.tsx`), **Contexto de mercado**
  (`contexto-tab.tsx` + `contexto-mercado-panel.tsx`). Filtro de período (preset como no
  Radar de Comércio) só aparece na aba Construção - as outras três não são série temporal
  (PGV, zoneamento e contexto de mercado são "foto" do estado mais recente, não histórico).
- `src/lib/api.ts` ganhou os cinco fetchers do Radar Imobiliário (`getConstrucao`,
  `getValorReferencia`, `getZoneamento`, `getContextoImoveis`, `getQualidadeDadosImoveis`),
  mesmo padrão snake_case→camelCase já usado pro Radar de Comércio.
- `src/lib/palette.ts` ganhou `expressaoCorSequencial` (rampa azul de 9 degraus já validada,
  reaproveitada como sequencial de magnitude - construção e valor de referência não têm polo
  negativo, então nunca a divergente do mapa de saldo) e `CATEGORICO_ZONEAMENTO`/
  `ZONA_OUTROS_COR` para o zoneamento. **Decisão motivada pelo skill `dataviz`**: o zoneamento
  real de Curitiba tem 12 `nm_grupo` distintos (confirmado por query direta no banco - "ZONAS
  RESIDENCIAIS", "EIXO METROPOLITANO LINHA VERDE", "UNIDADE DE CONSERVAÇÃO", etc.), mas a
  paleta categórica de 8 cores do skill só valida CVD "all-pairs" (o teste que importa pra um
  coroplético, onde cores adjacentes quaisquer podem aparecer lado a lado) até 3 slots - acima
  disso, o próprio skill recomenda dobrar pra "outros" ou facetar. `zoneamento-map.tsx`
  calcula dinamicamente os 3 `nm_grupo` mais frequentes (`top3Grupos`, por contagem de
  feição) e pinta o resto num neutro acromático - nunca uma 4ª hue arriscada. Confirmado
  contra o banco real: os 3 mais frequentes são Zonas Residenciais, Eixo Metropolitano Linha
  Verde e Unidade de Conservação.
- Componentes novos extraídos/reaproveitados entre duas ou mais telas, seguindo o mesmo
  princípio de reuso já estabelecido (`SerieTemporalChart` no checkpoint 11c):
  `lib/geo.ts::calcularBoundsPoligonos` (extraído de `choropleth-map.tsx`, reaproveitado por
  todos os mapas novos), `components/fato-tile.tsx` (extraído de `radius-search-panel.tsx`),
  `components/imoveis-choropleth-map.tsx` (coroplético genérico por bairro, reaproveitado por
  Construção e Valor de referência - a mesma forma, só a fonte/expressão de cor mudam),
  `sequential-legend.tsx`, `categorical-legend.tsx`, `construcao-serie-chart.tsx` (mesma
  anatomia de `SerieTemporalChart`, rótulos e significado próprios: alvará "vai mudar" x CVCO
  "já mudou", nunca a mesma leitura de aberturas/desaparecimentos), `zoneamento-map.tsx`,
  `data-quality-imoveis.tsx`/`data-quality-imoveis-section.tsx` (mesmo princípio de
  `DataQuality`: fatos crus de `/imoveis/qualidade-dados`, sem nota nem score),
  `imoveis-detail-panel.tsx` (Sheet lateral - `FatoTile`, não `StatTile`, porque a API de
  construção não expõe baseline/tendência).
- Navegação cruzada entre os dois produtos: link "Radar Imobiliário" adicionado ao cabeçalho
  do Radar de Comércio (`dashboard.tsx`) e de `/comparacao`; link "Radar de Comércio" e
  "Metodologia" no cabeçalho de `/imoveis`; tela de entrada (`app/page.tsx`) ganhou um segundo
  CTA. Metadata do `layout.tsx` generalizada de "Radar de Comércio" pra "Mercator" (mesmo
  motivo do rename do título da API no checkpoint 11e - a partir daqui o produto é dois
  radares, não um com um apêndice).
- `/metodologia` ganhou uma segunda seção "Qualidade dos dados — Radar Imobiliário"
  (`DataQualityImoveisSection`, mesmo princípio da seção de comércio já existente) e um bloco
  de seções próprias (`SECOES_IMOVEIS`, âncoras prefixadas `imoveis-` pra não colidir com as
  seções de comércio) documentando alvará×CVCO, defasagem, valor de referência (PGV não é
  série temporal), zoneamento e a granularidade de cada fonte de contexto (UF/cidade/setor).
- **Bug real encontrado e corrigido na checagem visual**: `vigência` da PGV mostrava um dia a
  menos (ex.: "31/12/2024" em vez de "01/01/2025", vindo de `vigencia_inicio: "2025-01-01"` da
  API). Causa: `new Date("2025-01-01")` é interpretado como meia-noite UTC pelo construtor, e
  `.toLocaleDateString("pt-BR")` reformata no fuso local (Curitiba, UTC-3), regredindo um dia -
  mesma classe de bug que `formatarMesAno` (`lib/periodo.ts`, checkpoint 7c) já evitava fazendo
  parsing por split de string em vez de `new Date`. Corrigido com `formatarDataDMY` (novo, mesmo
  padrão de split), aplicado em `valor-referencia-tab.tsx` e `data-quality-imoveis.tsx` - os
  dois lugares que formatavam uma data-só (sem horário) vinda da API.
- **Achado real, não corrigido por ser pré-existente e fora do escopo deste checkpoint**: o
  variante `outline` de `components/ui/button.tsx` (shadcn) renderiza sem nenhuma borda visível
  - `getComputedStyle` confirma `border-color: rgba(0,0,0,0)` (a classe base `border-transparent`
  vence a classe do variante `border-border` no CSS compilado, apesar de `cn()` usar
  `tailwind-merge`). Reproduzido não só no CTA novo desta tela, mas também no botão
  pré-existente "Escolher intervalo" do Radar de Comércio (`dashboard.tsx`, checkpoint 7c) -
  não é uma regressão deste checkpoint, é um bug latente do design system que ninguém tinha
  notado (o único outro uso de `variant="outline"` no app é um botão pequeno, menos
  perceptível). Contornado localmente usando `variant="secondary"` no CTA de
  `app/page.tsx` (sem borda, preenchimento sólido claro - não depende do merge de cor de
  borda). Causa raiz (reconhecimento de `border-border` como parte do grupo de conflito
  "border-color" pelo `tailwind-merge`) não investigada a fundo nem corrigida - decisão de
  quando/se vale a pena mexer no design system compartilhado fica com o dono do projeto.
- **Rodado contra o banco/API/frontend reais** (via workaround de IP de LAN - ver Notas
  operacionais): `/imoveis` renderiza as quatro abas com dado real - Construção mostra "2.214
  alvarás aprovados e 1.373 CVCOs concluídos" no preset padrão de 12 meses, coroplético
  sequencial recolore corretamente ao alternar entre as duas métricas (toggle testado: 129 →
  110 no máximo da legenda), clique num bairro (CRISTO REI) abre o painel com os stat tiles
  certos (14 alvarás/6.126 m², 8 CVCOs/12.402 m², defasagem "dado em construção", valor venal
  R$2.013,68/m²) e o gráfico de duas linhas; Valor de referência mostra "74 bairros" e legenda
  até R$4.912,64/m², vigência corrigida (01/01/2025); Zoneamento mostra "223 zonas" com legenda
  dinâmica (Zonas Residenciais/Eixo Metropolitano Linha Verde/Unidade de Conservação/outros) e
  popup com nome completo da zona ao passar o mouse; Contexto de mercado mostra as 14 séries do
  BCB com nomes legíveis, os 4 segmentos do QuintoAndar e a tabela de bairros do Censo ordenada
  por densidade domiciliar. `npm run build`/`lint`/`tsc` limpos.

## Radar de Anúncios (fase seguinte, checkpoints 12a-12i)

Terceiro produto do projeto - mede intenção/movimento de mercado via anúncio (oferta), nunca
transação consumada, com atualização semanal. Reaproveita `dim_territorio`/`entidade`/
`observacao_*`/`fato_evento_territorial` sem alterá-los, mesma disciplina dos dois produtos
anteriores. **Numeração de checkpoint reinicia em 12a-12i, terceira sequência independente**
que só coincide em rótulo com os "checkpoints 11a-11f"/"checkpoints 11a-11e" das duas fases
anteriores - não confundir ao procurar contexto (mesma ressalva já registrada no início da
seção do Radar Imobiliário).

Regra não-negociável desta fase: um anúncio que desaparece nunca é chamado de "venda" ou
"imóvel vendido" em nenhum schema, endpoint ou string de UI - só "anúncio encerrado"/"saiu da
oferta". `tipo_valor` (Checkpoint 11) ganha o valor `'anuncio'` para todo preço desta fase,
sujeito à mesma trava de nunca misturar `tipo_valor` num agregado.

**Texto de referência completo salvo em `docs/prompt-referencia-radar-anuncios.md`** (recebido
do dono do projeto em 2026-08-16, depois de várias sessões citando "o prompt de referência"
sem ele estar em lugar nenhum recuperável do repositório). A partir daqui, qualquer sessão
retomando este produto deve ler esse arquivo primeiro, não inferir escopo a partir só deste
CLAUDE.md.

### Checkpoint 12a - Verificação e formalização das duas fontes: **concluído, com um veredito desfavorável**

As duas fontes (Apolar, Chaves na Mão) já haviam sido escolhidas pelo dono do projeto - este
checkpoint não foi seleção entre candidatos, foi verificação técnica (robots.txt, sitemap) e
legal (Termos de Uso) de cada uma, documentada em `docs/fontes-anuncios.md` antes de qualquer
conector existir. `docs/lia-anuncios.md` (avaliação de interesse legítimo LGPD) e
`docs/pedido-autorizacao-apolar.md` (rascunho de pedido de autorização, não enviado - enviar
mensagem em nome do projeto é ação que exige decisão e execução do dono do projeto) também
escritos, como exige a seção 7 do prompt de referência.

- **Apolar**: `robots.txt` totalmente aberto (`Disallow:` vazio), confirmado. Sitemap
  (`sitemap.xml`, 16.826 URLs) analisado de verdade, não só a lista de índices - **achado que
  corrige o prompt de referência**: o segmento de URL da operação de venda é `/venda/...`, não
  `/comprar/...` como o prompt assumia por analogia com `/alugar/...`. Contagem real de páginas
  de detalhe em Curitiba: 940 aluguel + 2.612 venda = 3.552. **Não existe página de Termos de
  Uso publicada** (verificado com Chrome real - o site é uma SPA renderizada no cliente,
  `curl`/fetch sem JS só devolve a casca vazia; rodapé real só lista Política de Cookies, sem
  nenhum link de Termos) - nenhuma cláusula contratual publicada proíbe nem autoriza scraping,
  o `robots.txt` aberto é o único sinal técnico direto. Sem e-mail institucional público, só um
  formulário de contato (`/fale-conosco/`) - pedido de autorização redigido, aguardando envio
  pelo dono do projeto. **Veredito: favorável no técnico, pendente no formal** - tratar como
  fonte sem autorização expressa (regras conservadoras da seção 7) até o pedido ser enviado e
  respondido.
- **Chaves na Mão**: `robots.txt` sem bloqueio geral a `User-agent: *`, mas com ~40 user-agents
  de ferramenta de download nomeados individualmente com `Disallow: /` (`wget`, `HTTrack`,
  `WebCopier`, etc.) e um bloco `Content-Signal` (TDM opt-out da Diretiva UE 2019/790, citado no
  próprio arquivo) reservando direito sobre uso automatizado. **Termos de Uso próprios,
  localizados e lidos de verdade** (`chavesnamao.com.br/termos-de-uso`) - confirmado que é
  entidade própria ("CHAVES NA MÃO LTDA.", CNPJ 43.853.784/0001-03, sede em Curitiba), não do
  Grupo OLX, exatamente a distinção que o prompt de referência pediu para verificar. Cláusula
  decisiva, na seção "Condutas vedadas na plataforma": **"Uso de bots, scripts automatizados,
  ferramentas de raspagem ou qualquer sistema que simule acesso humano"** - proibição explícita
  e sem ambiguidade de leitura, listada ao lado de outras condutas vedadas (documento falso,
  conteúdo impróprio). Sitemap também verificado tecnicamente (81 arquivos `.xml.gz` de venda +
  13 de aluguel, nacionais e não filtrados por cidade, 50.000 URLs cada; Curitiba confirmada
  presente via padrão `-pr-curitiba-` na URL, 588 ocorrências só no arquivo mais recente de
  venda) - a viabilidade técnica não é o problema, é a cláusula contratual. **Veredito:
  desfavorável.** Conforme a regra de decisão da seção 6.3 do prompt de referência: o conector
  `chavesnamao_anuncios` não entra em produção com este veredito - decisão de seguir mesmo
  assim (ex.: buscando autorização direta, já que a empresa forneceu volume de anúncios pra
  imprensa antes) fica com o dono do projeto, registrada e datada, nunca inferida.
- `docs/lia-anuncios.md`: separa explicitamente duas perguntas que o prompt de referência trata
  como uma só na prática - base legal LGPD (legítimo interesse, art. 7º IX) para processar o
  dado pessoal incidental numa página de anúncio (nome/telefone/CRECI do anunciante, descartados
  no parsing, nunca persistidos) É uma pergunta diferente de ter permissão contratual pra
  acessar o site de forma automatizada (Termos de Uso). O teste de balanceamento passa pras duas
  fontes na dimensão de dado pessoal - mas isso não supera o veredito de Termos de Uso
  desfavorável da Chaves na Mão, que é uma barreira independente.
- **Achado fora do escopo deste checkpoint, registrado para os próximos**: o modelo de dado da
  seção 8 do prompt de referência do Radar de Anúncios declara `fonte_id ... REFERENCES
  canonical.dim_fonte(fonte_id)`, mas o Checkpoint 11b já decidiu deliberadamente não ter uma
  tabela `dim_fonte` no projeto (`fonte_id` é texto livre sem FK em todo o resto do schema) -
  a mesma decisão provavelmente vale aqui, mas fica para o Checkpoint 12c (modelo/taxonomia)
  decidir, não é uma questão de verificação de fonte.

### Checkpoint 12c - Domínio e taxonomia: **concluído**

Numa sessão que foi interrompida por limite antes de fechar o checkpoint (o commit em disco
parou no 12a) - trabalho recuperado e fechado numa sessão seguinte, depois de conferir tudo
contra o estado real do repositório, não só contra este arquivo.

- `src/domain/anuncio/` - `ObservacaoAnuncio`/`ClusterImovel` (dataclasses puras),
  `taxonomia.py` (normalização de tipologia, mesmo padrão de `commerce/categories`),
  `impressao_digital.py` (assinatura determinística território+área+quartos+vagas+andar+
  condomínio, usada pra casar o mesmo imóvel entre as duas fontes), `resolucao.py`
  (`resolver_imoveis`/`CandidatoResolucao` - clustering por impressão digital dentro de uma
  janela de tempo, `JANELA_PADRAO_DIAS`), `regras.py` (`detectar_eventos_anuncio_par`,
  `detectar_anuncio_encerrado`, `detectar_reanuncio` - regra pura, sem I/O, mesmo padrão de
  `domain/event/regras.py`).
- Catálogo de eventos (`domain/event/models.py`) ganhou `ANUNCIO_PUBLICADO`,
  `ANUNCIO_ENCERRADO`, `PRECO_ALTERADO`, `REANUNCIO` (`entity_type="anuncio_imovel"`).
  `ANUNCIO_ENCERRADO` é sempre confiança "baixa" por natureza - um anúncio pode sair da oferta
  por venda, aluguel, retirada, expiração ou republicação com outro identificador,
  indistinguíveis de fora (mesma distinção que já separa `DESAPARECIMENTO` de
  `FECHAMENTO_CONFIRMADO` no Radar de Comércio). `REANUNCIO` entra como reservado - a regra
  que cruza um anúncio novo contra o histórico de `ANUNCIO_ENCERRADO` fica para o checkpoint
  12e, mesmo padrão de `FECHAMENTO_CONFIRMADO`/`TRANSACAO`/`LANCAMENTO`.
- 67 testes novos (`tests/domain/anuncio/`, `tests/lint/test_vocabulario_anuncio.py` - este
  último varre o código-fonte por strings proibidas tipo "venda confirmada"/"imóvel vendido"
  fora de contexto de operação, reforçando em teste automatizado a regra não-negociável desta
  fase: um anúncio que desaparece nunca é chamado de venda).

### Checkpoint 12d - Conectores, persistência e pipelines: **concluído, rodado contra as fontes reais**

- **`apolar_anuncios`** (`src/infrastructure/connectors/apolar_anuncios/`) - achado real: a
  Apolar é uma SPA em Vue renderizada 100% no cliente, `requests` sozinho só vê título/meta
  description, nunca preço/quartos/vagas/condomínio. `normalize()` usa Playwright (Chromium
  headless) pra renderizar cada página antes do parse - decisão confirmada com o dono do
  projeto (não é troca por endpoint interno de API, que a seção 7 do prompt de referência
  proíbe explicitamente; é a mesma página pública que qualquer visitante veria). `fetch()`
  continua HTTP puro (o sitemap é XML estático). Rate limit de 3s/req (`INTERVALO_MINIMO_S`).
- **`chavesnamao_anuncios`** (`src/infrastructure/connectors/chavesnamao_anuncios/`) - HTTP
  puro (site server-rendered), descoberta só por sitemap (94 arquivos `.xml.gz`), mesmo rate
  limit de 3s/req. Achado real de escala: 81.408 anúncios de Curitiba/PR - a 3s/req, coletar
  tudo levaria ~68h; o conector reporta essa estimativa e nunca tenta rodar de uma vez
  (`LIMIAR_HORAS_PARA_AVISAR`, mesmo padrão do checkpoint 9c/Nominatim).
- `canonical.dim_tipologia_imovel`, `canonical.observacao_anuncio`, `canonical.imovel_resolvido`,
  `canonical.imovel_resolvido_membro` - migração `95ec5cf9b2ae`, aplicada no Postgres local.
  `infrastructure/database/orm/dim_tipologia_imovel.py`/`observacao_anuncio.py` (as duas
  tabelas de `imovel_resolvido*` moram neste segundo arquivo, junto da tabela que elas
  referenciam) + `repositories/anuncio_repository.py`, `imovel_resolvido_repository.py`,
  `tipologia_repository.py`.
- `pipelines/ingestion/run_chavesnamao_anuncios.py`, `run_tipologias_imovel.py` e
  `pipelines/event_detection/run_anuncio.py` (detecta `ANUNCIO_PUBLICADO`/`PRECO_ALTERADO`/
  `ANUNCIO_ENCERRADO` comparando dois snapshots já ingeridos; `REANUNCIO` fica pro 12e, mesmo
  motivo do domínio acima) - todos retomáveis por design (mesmo padrão de `alvaras_smf`/
  geocodificação: um lote parcial ou interrompido continua de onde parou, sem re-coletar).
- **`pipelines/ingestion/run_apolar_anuncios.py`** - único pedaço que faltava pra fechar o
  checkpoint quando o trabalho foi retomado; escrito espelhando exatamente
  `run_chavesnamao_anuncios.py` (mesma estrutura de retomada via
  `listar_identificadores_fonte_com_observacao`, mesmo padrão de lote+`pipeline_run`).
- **Três problemas reais pegos só ao rodar contra o ambiente/site de verdade** (nenhum
  aparecia nos testes unitários, que usam sessão HTTP/renderizador fake):
  - Os 4 diretórios de teste novos desta fase (`tests/domain/anuncio/`, `tests/lint/`,
    `tests/infrastructure/connectors/{apolar,chavesnamao}_anuncios/`) não tinham `__init__.py`
    - diferente de todo outro diretório de teste do projeto -, o que quebrava a *coleta* do
    pytest inteira (`import file mismatch` entre `apolar_anuncios/test_connector.py` e
    `chavesnamao_anuncios/test_connector.py`, mesmo nome de módulo sem pacote pra
    desambiguar). Corrigido adicionando os `__init__.py` faltantes.
  - `apolar_anuncios/connector.py::_renderizador_playwright` tentava anexar um atributo
    (`.fechar`) a `sessao.renderizar`, um bound method - bound methods não têm `__dict__`
    próprio, então isso levanta `AttributeError` na primeira chamada real (só apareceu
    rodando contra o site de verdade; o teste unitário injeta uma função fake, que aceita o
    atributo sem problema). Corrigido envolvendo a chamada numa função solta antes de anexar
    `.fechar`.
  - **Violação real da seção 7 do prompt de referência, achada rodando a coleta completa em
    produção, não em teste.** Os dois conectores (`apolar_anuncios` e `chavesnamao_anuncios`)
    tinham um método `_salvar_html_bruto` que gravava a página HTML **inteira** (renderizada
    ou crua) em `data/raw/<fonte>/paginas/<id>.html` - violando de frente "Raw Zone sem
    conteúdo autoral... só campos estruturados... e um hash da URL" e "descarte de dado
    pessoal na ingestão... nem em Raw Zone, nem em log". Achado durante a coleta completa da
    Apolar em background: **954 páginas (270MB) já gravadas continham a string literal
    "CRECI"** (registro profissional do corretor/anunciante, dado pessoal sob a LGPD) antes de
    o problema ser notado e a coleta ser interrompida. Corrigido removendo
    `_salvar_html_bruto` dos dois conectores por completo (o dado estruturado já vai pro
    banco; não há necessidade de um dump paralelo da página inteira) - nenhum teste unitário
    testava o conteúdo desse método, então a remoção não quebrou nada (354 testes seguem
    passando). Todos os arquivos já gravados (`data/raw/apolar_anuncios/paginas/`,
    `data/raw/chavesnamao_anuncios/paginas/` - este segundo, resquício pequeno de ~4MB de uma
    tentativa anterior) foram apagados do disco local - nunca foram commitados
    (`data/raw/` é gitignored), então não há histórico git para limpar, só o disco local. As
    linhas já gravadas em `canonical.observacao_anuncio` não foram afetadas - só contêm campos
    estruturados desde sempre, o problema era exclusivamente o dump de HTML em paralelo.
    **Lição para as próximas fontes de coleta**: "não persistir X" precisa de verificação
    ativa (grep no disco depois de uma coleta real), não só uma docstring dizendo que X não é
    persistido - a documentação em `docs/lia-anuncios.md` já dizia a coisa certa o tempo todo,
    o código é que não seguia.
  - Depois das três correções: os **354 testes do projeto passam**.
- **Resolução entre fontes (seção 8.1) ganhou o pipeline que faltava**:
  `src/pipelines/resolucao/run_imovel_resolvido.py` (novo) - lê candidatos pendentes
  (`imovel_resolvido_repository.listar_candidatos_resolucao_pendentes`), agrupa via
  `domain.anuncio.resolucao.resolver_imoveis` (lógica pura, já testada desde o 12c) e grava em
  `canonical.imovel_resolvido`/`imovel_resolvido_membro`. Faltava só isso pra fechar 8.1 de
  ponta a ponta - o domínio e o repositório já existiam, só não havia nenhum script chamando
  os dois juntos. Idempotente (confirmado rodando duas vezes seguidas: segunda vez processa 0
  candidatos). **Rodado contra dado real, em duas passagens** (antes e depois da coleta
  completa da Apolar terminar): 813 candidatos → 761 clusters, depois mais 2.740 candidatos →
  2.541 clusters novos - total **3.302 clusters / 3.553 membros**, 0 com múltiplas fontes
  (esperado - só a Apolar coletou até agora; "provar a resolução entre fontes assim que a
  segunda estiver coletando", seção 11 do prompt de referência, fica pendente até a Chaves na
  Mão rodar).
- **Rodado contra as fontes reais - coleta completa da Apolar concluída**: smoke test inicial
  (5 páginas) validou preço/área/quartos/vagas/condomínio/andar corretos e `territorio_id`
  resolvido em 5 de 5. Coleta completa (~3.549 páginas de Curitiba, Playwright real, ~3h a
  3s/req) rodou em background - interrompida a ~929 páginas quando a violação de Raw Zone
  acima foi encontrada, corrigida, e reiniciada (retomou sozinha via
  `listar_identificadores_fonte_com_observacao`, sem re-coletar o que já estava em
  `observacao_anuncio`). **Resultado final: 3.545 de 3.549 páginas coletadas (99,9% -
  diferença são falhas de renderização isoladas, timeout de 30s, tratadas como não-fatais),
  96,3% (3.413) com `territorio_id` resolvido** contra `dim_territorio` (bairro já vem no slug
  da URL da Apolar, sem geocodificação nenhuma). Confirmação explícita do dono do projeto
  (2026-08-16): a coleta da Apolar pode continuar normalmente, sem esperar resposta ao pedido
  de autorização
  (seção 6.1/12a do prompt de referência já previa isso como não-bloqueante).
- **Chaves na Mão: bloqueio superado, primeiro lote real concluído.** O bloqueio original do
  classificador de modo automático do Claude Code (palpite: a cláusula de Termos de Uso que
  proíbe "bots, scripts automatizados, ferramentas de raspagem", `docs/fontes-anuncios.md`,
  seção 2) parou de acontecer depois que o dono do projeto obteve **autorização direta das
  duas empresas por conversa** (2026-08-16, registrado em `docs/fontes-anuncios.md` seção 2.1)
  - confirma que o palpite provavelmente estava certo, já que a mesma ferramenta que bloqueava
  antes passou a permitir sem nenhuma mudança de código. Smoke test (5 páginas) rodou limpo:
  preço/área/quartos/vagas/condomínio/IPTU corretos, bairro resolvido em 5 de 5, nenhum HTML
  bruto gravado (a correção da violação de Raw Zone, descrita acima, vale igualmente para os
  dois conectores). Descoberta real de escala: **81.934 anúncios de Curitiba** nos sitemaps -
  a 3s/req, coletar tudo levaria ~68h; um lote de 5.000 páginas (~4h) foi rodado em background
  por decisão do dono do projeto. **Concluído com sucesso**: 5.000 lidos, 5.000 gravados,
  status `sucesso` no `pipeline_run` - **5.013 observações totais de `chavesnamao_anuncios`**
  no banco (5 do smoke test + 5.000 do lote, mais um pequeno resto de reprocessamento de
  URLs já vistas), **95,9% (4.807) com `territorio_id` resolvido**. Volume de URLs "fora do
  padrão esperado" ao longo do lote (ex.: "ponto comercial" sem contagem de quartos no slug)
  ignoradas como já documentado no checkpoint 12d - não interrompeu a coleta. Resto dos
  ~77 mil anúncios ainda não coletados fica para lotes futuros, mesmo padrão retomável do
  pipeline (`listar_identificadores_fonte_com_observacao`) - decisão de quando rodar o
  próximo lote é do dono do projeto.

### Checkpoint 12b - Fontes gratuitas (QuintoAndar/FipeZAP): **concluído**

Antes desta sessão, a lacuna do 12b ("segue não iniciado") tinha um motivo não registrado -
esclarecido depois que o dono do projeto passou o texto completo do prompt de referência
(agora salvo em `docs/prompt-referencia-radar-anuncios.md`): a própria seção 12 (texto do
checkpoint 12a) já dizia "este checkpoint está satisfeito para as duas fontes; o 12d pode
prosseguir para ambas" - a sessão anterior não pulou o 12b por engano, o prompt já previa isso.

- **QuintoAndar - reaproveitamento puro, sem código novo**: o Índice QuintoAndar/Imovelweb de
  aluguel (`mkt.quintoandar.com.br/dados`, seção 9) é exatamente a mesma fonte já ingerida no
  Radar Imobiliário (checkpoint 11d,
  `infrastructure/connectors/quintoandar_aluguel`/`canonical.contexto_quintoandar_aluguel`) -
  princípio 1 do projeto (substrato compartilhado) aplicado de verdade, não só citado.
  `python -m pipelines.ingestion.run_quintoandar_aluguel` rodado de novo pra confirmar
  atualidade: **0 leituras novas gravadas** - achado real, não falha do pipeline: o CSV público
  da fonte não tem dado além de agosto/2025 (confirmado comparando `MAX(periodo_referencia)`
  antes/depois do re-run, idêntico) - a série está travada há um ano na origem, não no nosso
  lado. Registrado aqui como limitação de dado real, não investigado mais a fundo (não é um
  conector nosso que quebrou).
- **FipeZAP - conector novo** (`src/infrastructure/connectors/fipezap/`) - informe mensal só em
  PDF (`downloads.fipe.org.br/indices/fipezap/fipezap-<AAAAMM>-residencial-<venda|locacao>.pdf`),
  sem CSV nem API. Verificação técnica feita antes de escrever código (mesma disciplina do
  checkpoint 12a): `downloads.fipe.org.br` não publica `robots.txt` (redireciona pra uma página
  404 do site principal - sem restrição declarada); o download só funciona com um User-Agent
  próprio - o padrão do `requests` recebe 403 do WAF da Fipe (achado real, identificação honesta
  da seção 7 já resolve isso, não é evasão de bloqueio).
  - `src/domain/contexto/models.py` ganhou `IndicadorFipezapCidade`/`IndicadorFipezapBairro` -
    **uso estritamente interno, documentado na própria docstring**: a Fipe não publica licença
    de redistribuição (seção 9: "use internamente para validação... não redistribua sem
    escrever pra Fipe antes") - nenhuma rota de API pública lê essas tabelas.
  - `parsing.py` (puro, sem pdfplumber, testável com texto simples) - **achado real que mudou o
    desenho**: a tabela "capitais monitoradas" da mesma página, extraída via
    `page.extract_text()`, sai com a ordem dos caracteres embaralhada em alguns meses/operações
    (largura de coluna variável do PDF real) - confirmado comparando o relatório de venda
    (extrai limpo) contra o de locação do mesmo mês (embaralhado) de julho/2026. Contornado
    lendo os KPIs de cidade da prosa "DESTAQUES DO MÊS" (sempre limpa nos dois relatórios) em
    vez da tabela, via regex `Cidade\(([+-]X,XX%)\)` - a ausência de sinal `+`/`-` na
    rentabilidade do aluguel (a única outra métrica parentética na mesma prosa) já filtra esse
    quinto número sem tratamento especial.
  - Segundo achado real: a lista de "bairros mais representativos" (a própria Fipe declara no
    rodapé que não publica nada mais granular - "a Fipe não divulga informações detalhadas ou
    tabelas de preço médio por zona, distrito ou bairro") às vezes vem com rótulo de legenda de
    gráfico colado na mesma linha de uma linha de dado real (ex.: "Preço médio AGUA VERDE R$
    12.475 /m² +2,2%" - "Preço médio" é rótulo do gráfico ao lado, "AGUA VERDE..." é o dado).
    Regex de extração busca (não ancora no início da linha) e só aceita maiúscula/espaço no
    nome do bairro, o que já descarta o rótulo (tem minúscula) sem tratamento especial.
  - Terceiro achado real: nomes de bairro longos às vezes saem truncados com "…" no relatório
    de locação (`"CIDADE INDUSTRIAL DE…"`) mas não no de venda do mesmo mês
    (`"CIDADE INDUSTRIAL DE CURITIBA"` completo) - inconsistente até entre os dois relatórios
    do mesmo mês. `resolver_territorio_bairro` tenta o nome como veio; se truncado, casa por
    prefixo de slug contra `dim_territorio` e só resolve quando exatamente um bairro bate -
    prefixo ambíguo fica `None`, nunca um palpite.
  - `connector.py`: `fetch()` resolve o mês mais recente publicado tentando o corrente e
    retrocedendo (até 4 meses) - **achado real de robustez, encontrado rodando contra o site de
    verdade**: o mês corrente (ainda não publicado) às vezes devolve `403` em vez de `404` de
    forma inconsistente entre requisições (mesma URL, mesma sessão, minutos de diferença - um
    request manual isolado pra `202607` respondia `200` normalmente enquanto o pipeline, rodando
    logo em seguida, recebia `403` até para esse mesmo mês já publicado). Corrigido em duas
    camadas: backoff exponencial (`RETENTATIVAS_MAXIMAS = 3`, seção 7 do prompt de referência,
    "Backoff exponencial em erro") dentro de `_baixar_com_retentativa`, e - mais importante -
    qualquer falha persistente num mês (404 definitivo OU erro esgotado depois do retry) leva
    `_tentar_baixar_mes` a devolver `None` e `fetch()` cai pro mês anterior, em vez de abortar a
    busca inteira. Sem essa segunda camada, um 403 transitório no mês mais recente derrubava o
    conector por completo mesmo com meses mais antigos, já publicados, saudáveis.
  - `_extrator_paginas` injetável no `__init__` (mesmo padrão do `renderizador` de
    `apolar_anuncios`) - testa a orquestração de `normalize()` sem precisar construir um PDF
    binário de verdade.
  - `canonical.contexto_fipezap_cidade`/`contexto_fipezap_bairro` (migração `7dbe60ef606e`,
    aplicada) + `contexto_fipezap_repository.py` (idempotente por chave natural, mesmo padrão
    de `contexto_quintoandar_repository`). `pipelines/ingestion/run_fipezap.py` orquestra
    fetch→normalize→grava.
  - **Rodado contra a fonte real**: os dois PDFs de julho/2026 (venda + locação) baixados e
    verificados manualmente byte a byte contra o que a Fipe publica antes de escrever o parser.
    Depois de escrever o pipeline completo, uma tentativa de rodar `fetch()` de ponta a ponta
    contra o site ao vivo esbarrou no achado de `403` acima se repetindo em todos os 4 meses
    tentados (bem mais consistente que um blip isolado - sinal de que o volume de requisições
    desta sessão de investigação/desenvolvimento provavelmente disparou um rate-limit
    temporário do WAF da Fipe, não um bloqueio permanente). Decisão consciente de não insistir
    batendo no domínio (ritmo conservador, seção 7) - em vez disso, **`normalize()` +
    persistência foram verificados de ponta a ponta com os dois PDFs de julho/2026 já baixados
    localmente** (bypass só do `fetch()`/rede, não do parsing nem da gravação): 2 indicadores de
    cidade (venda R$11.761/m² +0,08%/+0,32%/+3,85%; locação R$48,91/m² +0,57%/+5,14%/+9,17%,
    todos batendo com leitura manual do PDF) e 20 indicadores de bairro (10 por operação),
    **100% (20/20) com `territorio_id` resolvido** contra `dim_territorio` - incluindo o caso
    truncado "CIDADE INDUSTRIAL DE…" resolvido corretamente por prefixo. 22 registros gravados
    no banco real, `pipeline_run` registrado manualmente pra refletir essa execução híbrida.
    Rodar `python -m pipelines.ingestion.run_fipezap` de ponta a ponta contra a rede (sem
    nenhum PDF pré-baixado) fica pendente pra quando o rate-limit da Fipe arrefecer - o código
    já tem retry/fallback de mês pra lidar com isso sozinho quando isso acontecer.
- 29 testes novos (`tests/domain/contexto/` ampliado, `tests/infrastructure/connectors/fipezap/`
  novo - parsing puro com texto real extraído dos PDFs reais, conector com sessão HTTP fake).
  Total do projeto: **385 testes Python passando**. `alembic check` sem drift novo (só o já
  documentado desde o checkpoint 8). Trabalho deste checkpoint rodou em paralelo com a coleta
  da Chaves na Mão (checkpoint 12d, ver acima) em background, sem conflito - processos e
  tabelas independentes.

### Checkpoint 12e - Ciclo de vida: **parcial, com um bloqueio real de calendário registrado**

Este checkpoint tem duas partes independentes na seção 12 do prompt de referência: (1)
segundo/terceiro snapshots com `ANUNCIO_ENCERRADO`/`PRECO_ALTERADO`/`REANUNCIO` funcionando, e
(2) calibração contra ONR e QuintoAndar (seções 1.1 e 9). A primeira esbarra numa restrição de
calendário real que nenhuma sessão consegue contornar - registrada aqui antes de fingir que não
existe.

- **`REANUNCIO` implementado e wireado** (faltava desde o checkpoint 12d, que já tinha deixado
  isso reservado explicitamente). `anuncio_repository.buscar_encerrados_recentes_por_impressao`
  (novo) - dado um conjunto de impressões digitais candidatas, acha o `ANUNCIO_ENCERRADO` mais
  recente (dentro de `JANELA_PADRAO_DIAS`, reaproveitada de `domain.anuncio.resolucao` - mesmo
  conceito de "janela razoável" da seção 8.1, sem inventar um segundo número) cuja observação de
  origem bata, via join por `origem_observacoes[1]` (mesmo padrão já usado por
  `construcao_repository` no Radar Imobiliário). Nunca considera impressões
  `PLACEHOLDER_SEM_FINGERPRINT` (`"sem-fp:..."`, anúncios sem área útil suficiente) - mesma
  exclusão que já valia pra resolução entre fontes. Busca é **cross-fonte de propósito**: o
  mesmo imóvel físico pode reaparecer em qualquer uma das duas fontes, não só na mesma.
  `pipelines/event_detection/run_anuncio.py` reescrito para resolver "anúncios novos" (sem
  observação anterior) **em lote** (uma consulta por lote de `TAMANHO_LOTE`, não uma por
  anúncio) contra essa função, decidindo `REANUNCIO` vs `ANUNCIO_PUBLICADO` - mesma leitura "mais
  específica do mesmo fato, não um evento adicional" já usada em
  `ABERTURA_CONFIRMADA`/`PRIMEIRA_OBSERVACAO` (Radar de Comércio, checkpoint 3).
  - **Validação sem pytest, mesmo padrão já estabelecido no projeto** (nenhum repositório deste
    projeto tem teste unitário dedicado - só domínio puro e conectores com sessão fake são
    testados via pytest; repositórios são verificados contra o banco real e documentados aqui).
    Rodado numa transação aberta e nunca commitada (rollback no fim, nada persistido) contra o
    banco real: evento sintético de `ANUNCIO_ENCERRADO` inserido apontando pra uma observação
    real existente → a consulta encontra a correspondência certa (entidade + preço); fora da
    janela → não encontra; impressão placeholder → nunca entra. Os três ramos confirmados.
  - **Rodado de verdade contra dado real, não só sintético**: um achado incidental abriu uma
    janela genuína pra isso - `canonical.observacao_anuncio` tinha 8 registros residuais de
    `chavesnamao_anuncios` datados de 2026-08-15 (resquício de uma tentativa anterior a esta
    sessão, antes do bloqueio de autorização ser resolvido), ao lado dos 5.005 de 2026-08-16.
    Rodar `python -m pipelines.event_detection.run_anuncio chavesnamao_anuncios 2026-08-15
    2026-08-16` de ponta a ponta contra o banco real produziu **5.001 eventos reais gravados**:
    4.999 `ANUNCIO_PUBLICADO`, 2 `ANUNCIO_ENCERRADO` (dos 8 antigos, só 2 não apareceram no
    snapshot novo) - `REANUNCIO` não disparou nenhuma vez nessa amostra (esperado, com só 2
    encerrados e volume pequeno, nenhuma coincidência de impressão digital). Não é o cenário
    real do produto (snapshots deveriam ser semanais, não de um dia pro outro, e o resíduo de
    8 registros é minúsculo) - mas prova que o código roda de ponta a ponta contra dado real
    sem erro, incluindo o caminho novo de `REANUNCIO`.
- **Bloqueio real de calendário, não contornável**: `ANUNCIO_ENCERRADO`/`PRECO_ALTERADO`/
  `REANUNCIO` em escala de produto exigem dois snapshots semanais reais e completos das duas
  fontes - isso significa dias/semanas de calendário passando entre execuções da coleta, não
  algo que uma sessão consiga produzir sozinha revisitando o mesmo dia. O achado dos 8 registros
  residuais acima prova que o *mecanismo* funciona; não substitui os snapshots de verdade.
  Próximo passo real: rodar `run_apolar_anuncios.py`/`run_chavesnamao_anuncios.py` de novo
  daqui a uma semana (ou quando o dono do projeto decidir), depois `run_anuncio.py` pra cada
  fonte comparando as duas datas.
- **Calibração contra ONR (seção 1.1) - achado real que diverge do prompt de referência**:
  investigação técnica direta no Portal Estatístico Registral
  (`registrodeimoveis.org.br/portal-estatistico-registral`, verificado com Chrome real, não só
  `WebFetch`) mostra que a página **não expõe** a série de "volume mensal de atos de
  transferência" como CSV baixável, ao contrário do que a seção 1.1 do prompt de referência
  descreve ("publicado de graça... CSV, série desde 2017"). O que a página realmente expõe com
  exportação de CSV ao vivo são só **Usucapião Extrajudicial** e **Recuperação de Crédito**
  (execução extrajudicial de devedor fiduciante) - filtráveis por UF/comarca/serventia/ano/mês,
  2017-2026. O indicador de compra-e-venda que o prompt de referência quer (o que apareceu no
  achado do checkpoint anterior, "Curitiba +14,7%" etc.) só existe publicado como **notícia
  narrativa periódica** (ex.: "Indicadores de transações imobiliárias - Janeiro/24", artigo de
  blog, não dado estruturado) - o link que a própria notícia dá como "relatório completo" volta
  pro mesmo Portal Estatístico que não tem esse indicador em CSV. Não encontrado (buscado
  também `/dados-abertos`, que redireciona pra home) nenhum outro caminho de dado estruturado
  pra esse indicador específico. **Calibração contra ONR fica bloqueada até uma investigação
  mais profunda** (ex.: contato direto com o RIB perguntando se existe um caminho de dado bruto
  não descoberto, mesmo padrão do pedido de autorização já redigido pra Apolar) - decisão de
  investir nisso, ou aceitar calibrar só contra QuintoAndar (aluguel), é do dono do projeto.
- **Calibração contra QuintoAndar (seção 9) - também bloqueada, mas por dado de anúncio, não
  por fonte**: tecnicamente possível desde o checkpoint 12b (o índice já está no banco,
  atualizado até ago/2025), mas a métrica em si ("descolamento entre pedido e contratado")
  precisa do preço pedido mediano de aluguel calculado a partir de anúncios reais - que
  depende do mesmo bloqueio de calendário acima (`ANUNCIO_PUBLICADO`/estoque de aluguel real
  precisa de volume real coletado, que já existe via a coleta desta sessão, mas a série
  temporal de preço pedido precisa de mais de um ponto no tempo pra fazer sentido como
  "descolamento", não um single snapshot).
- Nenhum teste novo de pytest (mesma nota acima - a mudança é em repositório/pipeline, testados
  contra o banco real, não com fixture). **385 testes Python seguem passando** (nenhuma
  regressão). `alembic check` sem drift novo.

### Checkpoint 12f - Termômetro: **concluído para o que dado real sustenta hoje**

Seção 2 do prompt de referência (9 métricas por bairro × tipologia × operação × mês, quadrante
de aquecimento na seção 2.1, piso de amostra na seção 2.2). Mesma disciplina do checkpoint 12e:
construir tudo, deixar rodar contra dado real, e não fingir que métricas que dependem de
histórico têm um número quando não têm.

- `src/analytics/features/anuncio_termometro.py` (novo, puro, sem I/O) - uma função pequena por
  métrica (mesmo estilo de `indicadores.py`, não uma função gigante fazendo tudo):
  `contar_novos_anuncios` (soma `ANUNCIO_PUBLICADO`+`REANUNCIO` - mesmo raciocínio já usado pra
  `aberturas` no Radar de Comércio, checkpoint 8: `REANUNCIO` é uma leitura mais específica do
  mesmo fato "entrou na oferta", não uma categoria à parte), `calcular_novos_por_mil_domicilios`,
  `calcular_rotacao_oferta`, `calcular_renovacao`, `calcular_permanencia_mediana`,
  `calcular_pressao_preco`, `calcular_estatistica_preco` (mediana/P25/P75 via
  `statistics.quantiles`, reaproveitada tanto pra preço quanto pra preço/m²),
  `classificar_quadrante_aquecimento` (as 4 leituras nomeadas da seção 2.1 - `aquecendo`/
  `otimismo_nao_validado`/`ajustando`/`desacelerando`, `None` quando falta qualquer uma das
  duas variações de entrada, nunca um palpite com metade da informação). `PISO_MINIMO_AMOSTRA
  = 30` (seção 2.2) - abaixo disso, mediana/P25/P75 viram `None` com
  `motivo_indisponivel="amostra_insuficiente"`, a contagem crua continua visível. 22 testes.
- `infrastructure/database/repositories/termometro_repository.py` (novo) -
  `consultar_estoque_e_precos_ativos` (uma linha por cluster resolvido ainda ativo - exclui
  entidades com `ANUNCIO_ENCERRADO` já gravado, nunca conta o mesmo imóvel físico duas vezes,
  seção 8.1) e `consultar_contagem_eventos_por_celula` (tipos de evento por bairro/tipologia/
  operação/mês, lidos do `payload` JSONB do evento, sem precisar voltar em
  `observacao_anuncio`). `substituir_termometro` - mesmo padrão `DELETE`+`INSERT` de
  `analytics.contagem_eventos` (checkpoint 5).
- `canonical` → `analytics.termometro_anuncio` (migração `1cb9bccb596b`, aplicada) +
  `analytics/features/run_termometro_anuncio.py` (orquestra: busca estoque/eventos/domicílios,
  monta células em Python via `_montar_linhas` - 10 testes puros cobrindo montagem, amostra
  insuficiente, `REANUNCIO` contando como novo, células só-com-evento sem estoque atual,
  território `None`, mês errado sendo ignorado - grava). `python -m
  analytics.features.run_termometro_anuncio`.
- **Limitação de dado real, documentada na própria tabela/módulo, não escondida**: rotação da
  oferta, renovação, permanência mediana, pressão de preço e o quadrante de aquecimento ficam
  `NULL` em toda célula hoje - todas exigem histórico (estoque de início de mês, ciclos de vida
  completos, ou baseline de 3+ meses via `calcular_baseline`/`calcular_tendencia`, reaproveitadas
  do checkpoint 8, mas que exigem `MINIMO_MESES_BASELINE=3`) que ainda não existe, mesmo bloqueio
  de calendário já registrado no checkpoint 12e. `novos_anuncios`/`encerrados`/`estoque`/preço
  são reais hoje porque não dependem de mais de um ponto no tempo.
- **Achado real, corrigido antes de confiar no resultado**: a primeira execução do pipeline
  contra o banco real devolveu só 14/760 células com amostra suficiente e um estoque total de
  3.300 - suspeito, dado que só a Apolar (3.545 observações) tinha passado pela resolução entre
  fontes (checkpoint 12c/8.1) desde a coleta completa; o lote de 5.000 da Chaves na Mão (rodado
  no checkpoint 12d desta sessão) nunca tinha sido re-resolvido depois de gravado - confirmado
  contando `imovel_resolvido_membro` por `fonte_id`: 3.545 Apolar, só 14 Chaves na Mão.
  Corrigido rodando `python -m pipelines.resolucao.run_imovel_resolvido` de novo (4.999
  candidatos pendentes → 4.348 clusters novos, ainda 0 multi-fonte - achado à parte, registrado
  mas não investigado a fundo: as duas fontes não têm nenhuma sobreposição de imóvel físico
  detectada ainda, plausível dado que são fontes de natureza diferente - uma imobiliária única
  vs. um agregador multi-imobiliária). Depois da correção: **estoque total 7.648** (batendo
  com a soma real das duas fontes), **44/760 células com amostra suficiente**.
- **Achado real de infraestrutura de teste, corrigido**: a primeira tentativa de rodar a
  suíte completa depois deste checkpoint quebrou 52 testes de `tests/api/` com
  `NoReferencedTableError` - `observacao_anuncio.py` declara FK pra `dim_tipologia_imovel`/
  `entidade`/`dim_territorio` mas nunca importava esses módulos ele mesmo, confiando em quem
  importasse por fora já ter registrado tudo em `Base.metadata` (um registro global por
  processo). `tests/api/conftest.py` nunca precisou de `observacao_anuncio` antes, então nunca
  importava `dim_tipologia_imovel` - até `termometro_repository.py` (este checkpoint) importar
  `observacao_anuncio` numa sessão de teste que também roda `create_all()` pros testes de API,
  expondo a lacuna. Corrigido não em `conftest.py` (adicionar tabelas que a API não usa seria
  escopo indevido), mas na fonte: `observacao_anuncio.py` e `termometro_anuncio.py` agora
  auto-importam os módulos ORM dos quais dependem via FK, garantindo a invariante "se esta
  classe está registrada, os alvos dos FKs dela também estão" independente de quem importa
  primeiro. 417 testes voltaram a passar, confirmado estável em duas rodadas seguidas.
- **Rodado contra o banco real** (depois da correção de resolução acima): 760 células
  (bairro×tipologia×operação), estoque total 7.648, 4.999 novos anúncios/2 encerrados (mesmos
  números do checkpoint 12e). Preços batem com o padrão já visto no FipeZAP (checkpoint 12b) -
  Batel lidera preço de aluguel de apartamento (R$5.900 mediano), Centro lidera volume (355
  apartamentos de aluguel em estoque, 306 salas comerciais) - mesma hierarquia de bairro cara/
  bairro denso já confirmada por uma fonte totalmente independente.
- 32 testes novos (`tests/analytics/features/test_anuncio_termometro.py`,
  `test_run_termometro_anuncio.py`). Total do projeto: **417 testes Python passando**.
  `alembic check` sem drift novo (só o já documentado desde o checkpoint 8).

### Checkpoint 12g - Leitura cruzada: **concluído para o que dado real sustenta hoje**

Seção 3 do prompt de referência ("a seção que diferencia o produto"). Código vive em
`src/analytics/features/cross/` e `infrastructure/database/repositories/cross_repository.py` -
fora de `commerce/` e de qualquer pacote específico do Radar de Anúncios, porque é leitura
sobre o substrato compartilhado (`dim_territorio`), não integração nova.

- **3.1 Defasagem cruzada** (`cross/defasagem.py`, puro) - `calcular_correlacao_cruzada`
  testa `2×lag_maximo+1` defasagens (padrão 12, então 25 no total) via correlação de Pearson,
  com **intervalo de confiança corrigido por Bonferroni** (`n_testes` explícito, nunca
  inferido às escondidas - transformação de Fisher + `statistics.NormalDist().inv_cdf(...)`
  pro z crítico, sem precisar de scipy) - primeira trava obrigatória da seção 3.1
  ("aplique correção para múltiplas comparações... publique intervalo de confiança").
  `PISO_MINIMO_MESES_SOBREPOSTOS = 12` - terceira trava (piso de amostra). Série constante
  (variância zero) fica indisponível, nunca vira `r=0` (zero afirmaria "sem relação", que é
  informação diferente de "não dá pra medir"). `cross/servico_defasagem.py` implementa a
  primeira trava por completo: `analisar_defasagem_por_bairro` **só roda se
  `analisar_defasagem_cidade` achou uma defasagem significativa** - "resultado válido, não uma
  falha" quando não acha, mesma linguagem do checkpoint 12e/12f. 11 testes (inclui um caso
  sintético com lag verdadeiro conhecido - série não-periódica via `sin(i)` com `i` inteiro,
  índice não múltiplo de π, pra não colidir com o próprio lag testado por aliasing - onde a
  correlação encontrada bate exatamente com o lag construído, `r≈1.0`).
- **3.2 Quadrante cruzado** (`cross/quadrante_cruzado.py`, puro) - 4 rótulos descritivos
  (`movimento_nos_dois_lados`/`comercio_cresce_oferta_escassa`/`oferta_cresce_comercio_parado`/
  `movimento_baixo_nos_dois_lados`), nunca avaliativos - `None` quando falta qualquer um dos
  dois eixos. 6 testes.
- **3.3 Coincidência espacial fina** (`cross_repository.consultar_coincidencia_espacial`) -
  **achado real que mudou o desenho**: nenhuma entidade `tipo_entidade='anuncio_imovel'` tem
  linha em `canonical.geolocalizacao_entidade` (0 confirmado por query direta) - o Radar de
  Anúncios nunca geocodificou nada, só resolve bairro (checkpoint 12c/12d). Isso torna "raio de
  N metros" literal impossível pro lado do anúncio hoje. Em vez de inventar um ponto aproximado
  (ex.: centroide do bairro fingindo ser geocodificação), o resultado reporta os dois lados com
  **granularidades explicitamente diferentes**: comércio via raio real (reaproveita
  `eventos_no_raio`, checkpoint 9d/11d, ponto-a-ponto de verdade) e anúncio por bairro inteiro
  (resolvido via `ST_Contains` do ponto contra `dim_territorio.geometria`) - nunca escondido
  atrás de um número só, mesma disciplina de transparência de fonte/granularidade já usada em
  `/imoveis/contexto` (Radar Imobiliário) e na seção 1.2 (Radar de Anúncios).
- **Achado real, corrigido antes de confiar em qualquer resultado** - o mais importante deste
  checkpoint: a primeira execução do relatório contra o banco real (`run_leitura_cruzada.py`)
  encontrou uma defasagem "significativa" em lag=0 (r=-0,568, IC95 não continha zero) - exame
  manual mostrou que era exatamente a correlação espúria que a seção 3.1 pede pra evitar.
  Causa: `series_novos_anuncios_todos_bairros`/`serie_novos_anuncios_cidade` zero-preenchiam a
  série de anúncio (~40 meses), mas a série real só tem **1 mês** de profundidade (mesmo
  bloqueio de calendário do checkpoint 12e/12f) - os ~39 zeros fabricados criavam contraste
  artificial contra o único mês real, não um sinal de verdade. Violava um princípio que o
  próprio projeto já tinha estabelecido em outro lugar (`feature_repository.
  consultar_saldo_mensal_todos_bairros`: "ausência de mês significa 'não processamos essa
  comparação', não 'zero'") - só não tinha sido aplicado aqui na primeira versão. Corrigido
  removendo o zero-fill dessas duas funções (mês sem evento de anúncio simplesmente não entra
  na série, deixando `_alinhar_series` pareá-la corretamente só onde há dado real dos dois
  lados) - depois da correção, o relatório passou a reportar corretamente "amostra
  insuficiente" e nenhuma defasagem por bairro é calculada, exatamente o resultado honesto
  esperado dado o histórico real disponível.
- `cross/run_leitura_cruzada.py` - relatório (não grava nada, não há endpoint/tela ainda,
  checkpoint 12i) que imprime os dois resultados. **Rodado contra o banco real**: 3.1 reporta
  corretamente "nenhuma defasagem significativa - amostra insuficiente" (40 meses de comércio
  com dado real via `contagem_inicio_atividade`, só 1 mês de anúncio); 3.3 no ponto já usado
  pela busca por raio do checkpoint 9d (AV. PRESIDENTE WENCESLAU BRAZ, 1893) devolve 818
  aberturas/165 desaparecimentos de comércio num raio de 1km (últimos 12 meses) e 942 novos
  anúncios no bairro Centro (que contém o ponto) - números plausíveis, Centro já confirmado
  como o bairro de maior volume tanto no checkpoint 12f quanto aqui.
- 17 testes novos (`tests/analytics/features/cross/` - `test_defasagem.py`,
  `test_servico_defasagem.py`, `test_quadrante_cruzado.py`). Total do projeto: **434 testes
  Python passando**. `alembic check` sem drift novo (nenhuma tabela nova neste checkpoint -
  tudo lido ao vivo, mesmo raciocínio de `eventos_no_raio`).

### Checkpoint 12h - Pressão especulativa: **concluído para o que dado real sustenta hoje**

Seção 5 do prompt de referência - 5 indicadores mensuráveis, cada um nomeado pelo que é
("o produto não pode chamar nada de especulação"). `src/analytics/features/
pressao_especulativa.py` (puro, 5 dataclasses + 5 funções, 15 testes) +
`infrastructure/database/repositories/pressao_especulativa_repository.py` (consultas reais) +
`run_pressao_especulativa.py` (relatório, mesmo padrão de `cross/run_leitura_cruzada.py` - não
grava nada, sem endpoint/tela ainda).

- **Indicador 1 (reanúncio com preço maior)**: `calcular_taxa_reanuncio` - taxa =
  `REANUNCIO ÷ ANUNCIO_ENCERRADO` na mesma janela de `domain.anuncio.resolucao.
  JANELA_PADRAO_DIAS` (reaproveitada, não um número novo); mediana do incremento usa só as
  variações **positivas** dos `REANUNCIO` (a seção 5 pede especificamente "preço maior", não
  toda variação de reanúncio).
- **Indicador 2 (preço subindo sem contrapartida física)**: `avaliar_preco_sem_contrapartida_fisica`
  cruza variação de preço (baseline) com `ALVARA_APROVADO`/`OBRA_CONCLUIDA`/
  `ZONEAMENTO_ALTERADO` do Radar Imobiliário no bairro - "aqui o Checkpoint 11 finalmente vira
  insumo analítico, não decoração" (seção 5), literal.
- **Indicador 3 (oferta alta com ocupação baixa)**: `calcular_oferta_por_domicilio_vago` -
  estoque de anúncios ativos (cluster resolvido, nunca conta duplicado) ÷ domicílios
  particulares vagos do Censo 2022. **Achado real, corrigido antes de rodar**:
  `contexto_censo_repository.consultar_agregado_por_bairro` (Radar Imobiliário, checkpoint
  11e) somava população/domicílios totais/ocupados/área, mas nunca `domicilios_particulares_vagos`
  - a coluna já existia em `ContextoCensoSetor` desde o checkpoint 11d, só não estava na
  agregação por bairro porque nenhum indicador tinha precisado dela até agora. Estendida
  aditivamente (chave nova no dict de retorno, `CensoBairroOut` ignora chaves extras por
  padrão do Pydantic - conferido que os 12 testes de `tests/api/test_imoveis.py` continuam
  passando antes de seguir).
- **Indicador 4 (concentração de anunciante)**: `calcular_concentracao_ofertante` (% dos
  anúncios ativos vindo dos 5 ofertantes mais frequentes, nunca o hash em si na saída - só a
  contagem). **Achado real, documentado, não escondido**: `ofertante_hash` existe no schema
  desde o checkpoint 12c mas **nenhum dos dois conectores o popula** - `apolar_anuncios`/
  `chavesnamao_anuncios` nunca extraem/hasheiam identificação de anunciante do HTML. Este
  indicador sempre reporta `amostra_insuficiente` (0 ofertantes) até isso ser corrigido nos
  conectores - lacuna de coleta, não bug desta consulta nem deste checkpoint.
- **Indicador 5 (descolamento entre pedido e contratado)**: `calcular_descolamento_pedido_contratado`
  - único dos 5 sem nenhum bloqueio de calendário, porque não depende de baseline nem de
  histórico de anúncio, só de um snapshot atual (preço pedido mediano de aluguel por m², cidade
  inteira) contra o índice QuintoAndar (checkpoint 12b). **Achado real a interpretar com
  cautela**: razão calculada = 0,93 (preço pedido R$42,58/m² **abaixo** do índice QuintoAndar de
  R$45,99/m²) - resultado contraintuitivo à primeira vista (esperava-se pedido ≥ contratado),
  mas o índice QuintoAndar usado está travado em ago/2025 (achado do checkpoint 12b: a fonte
  não publica dado mais recente) enquanto o preço pedido é de ago/2026 - **um ano de defasagem
  entre as duas pontas da comparação**, não uma leitura limpa do mesmo período. Registrado
  como está, sem ajustar o número pra "parecer certo" - a razão calculada bate com os dados reais
  disponíveis, a ressalva de defasagem temporal é que precisa acompanhar o número em qualquer
  tela futura (checkpoint 12i).
- **Rodado contra o banco real**: indicador 1 (0 reanúncios / 2 encerrados, taxa 0,0 - mesmos 2
  eventos do checkpoint 12e); indicador 2 (Centro e Batel têm `houve_contrapartida=True` via
  eventos reais de obra, variação de preço aguardando baseline); indicador 3 (Batel lidera com
  0,379 estoque/domicílio vago, Centro tem o maior estoque absoluto - 1.078 - mas razão menor
  por ter mais domicílios vagos também); indicador 4 (0, confirma o achado de coleta);
  indicador 5 (razão 0,93, conforme acima).
- 15 testes novos (`tests/analytics/features/test_pressao_especulativa.py`). Total do projeto:
  **449 testes Python passando**. `alembic check` sem drift novo (nenhuma tabela nova - tudo
  lido ao vivo ou de tabelas já existentes).

### Checkpoint 12i - Interface: **concluído para o que dado real sustenta hoje**

Primeiro checkpoint desta fase a tocar `apps/api`/`apps/web`. Seção 10 do prompt de referência -
adaptada à mesma realidade de dado documentada nos checkpoints 12e-12h: quadrante de
aquecimento, variação de preço/estoque, permanência mediana e leitura cruzada por bairro ficam
`None` em toda tela hoje (dependem de baseline histórica que só existe depois de mais
snapshots semanais reais) - a interface declara isso explicitamente em vez de esconder ou
fabricar.

- **Backend** (`apps/api/routers/anuncios.py`, novo) - três endpoints:
  - `GET /anuncios/termometro?operacao=...&tipologia=...` - estoque e preço pedido (mediana/
    P25/P75) por bairro, base do mapa. Lê **ao vivo** de `consultar_estoque_e_precos_ativos`
    (checkpoint 12f), não da tabela materializada `analytics.termometro_anuncio` - achado de
    desenho: mediana não soma entre tipologias, então "todos os tipos" precisa recalcular do
    preço bruto, não somar medianas já calculadas por célula (`anuncio_interface_repository.py`,
    novo).
  - `GET /anuncios/bairros/{id}/resumo` - painel de bairro, reaproveita `consultar_metricas_construcao`/
    `consultar_valor_venal_mediano_por_bairro` (Radar Imobiliário) pro contexto, em vez de
    duplicar essas consultas.
  - `GET /anuncios/procedencia` - Apolar e Chaves na Mão sempre separadas (seção 1.2).
  - **Achado real, corrigido antes de rodar os testes de API**: `contexto_censo_repository.
    consultar_agregado_por_bairro` precisou ganhar `domicilios_particulares_vagos` na agregação
    (checkpoint 12h) - a extensão é aditiva e `CensoBairroOut` ignora chaves extras por padrão
    do Pydantic, mas só ficou confirmado seguro rodando os 12 testes existentes de
    `/imoveis/contexto` antes de seguir, não por suposição.
  - `tests/api/conftest.py` ganhou seed própria de anúncio (30 aluguéis em Batel - o piso
    mínimo de amostra da seção 2.2 exigiu pelo menos 30 pontos pra exercitar o caminho "amostra
    suficiente" em teste, 5 não bastava - e 2 vendas em Centro pra exercitar "amostra
    insuficiente" e "bairro sem estoque"). 9 testes novos (`tests/api/test_anuncios.py`).
- **Frontend** (`apps/web/src/app/anuncios/`, `components/anuncios-*.tsx`, novo) - reaproveita
  pesadamente a biblioteca de componentes já existente do Radar Imobiliário
  (`ImoveisChoroplethMap`, `SequentialLegend`, `FatoTile`, `Headline`, `MethodologyTooltip`) -
  nenhum componente de mapa/legenda escrito do zero.
  - Mapa colorido por **preço pedido mediano** (rampa sequencial), não pelo quadrante de
    aquecimento que a seção 10 pede - o quadrante depende de baseline que não existe pra
    nenhum bairro ainda (mesmo bloqueio dos checkpoints 12f/12g); a legenda diz isso
    explicitamente ("quadrante de aquecimento aparece aqui assim que houver histórico
    suficiente"), nunca finge a coloração pretendida.
  - **Terceira correção da seção 10 implementada desde o início** (não como correção depois):
    a legenda declara quantos bairros ficaram de fora por amostra insuficiente ("42 de 72
    bairros... os outros 30 aparecem em cinza").
  - **Primeira correção da seção 10 implementada desde o início**: no painel de bairro, cada
    métrica indisponível (variação 12m, variação de estoque, permanência, quadrante, leitura
    cruzada) é uma linha de texto discreta com o motivo, nunca um `FatoTile` de peso visual
    cheio fingindo ter dado - o padrão que a seção 10 pede pra tirar do resto do produto entrou
    aqui já correto, em vez de precisar de uma correção futura (mesma classe de bug já
    registrada nos checkpoints 10d/11f do Radar Imobiliário, que regrediu uma vez).
  - **Segunda correção da seção 10 aplicada ao contexto de construção**: "valor venal mediano
    (PGV)" vem com o rótulo "referência para IPTU, não é preço de mercado" ao lado do número,
    visível, não em tooltip.
  - Só três dos quatro controles da seção 10 (operação/tipo de imóvel/bairro) - "período" fica
    de fora de propósito: o termômetro é um snapshot do estoque agora, não uma série filtrável
    por data ainda (mesma simplificação já usada nas abas Valor de referência/Zoneamento do
    Radar Imobiliário, que também não são série temporal).
  - Manchete editorial computada com dado real (nunca fabricado): "5.004 imóveis para alugar
    anunciados agora em Curitiba, com preço mediano confiável em 42 de 72 bairros" - não o
    "8% acima de um ano atrás" do exemplo do prompt de referência, que exigiria uma variação
    que não existe ainda.
  - Navegação cruzada: link "Radar de Anúncios" adicionado ao cabeçalho do Radar de Comércio,
    do Radar Imobiliário e de `/comparacao`; terceiro CTA em `/` - mesmo padrão já estabelecido
    no checkpoint 11f quando o Radar Imobiliário ganhou frontend próprio.
- **Achado real durante a verificação visual, investigado e descartado como não sendo do meu
  código**: a primeira checagem no navegador mostrou o mapa principal em branco (só o fundo
  cinza, sem coroplético nem basemap) tanto em `/anuncios` quanto - crucialmente - em `/imoveis`
  e `/radar`, duas telas que já funcionavam e que esta sessão não tocou. Investigação (rede,
  console, WebGL, interceptação do construtor `Worker` - mesma técnica já documentada no
  checkpoint 9f-9g) não achou nenhum erro: o estilo, os tiles e o worker (`maplibre-gl-worker.mjs`,
  confirmado presente e servindo `HTTP 200` via `curl`) todos carregavam; o canvas WebGL só não
  tinha pintado nenhum pixel ainda na hora da checagem. Depois de mais alguns segundos e
  interações (trocar de aba, abrir um `Select`), o mapa apareceu corretamente nas três telas,
  com coloração e dado batendo com o esperado (Batel mais escuro/caro, mesma hierarquia já
  confirmada por FipeZAP no checkpoint 12b) - **conclusão: pintura simplesmente mais lenta que
  o esperado nesta sessão** (múltiplos restarts de `next dev` e limpeza de cache `.next`
  aconteceram nela), não um bug de código - mas registrado aqui porque reproduziu de forma
  consistente o suficiente pra valer a pena documentar, caso apareça de novo numa sessão
  futura com mais tempo pra investigar a fundo.
- Workaround de IP de LAN (ver Notas operacionais) usado pra verificação visual - `next.config.ts`
  revertido antes de finalizar (nunca foi commitado antes, dev-only).
- **Rodado contra o banco/API/frontend reais**: `/anuncios` renderiza a manchete, os três
  filtros, o mapa (coroplético + legenda com contagem de amostra insuficiente), o painel de
  bairro (Batel: R$6.950,00 mediano, 246 em estoque, faixa P25-P75 R$3.500,00-R$12.740,30, 30
  alvarás/13 CVCOs/R$4.912,64 de contexto) e o painel de procedência (Apolar 3.545 observados/
  94,2% tipologia/96,3% bairro; Chaves na Mão 5.013/87,7%/95,9%) - todos com dado real,
  conferidos um a um no navegador. `npm run build`/`lint`/`tsc` limpos.
- 9 testes novos de API. Total do projeto: **458 testes Python passando**.

**Radar de Anúncios (checkpoints 12a-12i) concluído** - as três fontes (Apolar, Chaves na Mão,
FipeZAP) coletando, o ciclo de vida do anúncio (`ANUNCIO_PUBLICADO`/`PRECO_ALTERADO`/
`ANUNCIO_ENCERRADO`/`REANUNCIO`) funcionando, termômetro/leitura cruzada/pressão especulativa
implementados e testados, interface própria em `/anuncios`. **O que ainda depende só de tempo
de calendário passando, não de código**: baseline histórica (3+ meses) pra variação/quadrante/
rotação/permanência/leitura cruzada por bairro virarem números reais em vez de "amostra
insuficiente" - precisa de snapshots semanais reais se acumulando, documentado desde o
checkpoint 12e e não escondido em nenhuma tela. Dois gaps reais que dependem de decisão do dono
do projeto, não de tempo: `ofertante_hash` nunca populado pelos conectores (checkpoint 12h) e
calibração contra ONR bloqueada por a fonte não publicar o dado em CSV (checkpoint 12e).

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
- **Depois de processar um novo snapshot de alvarás**, duas features derivadas precisam ser
  recomputadas manualmente, nessa ordem (nenhuma roda automaticamente hoje):
  `python -m analytics.features.run_contagem_eventos` (checkpoint 5) e
  `python -m analytics.features.run_contagem_inicio_atividade` (checkpoint 8, otimização de
  2026-08-12). Esquecer a segunda não quebra nada visivelmente - o ranking e o painel de
  detalhe de bairro continuam respondendo rápido, só ficam com dado desatualizado (a query
  antiga, ao vivo, foi removida - não há mais um fallback lento-mas-atualizado).
- `uvicorn --reload` mostrou-se instável nesta máquina durante a sessão de 2026-08-12
  (checkpoint 8b) - processos órfãos ficaram escutando a porta 8000 servindo código velho
  depois de reinícios sucessivos, mascarando bugs reais por um tempo até serem percebidos via
  `netstat`. Rodar sem `--reload` e reiniciar manualmente a cada mudança de backend é mais
  confiável neste ambiente.
