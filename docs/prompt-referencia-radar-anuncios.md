# Prompt de referência — Radar de Anúncios

Texto de referência completo para a implementação do Radar de Anúncios (checkpoints 12a-12i),
fornecido pelo dono do projeto em 2026-08-16. Sessões anteriores citavam este documento como
"prompt de referência" sem ele estar salvo no repositório — este arquivo existe para que isso
pare de acontecer. Ver `CLAUDE.md`, seção "Radar de Anúncios", para o registro de qual
checkpoint implementa qual parte deste texto e quais desvios/achados reais surgiram na prática.

---

## 0. A tese do produto

O anúncio é um termômetro de mercado, não um registro contábil. Quando um imóvel é anunciado,
alguém decidiu que agora é hora de vender ou alugar naquele lugar, por aquele preço. Quando o
anúncio some rápido, o mercado absorveu. Quando o preço pedido sobe e os anúncios continuam
parados, alguém está pedindo mais do que o mercado aceita. Nada disso depende de saber se a
escritura foi lavrada.

Essa é uma escolha deliberada, e vale registrá-la como escolha: o produto mede intenção e
movimento de mercado, com atualização semanal, em vez de medir transação consumada com meses
de defasagem e cobertura pública inexistente em Curitiba. É um dado diferente, mais rápido e
mais granular — não um substituto pior.

O que o produto entrega, em ordem de importância:

1. Quais bairros estão aquecendo e quais estão desacelerando — pela dinâmica da própria oferta.
2. Quanto custa, por bairro e por tipo de imóvel — aluguel e venda, com série no tempo.
3. A leitura cruzada com o Radar de Comércio — onde abre negócio, aparece anúncio? Em que
   ordem? Esta é a leitura que nenhum concorrente consegue fazer, porque exige os dois lados
   no mesmo substrato territorial.
4. Indicadores associados a pressão especulativa — medidos e nomeados com precisão, nunca
   rotulados como "especulação" (seção 5).

## 1. A disciplina de linguagem que sustenta tudo

O produto pode dizer muita coisa sobre oferta. Não pode dizer uma: que um imóvel foi vendido.
Um anúncio que desaparece pode ter vendido, alugado, sido retirado, expirado ou republicado com
outro identificador — indistinguíveis do lado de fora. É a mesma distinção que já separa
DESAPARECIMENTO de FECHAMENTO_CONFIRMADO no Radar de Comércio.

Isso não limita o produto que você quer construir — nenhuma das perguntas da seção 0 exige
transação. Limita apenas o vocabulário:

| Não escreva | Escreva |
|---|---|
| "vendas no bairro" | "anúncios encerrados" ou "rotação da oferta" |
| "imóveis vendidos" | "imóveis que saíram da oferta" |
| "preço de venda" | "preço pedido" |
| "valorização" | "aumento do preço pedido" |
| "especulação" | o indicador específico medido (seção 5) |

Implemente como restrição estrutural: um teste de lint textual sobre schema, endpoints e
strings de UI falha se aparecer "vendido", "venda concretizada", "transacao" ou "valorização".
Barato de escrever, e impede regressão quando o produto crescer.

Reaproveite o enum `tipo_valor` do Checkpoint 11: todo preço de anúncio entra como `'anuncio'`,
e o teste que proíbe misturar `tipo_valor` num mesmo agregado continua valendo.

### 1.1 Calibração — como ganhar o direito de falar sobre transação

Some os anúncios encerrados de venda por mês e compare com o volume mensal de atos de
transferência do município, publicado de graça pelo Portal Estatístico Registral do ONR
(registrodeimoveis.org.br, CSV, série desde 2017). Publique a correlação e a razão entre as
séries dentro do produto.

Se a correlação for forte e estável, o produto passa a poder dizer: "anúncios encerrados —
indicador que acompanha o volume de transferências registrais do município, correlação X no
período Y". Isso é uma afirmação forte, citável e auditável. Se não for, o produto diz só
"anúncios encerrados". Em nenhum cenário o número vira "vendas".

### 1.2 Atribuição de fonte, sempre visível — regra obrigatória, não opcional

Com duas fontes de coleta coexistindo, é fácil o produto virar uma média silenciosa entre
Apolar e Chaves na Mão sem que ninguém consiga saber de onde veio um número. Isso é proibido.
A regra:

- Todo dado de anúncio carrega `fonte_id` na origem (já previsto no schema, seção 8) — isso
  não é novo. O que é novo é que a atribuição precisa sobreviver até a interface e até a API,
  não morrer na agregação.
