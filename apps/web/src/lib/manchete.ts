import type { BairroResumo, BuscaRaio, Categoria, MetricaComercio, RankingItem } from "@/lib/api";
import { formatarValorCompacto } from "@/lib/indicadores";

/**
 * Geração de frase interpretativa (checkpoint 10b) - composição de template
 * a partir de campos já calculados pela API (baseline/variação/tendência/
 * categoria dominante), sem IA generativa. Cada tela principal usa a função
 * correspondente aqui, nunca escreve a frase inline - mesmo padrão dos
 * outros formatadores em lib/indicadores.ts.
 */

export function formatarRaioM(m: number): string {
  return m >= 1000 ? `${m / 1000}km` : `${m}m`;
}

function formatarPct(variacaoPct: number | null): string | null {
  if (variacaoPct === null) return null;
  const pct = Math.round(variacaoPct * 100);
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

// Mapa: deriva do mesmo dado que colore o coroplético (saldo por bairro no
// período filtrado) - de propósito, não do ranking de crescimento de
// aberturas (checkpoint 8b: os dois indicadores podem divergir pro mesmo
// bairro/mês). A frase precisa descrever exatamente o que está pintado no
// mapa abaixo dela, não outra métrica.
export function mancheteMapa(
  metricas: MetricaComercio[],
  nomesPorTerritorio: Map<string, string>,
): string {
  const comDado = metricas.filter((m) => m.territorio_id !== null);
  if (comDado.length === 0) {
    return "Nenhum evento registrado no bairro e período filtrados.";
  }

  const lider = comDado.reduce((max, atual) => (atual.saldo > max.saldo ? atual : max));
  const nome = nomesPorTerritorio.get(lider.territorio_id as string) ?? lider.territorio_id;
  const positivos = comDado.filter((m) => m.saldo > 0).length;

  if (lider.saldo <= 0) {
    return `Nenhum bairro com saldo de comércio positivo no período filtrado - ${nome} é o menos afetado, com saldo ${formatarValorCompacto(lider.saldo)}.`;
  }

  return `${nome} lidera o saldo de comércio do período, com +${formatarValorCompacto(lider.saldo)} (${positivos} de ${comDado.length} bairros com saldo positivo).`;
}

// Ranking: usa só campos que a API já devolve por item (variacao_pct,
// tendencia) - sem fetch adicional.
export function mancheteRanking(itens: RankingItem[]): string {
  if (itens.length === 0) {
    return "Nenhum bairro elegível para o ranking de crescimento neste filtro ainda.";
  }

  const lider = itens[0];
  const pct = formatarPct(lider.variacaoPct);
  const partes = [`${lider.nome} lidera o ranking de crescimento comercial`];
  if (pct) partes.push(`com ${pct} acima da média histórica`);
  if (lider.tendencia === "acelerando" || lider.tendencia === "desacelerando") {
    partes.push(lider.tendencia);
  }
  return partes.join(", ") + ".";
}

// Painel de detalhe: eleva o "#1 de 74..." (checkpoint 8d) pra frase
// completa, reaproveitando quebra_categoria (já buscado por
// GET /bairros/{id}/resumo, sem fetch adicional).
export function mancheteDetalheBairro(resumo: BairroResumo): string {
  const { nome, posicaoRanking, totalRanking, aberturas, quebraCategoria } = resumo;

  if (posicaoRanking === null || totalRanking === null) {
    // Duas razões distintas pra não estar no ranking (checkpoint 10d): sem
    // baseline calculável (motivoIndisponivel presente) vs. baseline
    // calculável mas abaixo do piso mínimo de volume - a frase não pode
    // afirmar "sem histórico" quando na verdade há um baseline real, só
    // baixo demais pra competir pelas primeiras posições.
    if (aberturas.motivoIndisponivel === null) {
      return `${nome} tem crescimento calculável (baseline de ${formatarValorCompacto(aberturas.baseline ?? 0)} aberturas), mas volume baixo demais pra competir no ranking principal.`;
    }
    return `${nome} ainda não tem histórico suficiente para entrar no ranking de crescimento.`;
  }

  const partes: string[] = [];
  if (posicaoRanking === 1) {
    partes.push(`${nome} lidera o crescimento comercial entre os ${totalRanking} bairros analisados`);
  } else if (posicaoRanking <= 5) {
    partes.push(`${nome} está entre os 5 bairros que mais cresceram em comércio (posição #${posicaoRanking} de ${totalRanking})`);
  } else if (posicaoRanking <= 10) {
    partes.push(`${nome} está entre os 10 bairros que mais cresceram em comércio (posição #${posicaoRanking} de ${totalRanking})`);
  } else {
    partes.push(`${nome} é #${posicaoRanking} de ${totalRanking} em crescimento de comércio`);
  }

  const pct = formatarPct(aberturas.variacaoPct);
  if (pct) partes.push(`${pct} acima da média histórica`);

  const categoriaDominante = quebraCategoria.find((c) => c.categoriaId !== null)?.nome;
  if (categoriaDominante) partes.push(`puxado por ${categoriaDominante}`);

  if (aberturas.tendencia === "acelerando" || aberturas.tendencia === "desacelerando") {
    partes.push(aberturas.tendencia);
  }

  return partes.join(", ") + ".";
}

// Busca por raio: com categoria já filtrada pelo backend, todo resultado já
// pertence a ela - só nomeia. Sem filtro, a "categoria dominante" é uma
// contagem simples sobre a lista de estabelecimentos já retornada (não é
// uma média/estatística nova - é o mesmo tipo de agregação de apresentação
// que quebra-categoria.tsx já faz com dado vindo pronto do backend).
export function mancheteBuscaRaio(
  resultado: BuscaRaio,
  categorias: Categoria[],
  nomeCategoriaFiltro?: string,
): string {
  const raioTexto = formatarRaioM(resultado.raioM);
  const plural = resultado.total === 1 ? "" : "s";

  if (nomeCategoriaFiltro) {
    return `Essa região tem ${resultado.total} estabelecimento${plural} de ${nomeCategoriaFiltro} num raio de ${raioTexto} de "${resultado.enderecoBuscado}".`;
  }

  const nomePorCategoria = new Map(categorias.map((c) => [c.categoria_id, c.nome]));
  const contagemPorCategoria = new Map<string, number>();
  for (const e of resultado.estabelecimentos) {
    if (!e.categoriaId) continue;
    contagemPorCategoria.set(e.categoriaId, (contagemPorCategoria.get(e.categoriaId) ?? 0) + 1);
  }

  let categoriaDominante: string | null = null;
  let maiorContagem = 0;
  for (const [categoriaId, contagem] of contagemPorCategoria) {
    if (contagem > maiorContagem) {
      maiorContagem = contagem;
      categoriaDominante = categoriaId;
    }
  }

  if (categoriaDominante) {
    const nome = nomePorCategoria.get(categoriaDominante) ?? categoriaDominante;
    return `Essa região tem alta concentração de ${nome} - ${maiorContagem} de ${resultado.total} estabelecimentos num raio de ${raioTexto} de "${resultado.enderecoBuscado}".`;
  }

  return `${resultado.total} estabelecimento${plural} encontrado${plural} num raio de ${raioTexto} de "${resultado.enderecoBuscado}".`;
}
