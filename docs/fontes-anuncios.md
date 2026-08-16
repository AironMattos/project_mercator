# Verificação de fontes — Radar de Anúncios (Checkpoint 12a)

Data da verificação: 2026-08-15.

Método: consulta direta a `robots.txt` e aos sitemaps públicos dos dois domínios (`curl`,
sem autenticação), download e inspeção de amostras reais dos sitemaps de imóvel (não só a
lista de índices), e leitura da página de Termos de Uso de cada site — via navegador real
(Apolar é uma SPA renderizada no cliente; `curl`/`WebFetch` sem execução de JS só devolvem a
casca vazia, então a verificação do rodapé/Termos precisou do Chrome de verdade). Nenhum
conector, modelo ou pipeline foi escrito — este documento é o resultado da seção 6 do prompt
de referência do Radar de Anúncios. As duas fontes já foram escolhidas pelo dono do projeto;
este checkpoint não é uma seleção entre candidatos, é a verificação técnica e legal de cada
uma antes de qualquer coletor existir.

---

## 1. Apolar (`apolar.com.br`) — seção 6.1

### `robots.txt`

```
User-agent: *
Disallow:
Sitemap: https://www.apolar.com.br/sitemap-index.xml
```

Confirmado: **totalmente aberto**, nenhuma restrição de `Disallow`, nenhum bloqueio nomeado a
ferramenta específica (diferente da Chaves na Mão, ver seção 2). O `robots.txt` não faz
nenhuma declaração adicional sobre uso automatizado — nem `Content-Signal`, nem comentário.

### Sitemap

`sitemap-index.xml` aponta para dois arquivos: `condominiums-sitemap.xml` (páginas de
condomínio, não é anúncio individual — não é fonte de dado de preço/oferta) e `sitemap.xml`,
que é a fonte relevante: **16.826 URLs**, mistura páginas de detalhe de anúncio individual com
páginas de categoria/listagem (bairro, cidade, tipo — essas últimas não são "página de busca"
no sentido do robots.txt, mas também não têm o dado estruturado por imóvel; a coleta real deve
mirar só as páginas de detalhe).

**Achado que corrige o prompt de referência**: o segmento de URL da operação de venda é
`/venda/...`, não `/comprar/...` como o prompt assumia por analogia com `/alugar/...`.
Confirmado contando por padrão de URL no sitemap baixado:

- `/alugar/curitiba/...-<id>` (aluguel, Curitiba, página de detalhe): **940** URLs.
- `/venda/curitiba/...-<id>` (venda, Curitiba, página de detalhe): **2.612** URLs.
- Total de páginas de detalhe (todas as cidades onde a Apolar atua, aluguel+venda): **7.656**
  das 16.826 URLs do sitemap; o restante são páginas de categoria/listagem.

Formato de URL de detalhe, com exemplos reais capturados no sitemap:

```
https://www.apolar.com.br/alugar/curitiba/sitio-cercado/alugar-residencial-apartamento-curitiba-sitio-cercado-100127
https://www.apolar.com.br/venda/curitiba/butiatuvinha/venda-residencial-casa-curitiba-butiatuvinha-151309
https://www.apolar.com.br/venda/curitiba/tingui/venda-comercialresidencial-terreno-curitiba-tingui-155544
```

O slug já carrega operação, uso (`residencial`/`comercial`/`comercialresidencial`), tipologia
(`apartamento`/`casa`/`terreno`/...), cidade, bairro e um ID numérico estável — a maior parte
da taxonomia da seção 8 é derivável só do padrão de URL, sem precisar necessariamente abrir
cada página (a página de detalhe continua sendo a fonte de preço/área/quartos/vagas, que não
está no slug). `changefreq: daily` em toda entrada — coerente com a cadência semanal do
produto, sem sinal de o site preferir uma cadência diferente.

### Termos de Uso

**Não existe página de Termos de Uso publicada.** Verificado com o navegador real: o rodapé
do site lista `Sobre a Apolar`, `Nossas Lojas`, `FAQ`, `Blog`, `Consórcio`, `Área Restrita`,
`Política de cookies`, `Fale Conosco`, `Trabalhe Conosco`, `Seja Franqueado`, `Franquias` — sem
nenhum link de "Termos de Uso", "Termos e Condições" ou equivalente. A única política legal
publicada é `/politica-de-cookies`, que trata exclusivamente de cookies de navegador (consentimento
de rastreamento no browser), sem nenhuma cláusula sobre coleta automatizada, raspagem ou uso de
dado do site por terceiro. Não há, portanto, nenhuma cláusula contratual publicada que proíba
ou que autorize scraping — o `robots.txt` aberto é, hoje, o único sinal técnico/legal direto da
Apolar sobre o assunto.