- Todo tile, gráfico, linha de ranking e frase-manchete que usa dado de anúncio exibe a fonte
  visivelmente, na própria peça de UI — não em tooltip, não só no painel de procedência.
  Quando um número combina as duas fontes, o rótulo diz isso explicitamente (ex.: "Apolar +
  Chaves na Mão") e não apenas "anúncios".
- Quando as duas fontes contribuem para o mesmo agregado, a resposta de API devolve a
  composição — quantos registros vieram de cada `fonte_id` e, se a diferença de nível de preço
  entre as duas for grande o suficiente para mudar a leitura, isso é sinalizado (ex.: uma das
  fontes tem viés sistemático de imóvel mais alto padrão). Não é preciso resolver isso com um
  modelo estatístico agora — é preciso não escondê-lo.
- Um mesmo imóvel anunciado nas duas fontes ao mesmo tempo não pode contar duas vezes em
  estoque, novos anúncios ou qualquer contagem de volume — ver a resolução por
  `impressao_digital` na seção 8.1. Quando isso acontecer, a interface mostra "anunciado em:
  Apolar e Chaves na Mão" no imóvel resolvido, em vez de tratar como dois imóveis.
- Endpoint dedicado de transparência por fonte: `GET /imoveis/fontes-anuncio` devolve, por
  fonte, contagem de anúncios ativos, data do último snapshot e cobertura por bairro. É a
  versão programática do painel de procedência (seção 10), e existe para que a atribuição de
  fonte não dependa de alguém abrir uma tela específica para descobrir.

## 2. O termômetro — quais bairros estão aquecendo

Estas são as métricas centrais do produto. Todas por bairro × tipologia × operação × mês, em
`src/analytics/features/`, reaproveitando a máquina de baseline do Checkpoint 8.

| Métrica | Fórmula | Leitura |
|---|---|---|
| Novos anúncios | contagem de `ANUNCIO_PUBLICADO` no mês | entrada de oferta |
| Novos anúncios por 1.000 domicílios | novos anúncios ÷ (domicílios do Censo 2022 ÷ 1.000) | entrada de oferta corrigida pelo tamanho do bairro |
| Estoque anunciado | anúncios ativos no último dia do mês | tamanho da oferta |
| Rotação da oferta | anúncios encerrados no mês ÷ estoque no início do mês | quão rápido a oferta se renova |
| Renovação (churn) | (novos + encerrados) ÷ estoque médio | intensidade de movimento, independente da direção |
| Permanência mediana | mediana de dias entre publicação e encerramento | melhor indicador isolado de aquecimento |
| Pressão de preço | % de anúncios ativos com `PRECO_ALTERADO` para cima vs. para baixo, e a mediana da variação | quem está reajustando, e para onde |
| Preço pedido mediano | mediana de `preco`, com P25 e P75 | nível |
| Preço pedido por m² | mediana de `preco` / `area_util_m2` | nível comparável entre bairros |

A normalização por domicílios não é opcional. Sem ela, bairro grande sempre lidera qualquer
ranking de volume, e o produto vira uma lista de bairros populosos. O Censo 2022 já traz
domicílios por setor censitário, agregáveis a bairro.

### 2.1 O quadrante de aquecimento — em vez de um score composto

O impulso natural é criar um "Índice de Aquecimento: 87/100". Não crie. Um score composto
exige pesos arbitrários que ninguém consegue defender, e cai direto na proibição já vigente no
produto contra score sem fórmula publicada.

Em lugar disso, classifique cada bairro num quadrante de duas dimensões, ambas medidas e ambas
explicáveis: variação do preço pedido e variação da permanência mediana, cada uma contra a
própria baseline histórica do bairro.

| | Permanência caindo (mercado absorve mais rápido) | Permanência subindo (mercado absorve mais devagar) |
|---|---|---|
| Preço pedido subindo | Aquecendo — sobe preço e ainda assim sai rápido | Otimismo não validado — pede mais, mercado não acompanha |
| Preço pedido caindo | Ajustando — cedeu no preço e destravou | Desacelerando — cede no preço e ainda assim demora |

Quatro leituras nomeadas, cada uma derivada de dois números visíveis na tela, sem peso
arbitrário nenhum. O quadrante "otimismo não validado" é o mais valioso comercialmente: é onde
um corretor descobre que o cliente dele está pedindo caro demais, e é um insight que nenhum
índice de preço médio revela.

Isto é material legítimo para o Signal Engine previsto na arquitetura — sinal nomeado, por
regra explícita, com confiança declarada e rastreável até os números que o geraram. Implemente
lá, não como cálculo solto na camada de apresentação.

### 2.2 Piso de amostra

Célula (bairro × tipologia × operação × mês) com menos de 30 anúncios não exibe mediana, não
entra em ranking e não recebe classificação de quadrante. Mostre "amostra insuficiente" — nunca
um número frágil, nunca célula vazia sem explicação. Bairros abaixo do piso podem aparecer numa
lista separada com o total agregado de todas as tipologias, se houver volume para isso.

## 3. A leitura cruzada — comércio e imóveis no mesmo território

Esta é a seção que diferencia o produto. Os dois radares já produzem série mensal por bairro
sobre o mesmo `dim_territorio`; cruzar é uma feature de análise, não uma integração nova.

Onde o código vive: em `src/analytics/features/cross/` (ou pasta equivalente), não dentro de
`commerce/` nem de um pacote de produto imobiliário. É uma leitura sobre o substrato
compartilhado — exatamente o que a arquitetura previu quando disse que todo produto é uma
leitura sobre o mesmo event store. Se essa feature acabar importando código específico de um
produto, o desenho está errado.

### 3.1 Defasagem cruzada

Para cada bairro, e para a cidade inteira, calcule a correlação cruzada com defasagem entre a
série mensal de aberturas de comércio e a série mensal de novos anúncios de imóvel, em
defasagens de 0 a 12 meses, nas duas direções. Reporte a defasagem de correlação máxima.

Isso responde literalmente a pergunta "em bairro onde novos negócios estão abrindo, aparecem
também novos anúncios de imóvel?" — e responde melhor do que um sim/não, porque diz em que
ordem e com quanto atraso.

Três travas obrigatórias, e a primeira é a mais importante:

- **Correlação espúria por múltiplos testes.** Com ~75 bairros × 13 defasagens × 2 direções,
  você fará mais de 1.900 testes e encontrará "correlações fortes" por puro acaso. Exija que a
  relação se sustente no agregado da cidade antes de reportar qualquer relação por bairro,
  aplique correção para múltiplas comparações, e publique intervalo de confiança junto de cada
  coeficiente. Um número de correlação sem intervalo de confiança neste contexto é
  desinformação.
- **Associação, nunca causa.** A direção é ambígua por natureza: comércio pode seguir morador,
  morador pode seguir comércio, e ambos podem seguir uma terceira coisa (uma obra viária, uma
  mudança de zoneamento). O produto descreve o padrão temporal e para por aí. Escreva
  "movimento associado", "precede em N meses" — nunca "causa", "puxa", "impulsiona".
- **Piso de amostra nas duas séries.** Bairro que não tem volume dos dois lados não entra na
  análise cruzada.

### 3.2 Quadrante cruzado

Classifique cada bairro pela direção das duas séries no período, contra a própria baseline:

| | Oferta imobiliária crescendo | Oferta imobiliária encolhendo |
|---|---|---|
| Comércio abrindo acima da média | movimento nos dois lados | comércio cresce, oferta escassa |
| Comércio abrindo abaixo da média | oferta cresce, comércio parado | movimento baixo nos dois lados |

Rótulos descritivos, não avaliativos — o produto não diz que um quadrante é bom e outro é
ruim. Quem conhece o bairro tira a conclusão; essa é a divisão de trabalho correta entre a
ferramenta e quem a usa, e é a mesma postura que o resto do Mercator já adota.

### 3.3 Coincidência espacial fina

Além do bairro, use a geocodificação já existente (Checkpoint 9) e a busca por raio para uma
leitura mais fina: dado um ponto, quantos negócios abriram e quantos imóveis foram anunciados
num raio de N metros, nos últimos M meses. Isso reaproveita infraestrutura pronta e é o formato
mais direto de responder "o que está acontecendo em volta deste endereço" — que é a pergunta
que um corretor faz de verdade, e é exportável para um relatório de uma página.

## 4. Sazonalidade — a armadilha mais provável deste produto

Mercado imobiliário tem sazonalidade forte (dezembro/janeiro despencam, março e setembro
sobem). Sem tratar isso, todo janeiro o produto vai anunciar que a cidade inteira está
desacelerando, e todo março que está aquecendo — e vai estar errado nas duas vezes.

Compare sempre contra o mesmo mês do ano anterior, ou contra a baseline móvel do próprio bairro
que o Checkpoint 8 já calcula — nunca só contra o mês imediatamente anterior. Onde a comparação
mês a mês aparecer, ela vem acompanhada da comparação ano a ano. Enquanto não houver 12 meses
de série coletada, declare isso na interface: "série iniciada em MM/AAAA — comparação anual
disponível a partir de MM/AAAA". Não estime, não extrapole, não preencha com dado sintético.

## 5. Pressão especulativa — o que medir e o que nunca afirmar

Você quer entender como a cidade lida com especulação imobiliária. O produto pode medir
fenômenos associados a isso. O produto não pode chamar nada de especulação — é um termo com
carga valorativa e política, cuja aplicação depende de intenção do proprietário, que nenhum
dado de anúncio revela. Isso importa em dobro se o produto for um dia apresentado a uma
prefeitura: rotular um bairro de "especulativo" transforma uma ferramenta de dado numa peça de
acusação, e queima a credibilidade construída até aqui.

Indicadores mensuráveis, cada um nomeado pelo que ele é:

- **Reanúncio com preço maior** — o mesmo imóvel volta à oferta em janela curta, com preço
  acima do anterior. Exige impressão digital do imóvel (bairro + área + quartos + vagas +
  andar + condomínio), não o ID do portal, que muda. Reporte a taxa de reanúncio e a mediana
  do incremento.
- **Preço pedido subindo sem contrapartida física** — o preço sobe num bairro onde não houve
  alvará novo, nem CVCO, nem mudança de zoneamento no período. Aqui o Checkpoint 11 finalmente
  vira insumo analítico, não decoração.
- **Oferta alta com ocupação baixa** — anúncios ativos por domicílio vago do Censo 2022
  (condição de ocupação é resultado do universo; confirme a variável no dicionário antes de
  modelar). Bairro com muita oferta e muito domicílio vago é um padrão que vale mostrar — e
  deixar a interpretação para quem lê.
- **Concentração de anunciante** — quantos anúncios ativos vêm de poucos ofertantes distintos.
  Mede concentração de oferta sem identificar ninguém: guarde apenas um identificador
  anonimizado e irreversível do ofertante, calcule a concentração, e nunca exponha nem
  persista quem é.
- **Descolamento entre pedido e contratado** — mediana do aluguel pedido dividida pelo índice
  de contratos reais do QuintoAndar para a cidade. É a medida mais direta de "está se pedindo
  mais do que o mercado paga", e ninguém publica isso.

Cada um desses vai à interface com o nome do fenômeno medido e a fórmula, nunca com um rótulo
interpretativo agregado.

## 6. Checkpoint 12a — Verificação e formalização das duas fontes decididas

As fontes já foram escolhidas pelo dono do projeto: Apolar e Chaves na Mão. Este checkpoint não
é mais uma seleção entre candidatos — é a verificação técnica e legal de cada uma, documentada
em `docs/fontes-anuncios.md` antes de qualquer coletor ser escrito. As duas têm status
diferentes e cada uma tem uma tarefa própria.

### 6.1 Apolar — verificação técnica + pedido de autorização

Já verificado nesta sessão, confirme antes de construir em cima: `robots.txt` em
`apolar.com.br` está totalmente aberto (`Disallow:` vazio, sem restrição nenhuma), com
`Sitemap: https://www.apolar.com.br/sitemap-index.xml` apontando para um índice com pelo menos
dois sitemaps (`condominiums-sitemap.xml` e `sitemap.xml`), este último com páginas de detalhe
de imóvel individuais, `changefreq: daily`, organizadas por operação/tipologia/bairro na
própria URL (ex.: `/alugar/apartamento/curitiba/sitio-cercado/...`).

Apolar é uma imobiliária só, não um agregador — isso muda a estratégia. Antes de qualquer
coleta, envie um pedido formal de autorização por escrito (e-mail ou canal institucional
deles), explicando o que o Mercator é, o que será coletado (campos estruturados, nunca
foto/texto/dado de corretor), a cadência (semanal), e que o uso é agregado, nunca republicação
de anúncio individual. Anexe ou referencie o LIA. Registre a data do pedido e a resposta (ou
ausência dela após prazo razoável) em `docs/fontes-anuncios.md`.

- Se autorizarem: a coleta roda com essa autorização documentada — o cenário de menor risco
  possível, e vale desenhar o coletor para já emitir identificação clara (User-agent) que
  facilite a Apolar reconhecer o tráfego como o combinado.
- Se não responderem em prazo razoável (sugestão: 10 dias úteis) ou recusarem: trate a Apolar
  como qualquer fonte sem autorização expressa — as regras da seção 7 (sitemap-only, ritmo
  conservador, nunca burlar) se aplicam integralmente, e o `robots.txt` aberto já é,
  tecnicamente, permissão de acesso — mas não de uso comercial do dado coletado, que é uma
  questão separada de propriedade sobre a base derivada. Documente qual dos dois cenários se
  aplicou.

### 6.2 Chaves na Mão — veredito técnico desfavorável, coleta autorizada por decisão expressa do dono do projeto

Verificado: os Termos de Uso próprios da Chaves na Mão Ltda. (CNPJ 43.853.784/0001-03, sede em
Curitiba — confirmado que não é Grupo OLX) contêm cláusula explícita e sem ambiguidade vedando
"uso de bots, scripts automatizados, ferramentas de raspagem ou qualquer sistema que simule
acesso humano". O `robots.txt` do site não bloqueia agente genérico, publica sitemaps (588
anúncios de Curitiba confirmados só no arquivo mais recente), e ainda assim declara um bloco de
"Content Signals Policy" tentando atribuir força contratual ao próprio arquivo — sinal de que a
empresa pensa ativamente sobre uso automatizado, mesmo esse mecanismo específico tendo respaldo
jurídico fraco no Brasil.

