export type GeoJsonFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: {
      type: string;
      coordinates: unknown;
    } | null;
    properties: {
      territorio_id: string;
      nome: string;
      nivel: string;
      territorio_pai_id: string | null;
      cidade_id: string;
    };
  }>;
};

export type Categoria = {
  categoria_id: string;
  nome: string;
};

export type MetricaComercio = {
  territorio_id: string | null;
  categoria_id: string | null;
  mes: string | null;
  aberturas: number;
  desaparecimentos: number;
  saldo: number;
  // Indicador de aberturas via INICIO_ATIVIDADE (não o campo "aberturas"
  // acima, que é por evento de detecção) - ver checkpoint 8b. Só vem
  // preenchido no modo série temporal (com territorio_id).
  baseline: number | null;
  variacaoPct: number | null;
  tendencia: "acelerando" | "desacelerando" | "estavel" | null;
  motivoIndisponivel: string | null;
};

export type PontoSerie = {
  mes: string;
  valor: number;
};

export type RankingItem = {
  territorioId: string;
  nome: string;
  valorAtual: number;
  baseline: number | null;
  variacaoPct: number | null;
  tendencia: "acelerando" | "desacelerando" | "estavel" | null;
  posicao: number;
  total: number;
  serie: PontoSerie[];
};

export type RankingFiltros = {
  categoriaId?: string;
  periodo?: string;
  limite?: number;
};

export type Indicador = {
  valorAtual: number;
  baseline: number | null;
  variacaoPct: number | null;
  tendencia: "acelerando" | "desacelerando" | "estavel" | null;
  motivoIndisponivel: string | null;
};

export type QuebraCategoria = {
  categoriaId: string | null;
  nome: string;
  contagem: number;
};

export type BairroResumo = {
  territorioId: string;
  nome: string;
  periodo: string;
  aberturas: Indicador;
  saldo: Indicador;
  posicaoRanking: number | null;
  totalRanking: number | null;
  quebraCategoria: QuebraCategoria[];
  serieTemporal: MetricaComercio[];
};

export type MetricasComercioFiltros = {
  territorioId?: string;
  categoriaId?: string;
  dataInicio?: string;
  dataFim?: string;
};