### Contato institucional

Não há e-mail institucional exposto publicamente (nem em rodapé, nem na página "Sobre a
Apolar"). O único canal de contato encontrado é um formulário em `/fale-conosco/` (sem
endereço de e-mail visível por trás dele). **O pedido de autorização da seção 6.1 ainda não foi
enviado** — não é uma ação que a IA deveria tomar sozinha (envio de mensagem em nome do dono do
projeto é uma ação que exige confirmação explícita, fora do escopo de uma verificação técnica).
O texto do pedido foi redigido e está em `docs/pedido-autorizacao-apolar.md`, pronto para o
dono do projeto revisar e enviar pelo formulário de contato (ou por um canal direto, se
existir uma relação comercial já estabelecida com a Apolar fora deste projeto).

### Veredito

**Robots.txt favorável (aberto, sem restrição). Sem Termos de Uso publicados que proíbam
coleta. Pedido de autorização redigido, ainda não enviado pelo dono do projeto — decisão e
envio ficam com ele.** Enquanto não houver resposta (ou decisão explícita de prosseguir sem
ela), a Apolar deve ser tratada como fonte sem autorização expressa: regras da seção 7
(sitemap-only, ritmo conservador, nunca burlar) valem integralmente, e a ausência de Termos de
Uso não é interpretada como autorização de uso comercial do dado coletado — só como ausência de
proibição contratual explícita.

**Decisão do dono do projeto (2026-08-15)**: prosseguir com a coleta sem aguardar resposta ao
pedido de autorização ("pode seguir com o scraping... não há necessidade de aceite"). Registrado
aqui como a decisão explícita que a seção 6.3 do prompt de referência exige antes de construir
o conector sem autorização confirmada. As regras técnicas da seção 7 (sitemap-only, ritmo
conservador, identificação honesta, nunca burlar proteção técnica, descarte de dado pessoal)
continuam valendo integralmente - a decisão dispensa a autorização formal, não a disciplina de
coleta.

**Atualizado em 2026-08-16** (ver seção 2.1): autorização direta obtida da Apolar por conversa
- a coleta deixa de rodar sob "sem autorização expressa" e passa a ter autorização confirmada.

---

## 2. Chaves na Mão (`chavesnamao.com.br`) — seção 6.2

### `robots.txt`

Não há bloqueio geral a `User-agent: *` (sem `Disallow: /`), mas com uma bateria de regras
específicas:

```
User-agent: *
Content-Signal: ai-train=no, search=yes, ai-input=yes

Allow: /*?pg=2$
Allow: /*?pg=3$
Allow: /*?pg=4$
Allow: /*?pg=5$
Disallow: /*?*
...
Disallow: /admin/
Disallow: /minhaconta/
...
Disallow: /imoveis/estatisticas/
```

Mais **~40 user-agents nomeados individualmente** com `Disallow: /` — todos ferramentas de
download/raspagem genéricas (`wget`, `HTTrack`, `WebCopier`, `SiteSnagger`, `Xenu`, `libwww`,
`Teleport`/`TeleportPro`, `MJ12bot`, `dotbot`, etc.), não um agente de propósito específico
deste projeto. O bloco `Content-Signal` (TDM opt-out sob o Art. 4 da Diretiva UE 2019/790,
citado no próprio `robots.txt`) é um mecanismo europeu, sem base jurídica direta no Brasil, mas
é um sinal explícito e público de que a empresa reserva direitos sobre uso automatizado do
conteúdo — o mesmo espírito que a cláusula de Termos de Uso abaixo declara de forma direta e
aplicável.

`Disallow: /*?*` (com exceções pontuais para paginação `pg=2` a `pg=5`) reforça a regra da
seção 7 do prompt de referência: nada de parâmetro de busca livre, só sitemap.

### Sitemap

`sitemap-index.xml` tem **1.822 entradas**, a maioria delas sitemaps de páginas de
categoria/filtro (cidade × bairro × tipo × quartos × característica, em todas as combinações —
não é dado por imóvel, é uma malha de páginas de listagem para SEO). Os sitemaps relevantes
para dado individual de anúncio:

- `sitemap-venda-imoveis-01.xml.gz` a `-81.xml.gz` (venda).
- `sitemap-aluguel-imoveis-01.xml.gz` a `-13.xml.gz` (aluguel).