Decisão do dono do projeto, registrada em 16/08/2026: prosseguir com a coleta da Chaves na Mão
apesar da cláusula, com base em que raspagem de dado público não é, em si, conduta vedada por
lei no Brasil. A avaliação técnica desta seção não indicava esse caminho — o registro existe
para que a decisão fique rastreável, como qualquer outra decisão de risco assumido neste
projeto (ex.: o resíduo do Nominatim no Checkpoint 9c).

Consequência prática que decorre da própria decisão: não envie pedido de autorização a esta
fonte. Pedir e receber uma recusa por escrito, e coletar mesmo assim, é estritamente pior do
que nunca ter perguntado — troca um risco ambíguo por má-fé documentada, e retira exatamente o
argumento de boa-fé que o art. 7º §3º da LGPD exige para tratamento de dado tornado público.
Não contate a Chaves na Mão sobre este assunto.

O que essa decisão muda: o risco contratual da cláusula. O que essa decisão não muda, e
continua obrigatório sem exceção: todas as regras técnicas da seção 7 — descoberta só por
sitemap, nunca burlar login/captcha/WAF, ritmo conservador, descarte de dado pessoal na
ingestão, nenhum conteúdo autoral persistido, nenhum dado individual exposto. Violar uma
cláusula contratual conhecida não é motivo para relaxar nenhuma outra disciplina — é motivo
para reforçá-las, porque é a única postura que ainda resta para mitigar exposição nos outros
eixos (LGPD, autoral, boa-fé processual).

