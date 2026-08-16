# Avaliação de Interesse Legítimo (LIA) — Radar de Anúncios

Checkpoint 12a. Escrito antes de qualquer coleta, como exige a seção 7 do prompt de referência
do Radar de Anúncios. Cobre o dado pessoal que passa pelo pipeline de coleta de anúncio
imobiliário (Apolar e, condicional ao veredito de `docs/fontes-anuncios.md`, Chaves na Mão) —
não cobre nenhum outro produto do Mercator, que já não lida com dado pessoal de anunciante
(o Radar de Comércio usa dado público de alvará, sem contato pessoal; o Radar Imobiliário usa
dado público de fonte governamental).

**Importante, antes da avaliação em si**: uma LIA responde se o projeto tem base legal (LGPD)
para *processar* o dado pessoal que aparece incidentalmente numa página de anúncio. Ela **não**
responde se o projeto tem *permissão para acessar* aquela página de forma automatizada — isso é
uma questão de contrato/Termos de Uso, distinta e resolvida em `docs/fontes-anuncios.md`. As
duas precisam ser positivas. Um resultado favorável nesta LIA não autoriza, por si só, coletar
de uma fonte cujos Termos de Uso proíbem raspagem — é exatamente esse o caso da Chaves na Mão
hoje (veredito desfavorável já registrado na seção 2 de `docs/fontes-anuncios.md`).

## 1. Que dado pessoal aparece no pipeline, e onde ele para

Uma página de anúncio publicada nos sites-fonte normalmente expõe, junto do dado estrutural do
imóvel: nome do anunciante ou corretor, telefone, e-mail, número de CRECI, e às vezes um
endereço com número. Nenhum desses campos é o dado que o produto quer — o produto quer
tipologia, área, quartos, vagas, andar, preço, condomínio, IPTU e localização a nível de bairro.

Disciplina de descarte, já especificada na seção 7 do prompt de referência e adotada aqui como
requisito de implementação, não como aspiração:

- Nome, telefone, e-mail e CRECI do anunciante/corretor são descartados no `normalize()` do
  conector — nunca chegam a ser escritos em Raw Zone, em `canonical.observacao_anuncio`, nem em
  log. Ficam em memória só durante o parsing da página, e só até serem descartados.
- Endereço é tratado como dado pessoal quando completo (rua + número identificam uma unidade
  específica, potencialmente ligada a uma pessoa física). O pipeline guarda `territorio_id`
  (bairro) e, quando necessário para a leitura cruzada de raio (seção 3.3 do prompt de
  referência), um ponto aproximado — nunca o número do imóvel.
- `ofertante_hash` (seção 8 do prompt de referência) é um hash irreversível e anonimizado
  calculado sobre o identificador do anunciante na fonte, usado só para medir concentração de
  ofertante (seção 5) — nunca é revertido, nunca é exposto, e não permite reidentificar a
  pessoa a partir do hash sozinho.
- Nada disso é uma promessa de interface — é o mesmo tipo de restrição que já vale para
  `identificador_fonte`/dado bruto de outras fontes do projeto (ex.: o CSV de alvarás também
  passa por Raw Zone sem qualquer dado de contato pessoal ser extraído para `canonical.*`).

O que efetivamente entra em `canonical.observacao_anuncio` e sobrevive até a API/interface é
só o dado estrutural do imóvel e o hash anonimizado do ofertante — nunca informação que
identifique uma pessoa física diretamente.

## 2. Base legal (LGPD art. 7º, IX — legítimo interesse)

Sem relação contratual com o titular do dado (o anunciante) e sem consentimento dele para este
uso específico, a base legal aplicável é o legítimo interesse do controlador (art. 7º, IX, e
art. 10 da LGPD), sujeita ao teste de necessidade, adequação e balanceamento com os direitos do
titular — não uma autorização automática, precisa ser justificada e documentada, que é o que
segue.

### 2.1 Teste de finalidade e necessidade

**Finalidade**: medir e publicar indicadores agregados de mercado imobiliário (preço pedido,
permanência, rotação de oferta) por bairro e tipologia em Curitiba — finalidade legítima,
específica e explícita, sem uso oculto.

