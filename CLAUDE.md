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

## Todos os 5 checkpoints da sequência original estão concluídos

Conforme o plano original: **parar aqui e aguardar revisão antes de seguir para API ou
front-end** — nenhum dos dois tem dado maduro o suficiente para valer a pena construir em
cima ainda. Se for retomar depois de uma revisão, os candidatos naturais de continuação (não
solicitados, apenas o que ficaria disponível) seriam: ampliar a cobertura de
`cnae_categoria_map` além dos 79 códigos atuais, tratar `FECHAMENTO_CONFIRMADO` quando uma
segunda fonte existir, ou começar `apps/api/` como uma camada fina sobre `analytics.features`.

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