### 6.3 Regra de decisão, daqui para frente

Para as duas fontes, o veredito e a decisão (favorável, pendente ou assumida por autorização
expressa) ficam registrados em `docs/fontes-anuncios.md` antes de qualquer coletor entrar em
produção — isso já está satisfeito para as duas. Se uma terceira fonte entrar neste checkpoint
ou em outro futuro, a mesma regra vale: veredito desfavorável não autoriza coleta por si só —
precisa de decisão expressa e datada do dono do projeto, nunca inferida pelo agente. As regras
técnicas da seção 7 valem para todas as fontes, autorizadas ou não.

## 7. Arquitetura de coleta — regras sem exceção

Estas regras valem igualmente para Apolar e para Chaves na Mão. Implemente os dois coletores
como conectores independentes (`apolar_anuncios`, `chavesnamao_anuncios`), cada um com seu
próprio `fonte_id`, seu próprio `pipeline_run`, e capaz de rodar, falhar ou pausar sem afetar o
outro — a mesma disciplina de isolamento de falha que já vale para os conectores de comércio.

- **Descoberta exclusivamente por sitemap.** O portal publica sitemap para ser lido por robô e
  libera as páginas de detalhe; a busca é `Disallow`. Leia o sitemap, resolva as URLs
  permitidas, e nunca construa URL de busca, nunca pagine resultado de busca, nunca chame
  endpoint interno de API. Além de respeitar o `robots.txt` integralmente, é o desenho mais
  estável — sitemap é interface pública, página de busca não.
