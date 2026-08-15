# Verificação de fontes — Radar Imobiliário (Checkpoint 11a)

Data da verificação: 2026-08-15.

Método: consulta direta aos endpoints REST do GeoCuritiba/IPPUC (`curl`/`f=json`, incluindo
schema de campos por layer) e submissão real do formulário do relatório da SMU (POST com
`__VIEWSTATE`/`__EVENTVALIDATION`, replicando o postback ASP.NET). Nenhum código de produto foi
escrito — este documento é o resultado da seção 2 do prompt de referência.

**Nota sobre a primeira rodada desta verificação**: a primeira passagem havia concluído,
incorretamente, que o relatório da SMU estava fora do ar e que a PGV só tinha camadas de
zoneamento sem valor monetário. As duas conclusões estavam erradas — erro de investigação, não
da fonte:
- O relatório da SMU falhou nas minhas duas primeiras tentativas (`curl` direto e Chrome real)
  porque ambas foram feitas contra HTTPS/porta 443, que não responde neste host — o servidor só
  atende em HTTP/porta 80 (confirmado depois com `curl -v`: a porta 443 dá timeout, a porta 80
  responde 302 normalmente). A ferramenta de fetch usada na primeira tentativa também
  auto-upgrada HTTP para HTTPS por padrão, mascarando o problema.
- A PGV foi consultada na URL certa desde o início, mas eu só li a lista de layers do
  `MapServer` raiz (que não mostra campos) e concluí, por suposição a partir dos *nomes* das
  duas layers, que nenhuma delas carregava valor monetário. Não cheguei a consultar o schema de
  campos da layer 0 — que de fato tem o valor unitário de terreno.

Registrado aqui porque é o tipo de erro que se repete se não for nomeado: **confundir "meu
método de verificação falhou" com "a fonte não existe"** — exatamente o risco que o dono do
projeto apontou ao revisar a primeira versão deste documento. As duas fontes abaixo foram
re-verificadas com o método correto e **nenhuma das duas está bloqueada**.

---

## 1. Relatório Mensal Alvará/CVCO (SMU)

**URL**: `http://www5.curitiba.pr.gov.br/gtm/pmat_alvaraconstrucao/relatoriomensalalvara.aspx`
(HTTP puro, porta 80 — a porta 443 não responde neste host, o que causou a falsa conclusão de
indisponibilidade na primeira passagem).

**Status: existe, responde e tem saída em lote.** Confirmado ponta a ponta: baixei a página do
formulário via `curl`, extraí os campos ASP.NET obrigatórios (`__VIEWSTATE`,
`__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`) e repliquei o `POST` que o botão "Gerar Relatório"
dispara — a mesma requisição que o navegador do usuário faria.

**Formulário** (`Default.aspx`, GET carrega o form, POST gera o relatório):
- `rblRelacao` — rádio, dois valores mutuamente exclusivos: `1` = "Alvará da Construção",
  `2` = "Certificado de Vistoria de Conclusão de Obra (CVCO)". **Os dois relatórios são
  fontes/telas separadas no próprio sistema**, confirmando a distinção `ALVARA_APROVADO` vs.
  `OBRA_CONCLUIDA` do catálogo de eventos deste checkpoint.
- `ddlAno` — ano, 1900 a 2026 (dropdown completo, sem sentido usar nada antes de ~2000 na
  prática, mas o sistema aceita).
- `ddlMes` / `ddlMesFinal` — mês inicial e final (permite pedir um intervalo dentro do mesmo
  ano num único request, ex.: Jan-Jul).

**Saída**: `POST` devolve um arquivo `.xls` (`Content-Type: application/vnd.ms-excel`, HTML
formatado como planilha do Excel — não é XLSX binário, é HTML/MSO, mesmo padrão usado por
sistemas ASP.NET antigos; parseável com `pandas.read_html` ou parsing de tabela HTML direto,
sem precisar de biblioteca de Excel). Testado com "Alvará da Construção", ano 2026, Jan-Jul:
**2.215 linhas**, 12,97MB. Testado com "CVCO", mesmo período: **1.393 linhas**, 8,3MB.

