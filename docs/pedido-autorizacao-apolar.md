# Pedido de autorização — Apolar (rascunho, não enviado)

Preparado como parte do Checkpoint 12a do Radar de Anúncios (`docs/fontes-anuncios.md`, seção
1). **Este texto não foi enviado** — enviar mensagem em nome do projeto para um terceiro é uma
ação que exige decisão e execução do dono do projeto, não algo que a IA faz sozinha. Revise,
ajuste o que fizer sentido (em especial os campos `[ ]`) e envie pelo formulário de contato em
`https://www.apolar.com.br/fale-conosco/` (não há e-mail institucional público — se houver um
contato direto já estabelecido com a Apolar fora deste projeto, prefira esse canal).

Depois de enviar, registre a data do envio e a resposta (ou a ausência dela, após ~10 dias
úteis) em `docs/fontes-anuncios.md`, seção 1 — é o veredito que decide se o coletor da Apolar
roda com autorização documentada ou sob as regras conservadoras de fonte sem autorização
expressa (seção 7 do prompt de referência do Radar de Anúncios).

---

**Assunto:** Uso agregado de dados públicos de anúncio — projeto de pesquisa territorial
(Mercator)

Olá,

Meu nome é [NOME], responsável pelo projeto Mercator — uma plataforma de inteligência
territorial para Curitiba que já mapeia abertura/fechamento de comércio e atividade de
construção civil por bairro, a partir de bases públicas (Prefeitura, IPPUC, IBGE, Banco
Central). Estou expandindo o projeto para incluir uma leitura sobre o mercado de anúncios
imobiliários — preço pedido, tempo de permanência da oferta e rotação, por bairro e tipo de
imóvel — e a Apolar é uma das duas fontes que eu gostaria de usar para isso em Curitiba.

Gostaria de pedir autorização formal para coletar, semanalmente, os campos estruturados
públicos das páginas de anúncio do site da Apolar (`apolar.com.br`) referentes a Curitiba e
região metropolitana:

- **O que é coletado**: tipologia do imóvel, bairro, área, quartos, banheiros, vagas, andar,
  preço pedido, condomínio e IPTU (quando publicados) — nada além de campos estruturados.
- **O que nunca é coletado nem armazenado**: fotos, texto descritivo do anúncio, nome,
  telefone, e-mail ou registro profissional (CRECI) de corretor/anunciante. Esses dados são
  descartados no momento do processamento, nunca chegam a ser persistidos em nenhuma etapa.
- **Como é usado**: só de forma agregada — médias, medianas e contagens por bairro e por mês.
  Nenhum anúncio individual, foto, link ou identificação de anunciante é exibido, publicado ou
  redistribuído pelo projeto, em nenhuma tela ou exportação.
- **Cadência**: uma coleta por semana, respeitando um limite de 1 requisição a cada 3 segundos
  — não é uma coleta contínua nem em alta frequência, e a coleta é feita exclusivamente a
  partir do sitemap público do site, nunca da busca interna.
- **Identificação**: a coleta se identifica com um user-agent próprio, com contato de e-mail,
  para que qualquer time da Apolar consiga reconhecer e, se quiser, pausar ou ajustar o tráfego
  a qualquer momento.

Se for útil, posso compartilhar a avaliação de interesse legítimo (LGPD) que documentei
internamente para este uso, ou conversar por chamada para tirar qualquer dúvida.

Fico à disposição.

[NOME]
[CONTATO — e-mail/telefone]
[Link do projeto, se já houver algo publicável]