- **Nunca burlar proteção técnica.** Sem contornar login, captcha, paywall, WAF ou Cloudflare.
  Sem rotação de IP ou user-agent para evadir bloqueio. Fonte que bloqueia sai da lista — não
  vira desafio de engenharia.
- **Identificação honesta.** User-agent próprio e identificável, com URL ou e-mail de contato.
- **Ritmo conservador.** Máximo de 1 requisição a cada 3 segundos por domínio, respeitando
  `Crawl-delay` declarado. Janela fora de horário de pico. Backoff exponencial em erro.
- **Descarte de dado pessoal na ingestão.** Nome, telefone, e-mail e CRECI do anunciante são
  descartados no parsing e nunca persistidos — nem em Raw Zone, nem em log. Endereço completo
  é tratado como dado pessoal: guarde bairro e ponto aproximado, não o número. Escreva o LIA em
  `docs/lia-anuncios.md` antes da primeira coleta.
- **Raw Zone sem conteúdo autoral.** Nada de foto nem de texto descritivo. Só campos
  estruturados (tipologia, área, quartos, vagas, andar, preço, condomínio, IPTU, bairro) e um
  hash da URL. Isso mantém a coleta do lado dos "dados em si", que a Lei 9.610/98 art. 7º §2º
  exclui expressamente da proteção autoral.