**Necessidade**: nenhuma das duas fontes oferece API pública ou exportação em lote de dado
agregado equivalente. A leitura estruturada da própria página de anúncio (via sitemap, não via
busca) é o meio tecnicamente menos invasivo disponível para atingir a finalidade — não há
alternativa que evite tocar a página onde o dado pessoal incidental aparece.

### 2.2 Teste de balanceamento

A favor do uso:

- O dado pessoal em si (nome, telefone, CRECI do anunciante) **não é o dado de interesse do
  projeto** e é descartado antes de qualquer persistência — o processamento dele é transitório,
  não um fim.
- O titular do dado publicou a página com o propósito explícito de ampla visibilidade (a
  finalidade de um anúncio é ser visto e contatado pelo maior número de pessoas possível) — o
  que reduz, mas não zera, a expectativa razoável de privacidade sobre os dados de contato ali
  publicados.
- O produto final expõe só estatística agregada (mediana, contagem, quadrante) — nunca um
  anúncio, link, foto ou identificação individual.
- `ofertante_hash` impede que mesmo a métrica de concentração de anunciante (seção 5 do prompt
  de referência) sirva para reidentificar alguém.

Contra o uso / mitigação necessária:

- Coleta automatizada, mesmo de página pública, ainda pode surpreender o titular ("eu não
  esperava que meu anúncio fosse processado por um robô") — mitigado por: (a) nunca persistir o
  dado de contato pessoal, (b) nunca republicar o anúncio, (c) canal de contato do projeto
  disponível para pedido de exclusão, ainda que a exclusão recaia sobre o registro estrutural do
  imóvel, já que o dado pessoal propriamente dito nunca chega a ser retido.
- Volume: milhares de anúncios por semana, o que amplifica o efeito de qualquer falha de
  descarte — por isso o descarte é tratado como requisito de implementação testável (seção 12c
  do prompt de referência: testes automatizados dos ramos de detecção/normalização), não como
  documentação sem verificação.
- Rate limiting e identificação honesta (seção 7) reduzem o impacto técnico sobre o site-fonte,
  o que também é parte do balanceamento — coleta agressiva ou disfarçada pesaria contra o
  legítimo interesse mesmo que a finalidade fosse a mesma.

### 2.3 Conclusão do teste

**Passa**, condicionado às mitigações acima serem implementadas de fato (não é uma aprovação
incondicional — é uma aprovação da abordagem descrita, que os checkpoints 12c/12d precisam
implementar fielmente, com teste automatizado do descarte de dado de contato). Isso resolve a
pergunta da LGPD. A pergunta do Termos de Uso é separada — ver a ressalva no topo deste
documento e o veredito por fonte abaixo.

## 3. Conclusão por fonte

- **Apolar**: LIA favorável (seção 2.3). Sem Termos de Uso publicados proibindo coleta
  (`docs/fontes-anuncios.md`, seção 1) — pedido de autorização formal ainda pendente de envio
  pelo dono do projeto. Enquanto isso, coleta sob as regras conservadoras da seção 7 (sem
  autorização expressa) é compatível com este LIA.
- **Chaves na Mão**: LIA favorável na dimensão de dado pessoal (mesma análise acima se aplica
  igualmente) - mas essa conclusão nunca superou, por si só, o veredito de Termos de Uso
  desfavorável (`docs/fontes-anuncios.md`, seção 2): a cláusula que proíbe "bots, scripts
  automatizados, ferramentas de raspagem" é uma barreira contratual independente da LGPD. O
  dono do projeto decidiu prosseguir mesmo assim em 2026-08-15 (registrado em
  `docs/fontes-anuncios.md`) - decisão dele, explícita e datada, sobre o risco contratual. Esta
  LIA continua valendo exatamente como escrita para a dimensão de dado pessoal: a coleta desta
  fonte só é aceitável se a disciplina de descarte da seção 1 for implementada de fato, com
  teste automatizado - a decisão sobre o risco contratual não abre exceção nenhuma na disciplina
  de dado pessoal.

## 4. Direitos do titular e canal de contato

Ainda que o dado pessoal não seja retido, o projeto mantém um canal de contato (o mesmo já
usado para o restante do Mercator) para qualquer titular que queira entender o que foi
processado sobre um anúncio seu — a resposta padrão, dado o desenho acima, é que nenhum dado
de contato pessoal foi retido, e o registro estrutural do imóvel (sem identificação) pode ser
localizado e removido mediante pedido razoável.