Cada arquivo é **nacional, não filtrado por cidade** (confirmado baixando e descomprimindo o
arquivo `01` de venda: 50.000 URLs, todas datadas de hoje, cidades espalhadas por todo o
Brasil). Coletar só Curitiba exige baixar os `.xml.gz` e filtrar pelo padrão de URL, não existe
um sitemap pré-filtrado por cidade para anúncio individual (os sitemaps `*-cidades-bairros*`
existentes são de página de categoria, não de anúncio). Confirmado que Curitiba/PR está
presente: **588 URLs** de venda com o padrão `-pr-curitiba-` só no primeiro arquivo (50.000
URLs, o mais recente) — volume real por cidade só fica claro depois de varrer os 81+13
arquivos, fora do escopo desta verificação.

Formato de URL de detalhe, exemplo real:

```
https://www.chavesnamao.com.br/imovel/apartamento-a-venda-2-quartos-com-garagem-pr-curitiba-campo-comprido-65m2-RS379000/id-45712812/
```

Mesmo padrão da Apolar: o slug já carrega tipologia, operação, quartos, garagem, UF, cidade,
bairro, área e preço — praticamente todos os campos estruturados da seção 8 estão no próprio
slug da URL, o que reduz (mas não elimina, falta pelo menos `andar`/`condomínio`/`IPTU`) a
necessidade de abrir cada página de detalhe.

### Termos de Uso

**Existe, é próprio da Chaves na Mão (não do Grupo OLX) e proíbe coleta automatizada de forma
explícita.** URL: `https://www.chavesnamao.com.br/termos-de-uso`. Parte contratante:

> "CHAVES NA MÃO LTDA. está inscrita no CNPJ sob o nº 43.853.784/0001-03", sediada em "Praça
> Tiradentes, nº 320, CEP 80.020-100, Centro, Curitiba/PR" — confirma que é entidade própria,
> com CNPJ e sede distintos de qualquer entidade do Grupo OLX, exatamente a distinção que o
> prompt de referência pediu para verificar.

Seções, em ordem: QUEM SOMOS · ACEITAÇÃO · LEGISLAÇÃO APLICÁVEL · RESPONSABILIDADES ·
UTILIZAÇÃO DA PLATAFORMA · INDICAÇÃO NA MÃO · DICAS DE VENDA ONLINE COM SEGURANÇA E
PRATICIDADE · PROPRIEDADE INTELECTUAL · RESOLUÇÃO DE CONFLITOS · DADOS DE CONTATO. Nenhuma
data de versão/última atualização aparece na página.

Cláusula que decide o veredito, na seção "Condutas vedadas na plataforma" (dentro de
UTILIZAÇÃO DA PLATAFORMA):

> "Uso de bots, scripts automatizados, ferramentas de raspagem ou qualquer sistema que simule
> acesso humano"

— listada ao lado de outras condutas proibidas (cadastro de menor de idade, uso de documento
falso, conteúdo impróprio, discurso discriminatório). **É uma proibição explícita, direta, sem
ambiguidade de interpretação**, cobrindo exatamente a categoria de coleta que este checkpoint
avalia — não uma restrição genérica de "uso indevido" que pudesse ser lida como não aplicável.

PROPRIEDADE INTELECTUAL reforça: "As marcas, logotipos, layouts, nomeações de serviços e todo
material deste portal são de propriedade exclusiva do portal CHAVES NA MÃO" — relevante para a
disciplina de "nada individual sai" da seção 7 (não é permissão pra reter/republicar conteúdo,
é uma reafirmação de que o portal já se declara dono do material).

RESPONSABILIDADES esclarece o papel do site como intermediário técnico: "O CHAVES NA MÃO não
participa da inserção, edição ou administração dos anúncios" e "não é parte das transações
realizadas entre anunciantes e usuários" — relevante para o LIA (`docs/lia-anuncios.md`): o
dado publicado é do anunciante, não do portal, mas a cláusula de proibição de raspagem acima é
do portal e vale independente de quem seja o titular do dado publicado.

### Contato institucional

DADOS DE CONTATO: telefone "(41) 3092-1001 / (41) 99266-8447 (WhatsApp)", e-mail
"atendimento@chavesnamao.com.br" — canal de atendimento ao usuário final, não necessariamente o
canal certo para uma negociação institucional de uso de dado, mas é um ponto de contato real e
direto (diferente da Apolar, que só tem formulário).

### Veredito

**Desfavorável.** Termos de Uso próprios (não do Grupo OLX, confirmado por CNPJ/razão social),
com cláusula explícita proibindo "bots, scripts automatizados, ferramentas de raspagem" — sem
ambiguidade de leitura. Conforme a regra de decisão da seção 6.3 do prompt de referência, esse
veredito por si só bloquearia a construção do conector `chavesnamao_anuncios`.