- **Nada individual sai.** Só agregado. Nenhum anúncio, foto, texto, link ou identificação de
  anunciante na interface, na API ou em exportação.
- **Cadência fixa e registrada.** Sem snapshots regulares não existe permanência, encerramento
  nem mudança de preço — que são metade do produto. Semanal é suficiente e educado. Cada
  execução registra `pipeline_run`.

## 8. Modelo de dado

Um anúncio é uma entidade de identidade instável observada no tempo — exatamente o problema
que a plataforma já resolve. Reaproveite a espinha, não crie modelo paralelo.

```sql
-- entidade: tipo_entidade = 'anuncio_imovel'
-- identificador_fonte = hash(portal + id_do_anuncio)
-- impressao_digital = hash(bairro, area, quartos, vagas, andar, condominio)  -- para reanúncio

CREATE TABLE canonical.observacao_anuncio (
    observacao_id      UUID PRIMARY KEY,
    entidade_id        UUID NOT NULL REFERENCES canonical.entidade(entidade_id),
    observado_em       DATE NOT NULL,
    operacao           TEXT NOT NULL CHECK (operacao IN ('venda','aluguel')),
    tipologia          TEXT NOT NULL,
    territorio_id      TEXT REFERENCES canonical.dim_territorio(territorio_id),
    preco              NUMERIC,
    tipo_valor         TEXT NOT NULL DEFAULT 'anuncio' CHECK (tipo_valor = 'anuncio'),
    condominio         NUMERIC,
    iptu               NUMERIC,
    area_util_m2       NUMERIC,
    quartos            SMALLINT,
    banheiros          SMALLINT,
    vagas              SMALLINT,
    andar              SMALLINT,
    ofertante_hash     TEXT,               -- anonimizado e irreversível, só para concentração
    impressao_digital  TEXT NOT NULL,
    fonte_id           TEXT NOT NULL REFERENCES canonical.dim_fonte(fonte_id),
    snapshot_ref        TEXT NOT NULL,
    UNIQUE (entidade_id, observado_em)
);
```

Eventos derivados na mesma mecânica de `event_detection` já existente: `ANUNCIO_PUBLICADO`,
`ANUNCIO_ENCERRADO` (confiança baixa por natureza — o catálogo deve declarar isso),
`PRECO_ALTERADO`, `REANUNCIO` (nova entidade com `impressao_digital` já vista em janela
recente).

Taxonomia canônica em `dim_tipologia_imovel`, tabela de tradução versionada, nunca um `if` no
parser — mesma disciplina de `dim_cnae` → `dim_categoria`. Categorias mínimas: `apartamento`,
`casa`, `sobrado`, `kitnet_studio`, `cobertura`, `terreno`, `sala_comercial`, `galpao`,
`chacara_sitio`. O que não casar vai para `nao_classificado` e aparece no relatório de
qualidade, não some em "outros".

### 8.1 Resolução entre fontes — o mesmo imóvel não conta duas vezes

Com Apolar e Chaves na Mão coletadas ao mesmo tempo, é bastante provável que o mesmo imóvel
físico apareça em ambas — uma imobiliária anuncia no site próprio e também num portal
agregador. Cada portal gera uma entidade própria (`identificador_fonte = hash(portal +
id_do_anuncio)`), o que é correto para auditoria por fonte, mas errado para contagem de volume
se não houver um passo de resolução: sem ele, "novos anúncios" e "estoque anunciado" ficam
inflados artificialmente sempre que houver sobreposição entre as duas fontes, e o quadrante de
aquecimento (seção 2.1) fica sujeito a ruído que não é sinal de mercado nenhum.