**Colunas do relatório de Alvará da Construção** (34 colunas — muito mais rico que o prompt de
referência assumia):

`Indicação Fiscal`, `Inscrição Imobiliária`, `Data Criação Alvará`, `Data Início Obra`,
`Data Conclusão Obra`, `Logradouro`, `Número`, `Bairro`, `Grupo Zoneamento`, `Abrangência`,
`Quantidade Pavimentos`, `Quantidade de Unidades Residenciais`,
`Quantidade Unidades Não Residenciais`, `Número Alvará`, `Uso(s) Alvará`, `Sub-Uso(s) Alvará`,
`Finalidade`, `Material(is)`, `Metragem Área Remanescente`, `Metragem Construída Lote`,
`Número de CAPACs Utilizadas`, `ACA-Área Adicional de Construção`, `Área Liberada`,
`Metragem Área Reforma Alvará`, `Quantidade Blocos Alvará`, `Quantidade Sub-Solo Alvará`,
`Autor do Projeto`, `Número Registro Crea/Cau AU`, `Responsável Técnico`,
`Número Registro Crea/Cau RT`, `Firma Construtora`, `Número CVCO`, `Tipo Vistoria`,
`Data Vistoria`. O relatório de CVCO tem as mesmas 34 colunas mais `Área Vistoria` (35 no
total).

**Achados que mudam o desenho, todos favoráveis**:

1. **`Indicação Fiscal` e `Inscrição Imobiliária` são as mesmas chaves que
   `Publico_GeoCuritiba_MapaCadastral` (`gtm_ind_fiscal`/`gtm_insc_imob` da camada "Lote
   Cadastral", já confirmada na seção 3) — junção direta por chave exata, sem geocodificação
   nenhuma, para resolver `territorio_id`/zoneamento por lote.** Isso é mais forte do que o
   pipeline de comércio, que precisa geocodificar endereço.
2. **`Quantidade Pavimentos` e `Metragem Construída Lote` já vêm no próprio relatório de
   alvará/CVCO.** Isso muda a seção 3.3 do prompt: não é preciso a camada "Edificação" do
   GeoCuritiba (que, como a seção 3 abaixo confirma, não existe) para ter área
   construída/pavimentos — o dado vem direto da fonte de licenciamento, por evento, o que é
   inclusive mais correto (área licenciada/concluída por obra, não um snapshot de estoque).
3. **O relatório de Alvará da Construção já carrega `Número CVCO`, `Tipo Vistoria` e
   `Data Vistoria`** — ou seja, dá para ver o par alvará→CVCO da mesma linha quando a obra já
   foi concluída, sem precisar cruzar os dois relatórios por chave. Útil para calcular a
   "defasagem mediana entre alvará e CVCO" (seção 5) direto de uma fonte, com o relatório de
   CVCO como conferência/cobertura adicional (nem toda obra concluída necessariamente aparece
   com o vínculo preenchido do lado do alvará).
4. **Volume real**: ~316 alvarás de construção/mês e ~199 CVCOs/mês, medidos em dado real (não
   estimativa) — ordem de grandeza tratável para pipeline mensal, nada perto do volume do CSV de
   alvará de funcionamento (500 mil+ linhas).

**Não verificado ainda, fica para o checkpoint 11c**: profundidade histórica real por trás do
dropdown 1900-2026 (o dropdown aceita o intervalo, mas isso não garante que haja dado
consistente desde 1900 — precisa testar um ano antigo antes de assumir cobertura), e
performance/estabilidade do servidor sob requisições em lote (é um sistema ASP.NET antigo,
IIS 6.0 — não tem indício de rate limit documentado, mas o pipeline deve tratar isso como uma
fonte frágil, com retry, no mesmo espírito do GeoCuritiba).

**Licença**: nenhum texto de termos de uso encontrado nesta tela específica do sistema
`www5.curitiba.pr.gov.br`. O portal de dados abertos geral (`dadosabertos.curitiba.pr.gov.br`)
declara "Conteúdo licenciado sob uma Licença Creative Commons" no rodapé, mas esse sistema é
separado do portal de dados abertos (não está listado lá — confirmado buscando "alvará" no
catálogo, que só retorna a "Base de Alvarás" da SMF, o dataset de funcionamento comercial já
usado no Radar de Comércio, sem nenhuma relação com este relatório de construção). Vale
perguntar à SMU explicitamente sobre a licença antes de publicar dado derivado desta fonte.

---

## 2. Planta Genérica de Valores (IPPUC)

**URLs verificadas**:
- Visualizador: `http://geoapp.ippuc.org.br/plantagenericadevalores/`
- Serviço REST: `https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/Publico_GeoCuritiba_Planta_Generica_Valores/MapServer` (nota: o path correto tem o segmento `GeoCuritiba/` antes do nome do serviço — o prompt de referência omitia esse segmento).
- Shapefile em lote: `http://ippuc.org.br/geodownloads/SHAPES/PGV.zip` (achado durante a
  verificação, linkado a partir do visualizador — sem autenticação).

**Sai em lote?** Sim, pelo serviço REST espacial mesmo — sem precisar do shapefile do
visualizador. `.../MapServer/0?f=json` (layer "Microrregião (PGV 2025)") devolve o schema de
campos direto, sem autenticação, mesmo padrão `resultOffset`/`resultRecordCount` já usado em
`geocuritiba_bairro`.

**O que a layer 0 contém, confirmado por query real** (`/MapServer/0/query?where=1=1&outFields=*`):
- **1.062 feições, geometria polígono, `wkid 31982`** (SIRGAS2000/UTM22S — mesmo sistema de
  todas as outras camadas do GeoCuritiba, sem o problema de CRS desconhecido que o shapefile
  legado do visualizador tem).
- Campos: `chave`, `sg_zona`/`nm_zona` (eixo/zona), `cd_microbairro`, `nm_bairro` (chave de
  junção direta com `dim_territorio`), `cd_microrregiao`, `cod_vukt` e **`vukt` — Valor
  Unitário Característico de Terreno, em R$/m², o valor venal de referência de fato**.
  Confirmado num registro real: `CAPÃO DA IMBUIA`, `vukt = 1304.99`.
- Existe também a layer `id 1` ("Índice de Infraestrutura Urbana (PGV 2025)") — um índice
  correlato, não verificado em detalhe neste checkpoint (não é `valor_m2`, fica para quando/se
  o produto precisar dele).

**Granularidade real: microrregião (1.062 polígonos), não face de quadra nem lote.** O prompt
de referência citava "~306 mil pontos por face de quadra" — esse número existe (é o
`PGV.zip`, shapefile legado do visualizador, inspecionado abaixo), mas não é o dado vigente. O
dado vigente e rotulado "PGV 2025" no próprio serviço é por microrregião. É uma granularidade
mais grossa do que o prompt imaginava, mas é: atual, tem CRS correto, e é consultável sem
fricção — ajustar o schema (`valor_referencia_territorial.geometria`) para receber um polígono
de microrregião em vez de um ponto de face de quadra é o desvio de desenho real aqui, não um
bloqueio.

**Achado à parte, mantido por transparência**: o shapefile legado (`PGV.zip`, linkado no
visualizador em `http://ippuc.org.br/geodownloads/SHAPES/PGV.zip`, sem autenticação) *também*
existe e tem 300.214 pontos por `INSC_IMOB` (lote) com série anual `V2002`...`V2017` — mas está
parado em 2017, sem `.prj` (CRS não identificável — só 0,008% dos pontos caem numa caixa
delimitadora plausível de Curitiba) e sem separar terreno de construção. **Não usar este
arquivo** como fonte de `ippuc_pgv` — ele é uma base histórica descontinuada, não a "PGV 2025"
vigente. Mantido documentado aqui só para não ser redescoberto do zero numa sessão futura.

**Componente terreno/construção**: `vukt` é só terreno (o próprio nome diz "Valor Unit.
Característico de **Terreno**"). Não há campo de valor de construção nesta layer — consistente
com o padrão de PGV municipal no Brasil (a componente de construção normalmente vem de uma
tabela de coeficientes por padrão construtivo, não geoespacial, e pode não estar publicada em
aberto). `ippuc_pgv` deve gravar só `componente='terreno'` por enquanto; `componente='construcao'`
fica pendente até uma fonte para essa tabela ser localizada (fora do escopo verificado aqui).

**Licença**: nenhum texto de licença ou termos de uso encontrado na página do visualizador nem
no serviço REST — mesma lacuna documentada para a fonte 1.

**Conclusão**: fonte viável, atual e sem bloqueio técnico. O único ajuste de desenho é a
granularidade (microrregião, não face de quadra/lote) e o escopo (`componente='terreno'`
apenas, por ora).

---

## 3. Camada Edificação (GeoCuritiba MapaCadastral)

**URL verificada**: `https://geocuritiba.ippuc.org.br/server/rest/services/GeoCuritiba/Publico_GeoCuritiba_MapaCadastral/MapServer/23?f=json`
(nota: mesmo ajuste de path do item 2 — falta o segmento `GeoCuritiba/` na URL do prompt de
referência; usei a base já confirmada como correta pelo conector `geocuritiba_bairro` existente,
que consulta `.../GeoCuritiba/Publico_GeoCuritiba_MapaCadastral/MapServer/2`.)

**A layer 23 não existe.** Consultei o `MapServer` raiz do serviço (`?f=json`) e listei as 41
layers reais que ele expõe. Os ids pulam de 22 ("Área de Ocupação Irregular") direto para 25
("Zoneamento", group layer) — **não existe nenhuma layer chamada "Edificação" em lugar nenhum
do serviço**, sob nenhum id.

**Não há, em nenhuma camada pública do GeoCuritiba, atributo de área construída, número de
pavimentos, ano de construção ou uso do imóvel.** As camadas mais próximas são de lote/quadra,
não de edificação:

| id | nome | geometria |
|----|------|-----------|
| 15 | Lote Cadastral | polígono |
| 16 | Lote Cadastral - Texto IF e Num Predial | polígono |
| 17 | Quadra Cadastral | polígono |
| 18 | Lote Físico - Implantado | polígono |
| 19 | Sublote Físico - Implantado | polígono |
| 20 | Testada Lote Físico - Implantado | linha |
| 21 | Quadra Física - Implantada | polígono |

Nenhuma delas carrega área construída/pavimentos — confirmado lendo o schema de campos de cada
uma via `?f=json`.

**Boa notícia, achada na mesma varredura**: as camadas que o prompt pede explicitamente para o
conector `geocuritiba_cadastro` existem e batem exatamente com os nomes de campo citados.

- **Lote Cadastral (id 15)** — 308.882 feições. Campos confirmados por query real:
  `gtm_ind_fiscal`, `gtm_insc_imob`, `gtm_mtr_area_terreno`, `gtm_nm_bairro`,
  `gtm_sigla_zoneamento` — todos presentes, exatamente como o prompt de referência especifica.
  Geometria em `wkid 31982` (SIRGAS2000/UTM22S) — o mesmo sistema já usado com sucesso pelo
  conector `geocuritiba_bairro` existente (checkpoint 1); o código de reprojeção já escrito é
  reaproveitável sem adaptação.
- **Quadra Cadastral (id 17)** — 16.606 feições.
- **Zoneamento Lei 15.511/2019 (id 36)** — 223 feições, campos `data_versao` e
  `data_atualizacao` confirmados — exatamente o que o prompt precisa para o "achado bônus"
  opcional de detectar `ZONEAMENTO_ALTERADO` por diff de versão sem diffing geométrico.
- `maxRecordCount` do serviço é 2000 (igual ao já tratado em `geocuritiba_bairro`) — mesmo
  padrão de paginação por `resultOffset`/`resultRecordCount` já implementado é diretamente
  reaproveitável.

**Conclusão**: a parte "o que se pode construir ali" (zoneamento + lote cadastral) do
checkpoint está confirmada e é a mais simples das três fontes — dá para implementar com o
padrão de conector já existente, sem achado bloqueante. A camada "Edificação" propriamente dita
(footprint/estoque construído já existente, para cruzar com domicílios do Censo na métrica 6)
**não existe como camada espacial no GeoCuritiba** — mas, como a seção 1 mostra, o relatório de
Alvará/CVCO da SMU já carrega `Quantidade Pavimentos` e `Metragem Construída Lote` por evento de
licenciamento. Não é a mesma coisa (é fluxo de obras licenciadas, não um snapshot de estoque
construído existente), mas cobre a maior parte do que a métrica 6 precisava sem precisar de uma
camada que não existe — decisão de desenho para o checkpoint 11e, não um bloqueio novo.

---

## O que isso muda no desenho

Resumo por fonte (versão final, depois da correção registrada no topo deste documento):

| Fonte | Sai em lote? | Situação |
|---|---|---|
| Alvará/CVCO (SMU) | Sim — `POST` no formulário devolve `.xls` (HTML/MSO) por ano+intervalo de mês, até 34-35 colunas | Viável. Só HTTP (porta 80), não HTTPS. Sem licença declarada nesta tela específica. |
| PGV (IPPUC) | Sim — REST paginado, `MapServer/0`, sem autenticação | Viável. Granularidade real é microrregião (1.062 polígonos), não face de quadra/lote; só `componente='terreno'` por ora. |
| Zoneamento + Lote Cadastral (GeoCuritiba) | Sim, REST paginado, mesmo padrão já usado | Viável, confirmado sem ressalvas. |
| Edificação (camada dedicada, GeoCuritiba) | N/A | A camada não existe — mas o relatório de Alvará/CVCO da fonte 1 já carrega pavimentos/área construída por evento, cobrindo a maior parte da necessidade original. |

Nenhuma das três fontes está bloqueada. Os ajustes de desenho, todos favoráveis ou neutros:

- **11b (domínio/schema)**: `valor_referencia_territorial.geometria` recebe polígono de
  microrregião (não ponto de face de quadra) para a fonte `ippuc_pgv`; nenhuma mudança de
  schema necessária além disso — o campo `componente` já previa `'terreno'` como valor válido.
- **11c (conectores do núcleo)**: os três seguem como planejado —
  `smu_alvaras_construcao` (via POST replicando o formulário, parseando o `.xls` HTML/MSO
  devolvido — sem scraping de tela, é o mesmo mecanismo que o botão "Gerar Relatório" já expõe),
  `ippuc_pgv` (REST, granularidade microrregião), `geocuritiba_cadastro` (lote + quadra +
  zoneamento, sem ajuste). `smu_alvaras_construcao` deve tratar o servidor como frágil (IIS 6.0
  antigo, sem indício de rate limit documentado) com o mesmo padrão de retry já usado no
  GeoCuritiba.
- **Métrica 6 da seção 5** ("densidade construtiva... cruzando footprint com domicílios") pode
  ser aproximada com `Metragem Construída Lote`/`Quantidade Pavimentos` do relatório de
  Alvará/CVCO, agregado por bairro — é fluxo de obras licenciadas, não um snapshot de estoque
  construído existente (rotular isso claramente na UI/metodologia, não apresentar como
  "footprint total"), mas usa dado real de uma fonte confirmada, não um proxy inventado.
- Os três novos tipos de evento da seção 3.1 (`ALVARA_APROVADO`, `OBRA_CONCLUIDA`,
  `ALVARA_DEMOLICAO`) têm fonte real confirmada — `ALVARA_APROVADO`/`OBRA_CONCLUIDA` mapeiam
  direto para os dois relatórios (Alvará da Construção / CVCO); `ALVARA_DEMOLICAO` precisa ser
  conferido no checkpoint 11c — não ficou claro nesta verificação se demolição aparece como um
  terceiro tipo de relação no mesmo sistema ou se está em outro lugar (`rblRelacao` só ofereceu
  os dois valores testados; vale checar se há mais opções que não apareceram no HTML estático,
  ou se demolição é um `Uso(s) Alvará`/`Finalidade` dentro do próprio relatório de alvará).

Seguindo para o checkpoint 11b completo, depois 11c com os três conectores do núcleo, conforme
direcionado.