export type CoberturaTemporal = {
  mesInicio: string | null;
  mesFim: string | null;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(
  path: string,
  params?: Record<string, string | undefined>,
): Promise<T> {
  const url = new URL(path, API_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value) url.searchParams.set(key, value);
    }
  }

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Falha ao chamar ${url.pathname} (HTTP ${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function getTerritorios(): Promise<GeoJsonFeatureCollection> {
  return fetchJson<GeoJsonFeatureCollection>("/territorios");
}

export function getCategorias(): Promise<Categoria[]> {
  return fetchJson<Categoria[]>("/categorias");
}

type MetricaComercioApi = {
  territorio_id: string | null;
  categoria_id: string | null;
  mes: string | null;
  aberturas: number;
  desaparecimentos: number;
  saldo: number;
  baseline: number | null;
  variacao_pct: number | null;
  tendencia: MetricaComercio["tendencia"];
  motivo_indisponivel: string | null;
};

export function getMetricasComercio(
  filtros: MetricasComercioFiltros = {},
): Promise<MetricaComercio[]> {
  return fetchJson<MetricaComercioApi[]>("/metricas/comercio", {
    territorio_id: filtros.territorioId,
    categoria_id: filtros.categoriaId,
    data_inicio: filtros.dataInicio,
    data_fim: filtros.dataFim,
  }).then((linhas) =>
    linhas.map((l) => ({
      territorio_id: l.territorio_id,
      categoria_id: l.categoria_id,
      mes: l.mes,
      aberturas: l.aberturas,
      desaparecimentos: l.desaparecimentos,
      saldo: l.saldo,
      baseline: l.baseline,
      variacaoPct: l.variacao_pct,
      tendencia: l.tendencia,
      motivoIndisponivel: l.motivo_indisponivel,
    })),
  );
}

type RankingItemApi = {
  territorio_id: string;
  nome: string;
  valor_atual: number;
  baseline: number | null;
  variacao_pct: number | null;
  tendencia: RankingItem["tendencia"];
  posicao: number;
  total: number;
  serie: PontoSerie[];
};

type RankingApi = {
  itens: RankingItemApi[];
  // Bairros com variacao_pct calculável mas baseline abaixo do piso mínimo
  // de volume (checkpoint 10d) - fora de `itens`, mas contados aqui, não
  // escondidos (mesmo padrão de excluidosBaixaConfianca em busca-raio).
  abaixo_do_piso_volume: number;
};

export type Ranking = {
  itens: RankingItem[];
  abaixoDoPisoVolume: number;
};

export function getRanking(filtros: RankingFiltros = {}): Promise<Ranking> {
  return fetchJson<RankingApi>("/ranking/comercio", {
    categoria_id: filtros.categoriaId,
    periodo: filtros.periodo,
    limite: filtros.limite !== undefined ? String(filtros.limite) : undefined,
  }).then((resposta) => ({
    itens: resposta.itens.map((i) => ({
      territorioId: i.territorio_id,
      nome: i.nome,
      valorAtual: i.valor_atual,
      baseline: i.baseline,
      variacaoPct: i.variacao_pct,
      tendencia: i.tendencia,
      posicao: i.posicao,
      total: i.total,
      serie: i.serie,
    })),
    abaixoDoPisoVolume: resposta.abaixo_do_piso_volume,
  }));
}

type IndicadorApi = {
  valor_atual: number;
  baseline: number | null;
  variacao_pct: number | null;
  tendencia: Indicador["tendencia"];
  motivo_indisponivel: string | null;
};

function mapIndicador(i: IndicadorApi): Indicador {
  return {
    valorAtual: i.valor_atual,
    baseline: i.baseline,
    variacaoPct: i.variacao_pct,
    tendencia: i.tendencia,
    motivoIndisponivel: i.motivo_indisponivel,
  };
}

type BairroResumoApi = {
  territorio_id: string;
  nome: string;
  periodo: string;
  aberturas: IndicadorApi;
  saldo: IndicadorApi;
  posicao_ranking: number | null;
  total_ranking: number | null;
  quebra_categoria: Array<{ categoria_id: string | null; nome: string; contagem: number }>;
  serie_temporal: MetricaComercioApi[];
};

export type BairroResumoFiltros = {
  categoriaId?: string;
  periodo?: string;
  dataInicio?: string;
  dataFim?: string;
};

export function getBairroResumo(
  territorioId: string,
  filtros: BairroResumoFiltros = {},
): Promise<BairroResumo> {
  return fetchJson<BairroResumoApi>(`/bairros/${encodeURIComponent(territorioId)}/resumo`, {
    categoria_id: filtros.categoriaId,
    periodo: filtros.periodo,
    data_inicio: filtros.dataInicio,
    data_fim: filtros.dataFim,
  }).then((r) => ({
    territorioId: r.territorio_id,
    nome: r.nome,
    periodo: r.periodo,
    aberturas: mapIndicador(r.aberturas),
    saldo: mapIndicador(r.saldo),
    posicaoRanking: r.posicao_ranking,
    totalRanking: r.total_ranking,
    quebraCategoria: r.quebra_categoria.map((c) => ({
      categoriaId: c.categoria_id,
      nome: c.nome,
      contagem: c.contagem,
    })),
    serieTemporal: r.serie_temporal.map((l) => ({
      territorio_id: l.territorio_id,
      categoria_id: l.categoria_id,
      mes: l.mes,
      aberturas: l.aberturas,
      desaparecimentos: l.desaparecimentos,
      saldo: l.saldo,
      baseline: l.baseline,
      variacaoPct: l.variacao_pct,
      tendencia: l.tendencia,
      motivoIndisponivel: l.motivo_indisponivel,
    })),
  }));
}

export type EstabelecimentoRaio = {
  entidadeId: string;
  nome: string | null;
  endereco: string | null;
  categoriaId: string | null;
  territorioId: string | null;
  distanciaM: number;
  confianca: "alta" | "media" | "baixa";
  ponto: { lat: number; lon: number };
};

export type BuscaRaio = {
  enderecoBuscado: string;
  pontoBusca: { lat: number; lon: number };
  raioM: number;
  categoriaId: string | null;
  total: number;
  estabelecimentos: EstabelecimentoRaio[];
  // Visível, não escondido: quantos estavam no raio mas com confianca='baixa'
  // (não entram na contagem principal) - checkpoint 9, seção 5/6.
  excluidosBaixaConfianca: number;
};

// Erro tipado pra distinguir "endereço não encontrado" (404) de "endereço
// ambíguo" (422) de qualquer outra falha - o painel de busca por raio
// precisa de uma mensagem diferente pra cada um (seção 6 do checkpoint 9),
// não um "algo deu errado" genérico.
export class BuscaRaioError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type BuscaRaioApi = {
  endereco_buscado: string;
  ponto_busca: { lat: number; lon: number };
  raio_m: number;
  categoria_id: string | null;
  total: number;
  estabelecimentos: Array<{
    entidade_id: string;
    nome: string | null;
    endereco: string | null;
    categoria_id: string | null;
    territorio_id: string | null;
    distancia_m: number;
    confianca: "alta" | "media" | "baixa";
    ponto: { lat: number; lon: number };
  }>;
  excluidos_baixa_confianca: number;
};

export async function getBuscaRaio(
  endereco: string,
  raioM: number,
  categoriaId?: string,
): Promise<BuscaRaio> {
  const url = new URL("/busca-raio", API_URL);
  url.searchParams.set("endereco", endereco);
  url.searchParams.set("raio_m", String(raioM));
  if (categoriaId) url.searchParams.set("categoria_id", categoriaId);

  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const corpo = await res.json().catch(() => null);
    const mensagem =
      (corpo as { detail?: string } | null)?.detail ?? `Falha ao buscar (HTTP ${res.status})`;
    throw new BuscaRaioError(res.status, mensagem);
  }

  const d = (await res.json()) as BuscaRaioApi;
  return {
    enderecoBuscado: d.endereco_buscado,
    pontoBusca: d.ponto_busca,
    raioM: d.raio_m,
    categoriaId: d.categoria_id,
    total: d.total,
    estabelecimentos: d.estabelecimentos.map((e) => ({
      entidadeId: e.entidade_id,
      nome: e.nome,
      endereco: e.endereco,
      categoriaId: e.categoria_id,
      territorioId: e.territorio_id,
      distanciaM: e.distancia_m,
      confianca: e.confianca,
      ponto: e.ponto,
    })),
    excluidosBaixaConfianca: d.excluidos_baixa_confianca,
  };
}

// Primeiro/último mês com evento real processado - não confundir com o
// range do preset de período selecionado no filtro (ver achado da
// auditoria de 2026-08-12: "últimos 12 meses" no filtro parecia sugerir 12
// meses de atividade real, mas só havia 1 mês de comparação processado).
export function getCoberturaTemporal(): Promise<CoberturaTemporal> {
  return fetchJson<{ mes_inicio: string | null; mes_fim: string | null }>(
    "/metricas/cobertura",
  ).then((r) => ({ mesInicio: r.mes_inicio, mesFim: r.mes_fim }));
}