Resolva com um passo explícito, separado da ingestão de cada conector:

- Agrupe entidades cuja `impressao_digital` (bairro + área + quartos + vagas + andar +
  condomínio) coincida dentro de uma janela de tempo razoável (ex.: 30 dias) num cluster de
  imóvel único, com uma tabela `canonical.imovel_resolvido` ligando as entidades-membro.
- Métricas de volume (novos anúncios, estoque, rotação, permanência) operam sobre o cluster
  resolvido, não sobre a contagem bruta de entidades por fonte — um imóvel presente nas duas
  fontes conta uma vez.
- Métricas de preço continuam podendo ser reportadas por fonte quando relevante (ex.: para
  detectar se uma fonte sistematicamente anuncia mais caro que a outra para o mesmo imóvel —
  isso também é um dado interessante, não um problema a esconder).
- O cluster resolvido carrega a lista de fontes que o compõem, e é isso que alimenta o rótulo
  "anunciado em: Apolar e Chaves na Mão" exigido na seção 1.2.
- Esta resolução é lógica pura sobre os dados já ingeridos — implemente em `src/domain/` (ou
  pasta equivalente), testável sem rede, com teste para o caso de coincidência dentro e fora da
  janela, e para o caso de nenhuma coincidência.

## 9. Fontes gratuitas — entram antes do coletor

**QuintoAndar** — Índice de Aluguel (`mkt.quintoandar.com.br/dados`): CSV aberto, calculado
sobre contratos reais assinados, Curitiba coberta. Granularidade de cidade. Não substitui a
coleta — é a âncora de calibração que permite medir e publicar o descolamento entre pedido e
contratado (seção 5).

**FipeZap**: informe mensal em PDF com os 10 bairros mais representativos por cidade. Segunda
régua. Sem licença publicada — use internamente para validação e não redistribua o número sem
escrever para a Fipe antes.

## 10. Interface — o produto precisa ficar mais simples

A tela atual abre com "2.214 alvarás aprovados e 1.373 CVCOs concluídos no período" —
verdadeiro e sem significado para quem não é do ramo. Preço e movimento de oferta viram a tela
principal; construção vira aba de contexto.

Manchete concreta, no padrão editorial do Checkpoint 10: "Alugar um apartamento de 2 quartos no
Batel custa hoje R$ 3.200 na mediana — 8% acima de um ano atrás, e os anúncios estão saindo
mais rápido."

Quatro controles no topo, em linguagem direta: operação (alugar/comprar) · tipo de imóvel ·
período · bairro. Com eles, todas as perguntas da seção 0 são respondíveis sem o usuário
aprender nada.

Mapa principal colorido pelo quadrante de aquecimento (seção 2.1), com legenda que explica os
dois eixos em uma linha cada.

Painel de bairro, nesta ordem: preço mediano com faixa P25–P75 → variação contra 12 meses →
estoque anunciado e sua variação → permanência mediana → quadrante e por que ele caiu ali →
leitura cruzada com comércio → e só então, embaixo e rotulado como contexto, construção e valor
venal.

Três correções da tela atual:

- O tile "defasagem mediana alvará → CVCO" exibindo "dado em construção" com peso visual de
  tile preenchido precisa sumir enquanto não houver dado. Tile sem dado não ocupa espaço de
  tile com dado — já foi corrigido no Checkpoint 10d e regrediu.
- "valor venal mediano (PGV)" precisa de rótulo ao lado do número, visível e não em tooltip:
  "valor de referência para IPTU — não é preço de mercado".
- Se o coroplético colore só parte dos bairros, declare na legenda quantos ficaram sem dado
  suficiente. Área sem cor e sem explicação lê como bug.

Painel de procedência ampliado: cada fonte com data do último snapshot, cadência, e — para
anúncio — quantos foram observados no período, taxa de classificação de tipologia e taxa de
resolução de bairro, separado por Apolar e por Chaves na Mão. Se o dado vem de anúncio, a
interface diz que vem de anúncio, sempre — e diz de qual das duas, ou das duas juntas, seguindo
a regra da seção 1.2. Nenhum tile, gráfico ou linha de ranking com dado de anúncio fica sem
essa indicação, mesmo fora deste painel.

Hierarquia quando houver conflito: credibilidade > clareza > utilidade > UX > estética >
quantidade de funcionalidades.

## 11. Escopo do v1