**Decisão do dono do projeto (2026-08-15)**: prosseguir mesmo assim ("pode seguir com o
scraping... não há necessidade de aceite") - decisão explícita, registrada e datada, que a
seção 6.3 do prompt de referência prevê como a única forma de seguir com um veredito
desfavorável. Isso muda a autorização contratual, não o risco documentado nem a disciplina
técnica: a cláusula dos Termos de Uso continua proibindo a conduta (o risco contratual é real e
foi assumido conscientemente pelo dono do projeto, não eliminado), e as regras da seção 7
(sitemap-only, ritmo conservador, identificação honesta, nunca burlar proteção técnica,
descarte de dado pessoal) valem com o mesmo rigor de antes - inclusive mais, já que é a única
salvaguarda restante nesta fonte.

**Atualizado em 2026-08-16** (ver seção 2.1): autorização direta obtida da Chaves na Mão por
conversa - o veredito desfavorável dos Termos de Uso deixa de ser um risco assumido sem
consentimento e passa a ter autorização confirmada do titular do site.

---

## 2.1 Atualização — autorização direta obtida das duas empresas (2026-08-16)

**Declaração do dono do projeto, registrada em 2026-08-16**: "Estou concedendo todas as
permissões após conversas com ambas as empresas." Isso supera as duas decisões de 2026-08-15
acima, que eram decisões de *prosseguir sem autorização confirmada* (Apolar) ou de *prosseguir
apesar de um veredito de Termos de Uso desfavorável* (Chaves na Mão) - agora, segundo o dono do
projeto, existe autorização direta e efetiva das duas empresas, obtida por conversa fora deste
projeto (não por e-mail formal via o pedido redigido em `docs/pedido-autorizacao-apolar.md`,
que segue não enviado e agora é redundante).

**O que muda**: as duas fontes deixam de operar sob "regras conservadoras de fonte sem
autorização" (seção 7, primeira metade) e passam a ter o cenário de menor risco possível
descrito na seção 6.1 do prompt de referência - autorização documentada. Para a Chaves na Mão
em particular, isso muda o risco contratual da cláusula de Termos de Uso: a conduta que a
cláusula proíbe deixa de ser praticada sem consentimento do titular do site, porque o titular
consentiu diretamente.

**O que não muda**: nenhuma das disciplinas técnicas da seção 7 é dispensada por causa de
autorização - identificação honesta, ritmo conservador (3s/req), descoberta só por sitemap,
nunca burlar proteção técnica, descarte de dado pessoal na ingestão (nome/telefone/e-mail/CRECI
nunca persistidos), Raw Zone sem conteúdo autoral (violação real dessa regra, encontrada e
corrigida em 2026-08-16 nos dois conectores - ver `CLAUDE.md`, checkpoint 12d). Autorização
muda quem pode reclamar de a coleta acontecer, não o que é coletado nem como.

**Registro honesto de limitação**: não tenho, neste momento, um documento (e-mail, contrato,
mensagem) da autorização em si - só a declaração do dono do projeto nesta conversa, que é
tratada aqui com o mesmo peso que as decisões de 2026-08-15 já registradas (mesmo padrão do
projeto: decisão explícita e datada do dono, não inferida). Se houver correspondência real
disponível depois, vale anexá-la ou referenciá-la aqui para o registro ficar mais completo.

## 3. Regra de decisão aplicada

12a foi verificação, não implementação — nenhum coletor foi construído durante este checkpoint.
Com a decisão do dono do projeto de 2026-08-15 (registrada nas seções 1 e 2 acima), os
checkpoints seguintes (12c em diante) constroem os dois conectores. O pedido de autorização em
`docs/pedido-autorizacao-apolar.md` segue disponível caso o dono do projeto decida enviá-lo
depois - não é mais um bloqueio para a Apolar, mas continua sendo a via mais limpa se a Apolar
responder favoravelmente em algum momento. Para a Chaves na Mão, o risco contratual documentado
na seção 2 não desaparece com a decisão de prosseguir - fica registrado aqui como um risco
assumido conscientemente, não como um problema resolvido.

## 4. Nota fora do escopo deste checkpoint, registrada para os próximos

O modelo de dado da seção 8 do prompt de referência declara `fonte_id TEXT NOT NULL REFERENCES
canonical.dim_fonte(fonte_id)` — mas o projeto decidiu deliberadamente, no Checkpoint 11b (Radar
Imobiliário), **não ter** uma tabela `dim_fonte`: `fonte_id` é texto livre sem FK em todo o
restante do schema, documentado como desvio proposital pra não introduzir uma abstração nova
sem outro uso. Quando o Checkpoint 12c (modelo/taxonomia) for implementado, essa mesma decisão
provavelmente deve valer aqui também — mas é uma decisão de modelagem, não de verificação de
fonte, por isso só registrada aqui, não resolvida.