Uma cidade (Curitiba), Apolar e Chaves na Mão como as duas fontes de coleta, duas operações, as
tipologias da seção 8. Implemente e valide o coletor da Apolar primeiro — é a fonte com
`robots.txt` mais permissivo e caminho de autorização direta — antes de ligar o da Chaves na
Mão, mesmo que os dois entrem no mesmo checkpoint. Prove a resolução entre fontes (seção 8.1)
assim que a segunda estiver coletando, não depois.

O que **não** fazer: chamar anúncio encerrado de venda, em nenhum campo ou rótulo · burlar
qualquer proteção técnica, para nenhuma das duas fontes, autorizada ou não · usar `/busca`,
`/api/` ou paginação profunda · persistir nome, telefone, e-mail ou CRECI · armazenar foto ou
texto de anúncio · publicar anúncio individual ou link · misturar `tipo_valor` num agregado ·
afirmar causalidade entre comércio e imóveis · rotular bairro como especulativo · redistribuir
número do FipeZap sem resolver licença · contatar a Chaves na Mão sobre este assunto (seção
6.2) · contar o mesmo imóvel duas vezes por estar presente nas duas fontes sem passar pela
resolução da seção 8.1 · exibir dado de anúncio sem indicar a fonte · tocar no pipeline de
comércio ou na geocodificação.

## 12. Sequência de implementação, com checkpoint de parada

- **12a** — Verificação das fontes. Seção 6, subseções 6.1 (Apolar) e 6.2 (Chaves na Mão)
  concluídas — `docs/fontes-anuncios.md` e `docs/lia-anuncios.md` escritos, decisão do dono do
  projeto registrada para a Chaves na Mão. Este checkpoint está satisfeito para as duas
  fontes; o 12d pode prosseguir para ambas. Pendência aberta e não bloqueante: resposta da
  Apolar ao pedido de autorização (seção 6.1) — acompanhe e registre quando chegar, mas não é
  pré-requisito para iniciar a coleta.
- **12b** — Fontes gratuitas. QuintoAndar e FipeZap (seção 9). Já entrega série de aluguel de
  Curitiba antes de existir coleta.
- **12c** — Modelo, taxonomia e resolução entre fontes. Seção 8 completa, incluindo 8.1
  (resolução por `impressao_digital`), com `dim_tipologia_imovel` versionada e testes dos
  ramos de detecção de evento e de resolução, sem banco nem rede.
- **12d** — Coletores. Seção 7, Apolar primeiro, Chaves na Mão em seguida, cada um como
  conector independente. Reporte por fonte: anúncios coletados, taxa de classificação de
  tipologia, taxa de resolução de bairro, requisições por minuto efetivas, bloqueios
  encontrados — e, assim que as duas estiverem coletando, quantos imóveis foram resolvidos
  como presentes nas duas fontes.
- **12e** — Ciclo de vida. Segundo e terceiro snapshots; `ANUNCIO_ENCERRADO`, `PRECO_ALTERADO`
  e `REANUNCIO` funcionando. Calibração contra ONR e QuintoAndar (seções 1.1 e 9), resultado
  escrito.
- **12f** — Termômetro. Seção 2, incluindo o quadrante no Signal Engine e o tratamento de
  sazonalidade da seção 4.
- **12g** — Leitura cruzada. Seção 3, com as três travas estatísticas. Reporte os coeficientes
  e intervalos de confiança antes de expor qualquer coisa na interface — se a relação não se
  sustentar no agregado da cidade, a feature não vai para a tela, e isso é um resultado
  válido, não uma falha.
- **12h** — Pressão especulativa. Seção 5.
- **12i** — Interface. Seção 10, incluindo as três correções.

Pare ao final de cada um, rode os testes, e resuma antes de seguir.

## 13. Critérios de sucesso

Pronto quando alguém que nunca viu o produto conseguir, em menos de um minuto e sem ajuda:
descobrir quanto custa alugar ou comprar um tipo específico de imóvel num bairro específico, e
se subiu ou caiu no último ano; ver quais bairros estão aquecendo e quais estão desacelerando,
e entender por quais dois números o produto chegou a essa conclusão; ver se o movimento de
comércio e o de imóveis andam juntos naquele bairro, e com que defasagem; entender, sem que
ninguém explique, que aquilo é oferta anunciada, não transação fechada; e saber, para qualquer
número na tela, se ele vem da Apolar, da Chaves na Mão, ou das duas — sem precisar procurar.

E, com o mesmo peso: quando o produto souber dizer o que não sabe — que não mede transação,
que anúncio encerrado não é venda, que abaixo de 30 anúncios ele se cala, que sem 12 meses de
série não há comparação anual — sem que isso soe como desculpa, e sim como método.
