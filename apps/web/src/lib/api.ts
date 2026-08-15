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

export type Ordem = "desc" | "asc";

export type RankingFiltros = {
  categoriaId?: string;
  periodo?: string;
  limite?: number;
  ordem?: Ordem;
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
    ordem: filtros.ordem,
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

// Ranking por categoria (checkpoint 11b) - mesma mecânica do ranking por
// bairro, agrupado por categoria; cidade inteira por padrão, ou um bairro
// específico via territorioId (usado no perfil de bairro).
export type RankingCategoriaItem = {
  categoriaId: string;
  nome: string;
  valorAtual: number;
  baseline: number | null;
  variacaoPct: number | null;
  tendencia: "acelerando" | "desacelerando" | "estavel" | null;
  posicao: number;
  total: number;
};

export type RankingCategorias = {
  itens: RankingCategoriaItem[];
  abaixoDoPisoVolume: number;
};

type RankingCategoriaItemApi = {
  categoria_id: string;
  nome: string;
  valor_atual: number;
  baseline: number | null;
  variacao_pct: number | null;
  tendencia: RankingCategoriaItem["tendencia"];
  posicao: number;
  total: number;
};

type RankingCategoriasApi = {
  itens: RankingCategoriaItemApi[];
  abaixo_do_piso_volume: number;
};

export type RankingCategoriasFiltros = {
  territorioId?: string;
  periodo?: string;
  limite?: number;
  ordem?: Ordem;
};

export function getRankingCategorias(
  filtros: RankingCategoriasFiltros = {},
): Promise<RankingCategorias> {
  return fetchJson<RankingCategoriasApi>("/ranking/categorias", {
    territorio_id: filtros.territorioId,
    periodo: filtros.periodo,
    limite: filtros.limite !== undefined ? String(filtros.limite) : undefined,
    ordem: filtros.ordem,
  }).then((resposta) => ({
    itens: resposta.itens.map((i) => ({
      categoriaId: i.categoria_id,
      nome: i.nome,
      valorAtual: i.valor_atual,
      baseline: i.baseline,
      variacaoPct: i.variacao_pct,
      tendencia: i.tendencia,
      posicao: i.posicao,
      total: i.total,
    })),
    abaixoDoPisoVolume: resposta.abaixo_do_piso_volume,
  }));
}

// Sinais (checkpoint 11b) - destaques com critério explícito e fixo (ver
// GET /sinais no backend), nunca um score.
export type Sinal = {
  territorioId: string;
  nome: string;
  descricao: string;
  mesesConsecutivos: number;
};

export type Sinais = {
  itens: Sinal[];
  criterio: string;
  periodoReferencia: string | null;
  motivoIndisponivel: string | null;
};

type SinaisApi = {
  itens: Array<{
    territorio_id: string;
    nome: string;
    descricao: string;
    meses_consecutivos: number;
  }>;
  criterio: string;
  periodo_referencia: string | null;
  motivo_indisponivel: string | null;
};

export function getSinais(): Promise<Sinais> {
  return fetchJson<SinaisApi>("/sinais").then((r) => ({
    itens: r.itens.map((i) => ({
      territorioId: i.territorio_id,
      nome: i.nome,
      descricao: i.descricao,
      mesesConsecutivos: i.meses_consecutivos,
    })),
    criterio: r.criterio,
    periodoReferencia: r.periodo_referencia,
    motivoIndisponivel: r.motivo_indisponivel,
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

// Comparação de territórios (checkpoint 11c) - mesmo formato de
// BairroResumo, um item por bairro selecionado, lado a lado.
export type ComparacaoFiltros = {
  categoriaId?: string;
  periodo?: string;
  dataInicio?: string;
  dataFim?: string;
};

type ComparacaoApi = { itens: BairroResumoApi[] };

export function getComparacao(
  territorioIds: string[],
  filtros: ComparacaoFiltros = {},
): Promise<BairroResumo[]> {
  return fetchJson<ComparacaoApi>("/bairros/comparar", {
    ids: territorioIds.join(","),
    categoria_id: filtros.categoriaId,
    periodo: filtros.periodo,
    data_inicio: filtros.dataInicio,
    data_fim: filtros.dataFim,
  }).then((r) =>
    r.itens.map((item) => ({
      territorioId: item.territorio_id,
      nome: item.nome,
      periodo: item.periodo,
      aberturas: mapIndicador(item.aberturas),
      saldo: mapIndicador(item.saldo),
      posicaoRanking: item.posicao_ranking,
      totalRanking: item.total_ranking,
      quebraCategoria: item.quebra_categoria.map((c) => ({
        categoriaId: c.categoria_id,
        nome: c.nome,
        contagem: c.contagem,
      })),
      serieTemporal: item.serie_temporal.map((l) => ({
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
    })),
  );
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

export type PontoSerieRaio = { mes: string; aberturas: number; fechamentos: number };

export type ComparacaoBairroRaio = {
  territorioId: string;
  nome: string;
  aberturas: Indicador;
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
  // Investigação por endereço evoluída (checkpoint 11d).
  densidadeKm2: number;
  aberturas: number;
  fechamentos: number;
  saldo: number;
  turnover: number | null;
  quebraCategoria: QuebraCategoria[];
  serieTemporal: PontoSerieRaio[];
  comparacaoBairro: ComparacaoBairroRaio | null;
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
  densidade_km2: number;
  aberturas: number;
  fechamentos: number;
  saldo: number;
  turnover: number | null;
  quebra_categoria: Array<{ categoria_id: string | null; nome: string; contagem: number }>;
  serie_temporal: Array<{ mes: string; aberturas: number; fechamentos: number }>;
  comparacao_bairro: { territorio_id: string; nome: string; aberturas: IndicadorApi } | null;
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
    densidadeKm2: d.densidade_km2,
    aberturas: d.aberturas,
    fechamentos: d.fechamentos,
    saldo: d.saldo,
    turnover: d.turnover,
    quebraCategoria: d.quebra_categoria.map((c) => ({
      categoriaId: c.categoria_id,
      nome: c.nome,
      contagem: c.contagem,
    })),
    serieTemporal: d.serie_temporal,
    comparacaoBairro: d.comparacao_bairro
      ? {
          territorioId: d.comparacao_bairro.territorio_id,
          nome: d.comparacao_bairro.nome,
          aberturas: mapIndicador(d.comparacao_bairro.aberturas),
        }
      : null,
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

// Fatos objetivos sobre a base (checkpoint 11a) - nunca um "índice de
// confiança" composto, ver GET /qualidade-dados no backend.
export type QualidadeDados = {
  totalEstabelecimentos: number;
  geocodificadosAlta: number;
  geocodificadosMedia: number;
  geocodificadosBaixa: number;
  naoGeocodificados: number;
  pctLocalizacaoValida: number;
  coberturaTemporal: CoberturaTemporal;
  ultimaAtualizacao: string | null;
};

type QualidadeDadosApi = {
  total_estabelecimentos: number;
  geocodificados_alta: number;
  geocodificados_media: number;
  geocodificados_baixa: number;
  nao_geocodificados: number;
  pct_localizacao_valida: number;
  cobertura_temporal: { mes_inicio: string | null; mes_fim: string | null };
  ultima_atualizacao: string | null;
};

// --- Radar Imobiliário (checkpoint 11f) ---------------------------------

export type MetricaConstrucao = {
  territorioId: string | null;
  mes: string | null;
  alvarasAprovados: number;
  areaLicenciadaM2: number;
  cvcosConcluidos: number;
  areaConcluidaM2: number;
  // Só preenchidos no modo agregado por bairro (sem territorioId no
  // filtro) - por mês a amostra é sempre pequena demais pra uma mediana
  // (ver GET /imoveis/construcao no backend).
  defasagemMedianaDias: number | null;
  paresAlvaraCvco: number | null;
  motivoIndisponivelDefasagem: string | null;
};

type MetricaConstrucaoApi = {
  territorio_id: string | null;
  mes: string | null;
  alvaras_aprovados: number;
  area_licenciada_m2: number;
  cvcos_concluidos: number;
  area_concluida_m2: number;
  defasagem_mediana_dias: number | null;
  pares_alvara_cvco: number | null;
  motivo_indisponivel_defasagem: string | null;
};

function mapMetricaConstrucao(l: MetricaConstrucaoApi): MetricaConstrucao {
  return {
    territorioId: l.territorio_id,
    mes: l.mes,
    alvarasAprovados: l.alvaras_aprovados,
    areaLicenciadaM2: l.area_licenciada_m2,
    cvcosConcluidos: l.cvcos_concluidos,
    areaConcluidaM2: l.area_concluida_m2,
    defasagemMedianaDias: l.defasagem_mediana_dias,
    paresAlvaraCvco: l.pares_alvara_cvco,
    motivoIndisponivelDefasagem: l.motivo_indisponivel_defasagem,
  };
}

export type ConstrucaoFiltros = {
  territorioId?: string;
  dataInicio?: string;
  dataFim?: string;
};

export function getConstrucao(filtros: ConstrucaoFiltros = {}): Promise<MetricaConstrucao[]> {
  return fetchJson<MetricaConstrucaoApi[]>("/imoveis/construcao", {
    territorio_id: filtros.territorioId,
    data_inicio: filtros.dataInicio,
    data_fim: filtros.dataFim,
  }).then((linhas) => linhas.map(mapMetricaConstrucao));
}

// Valor venal (PGV) por bairro - tipo_valor/componente/fonte_id sempre
// explícitos (regra das quatro grandezas). Sem baseline/variação de
// propósito: PGV não é série temporal (ver /metodologia#imoveis-valor-referencia).
export type ValorReferenciaBairro = {
  territorioId: string;
  valorM2Mediano: number;
  tipoValor: string;
  componente: string;
  quantidadeRegistros: number;
  fonteId: string;
  metodologia: string | null;
  vigenciaInicio: string;
};

type ValorReferenciaBairroApi = {
  territorio_id: string;
  valor_m2_mediano: number;
  tipo_valor: string;
  componente: string;
  quantidade_registros: number;
  fonte_id: string;
  metodologia: string | null;
  vigencia_inicio: string;
};

export function getValorReferencia(territorioId?: string): Promise<ValorReferenciaBairro[]> {
  return fetchJson<ValorReferenciaBairroApi[]>("/imoveis/valor-referencia", {
    territorio_id: territorioId,
  }).then((linhas) =>
    linhas.map((l) => ({
      territorioId: l.territorio_id,
      valorM2Mediano: l.valor_m2_mediano,
      tipoValor: l.tipo_valor,
      componente: l.componente,
      quantidadeRegistros: l.quantidade_registros,
      fonteId: l.fonte_id,
      metodologia: l.metodologia,
      vigenciaInicio: l.vigencia_inicio,
    })),
  );
}

// GeoJSON de zoneamento - forma própria (não reaproveita GeoJsonFeatureCollection,
// que é específico das properties de dim_territorio) porque as properties
// aqui são as de canonical.zoneamento_territorial.
export type ZoneamentoFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: string; coordinates: unknown } | null;
    properties: {
      objectid_fonte: number;
      territorio_id: string | null;
      cd_zona: string;
      sg_zona: string;
      nm_zona: string;
      nm_grupo: string | null;
      legislacao: string | null;
      data_versao: string | null;
      data_atualizacao: string | null;
      fonte_id: string;
    };
  }>;
};

export function getZoneamento(territorioId?: string): Promise<ZoneamentoFeatureCollection> {
  return fetchJson<ZoneamentoFeatureCollection>("/imoveis/zoneamento", {
    territorio_id: territorioId,
  });
}

// Contexto de mercado/demografia (checkpoint 11d/11e) - cada fonte com sua
// própria granularidade (UF/cidade/setor censitário agregado por bairro),
// nunca apresentada como se fosse levantamento por bairro sem dizer isso.
export type BcbIndicador = {
  indicador: string;
  categoria: string;
  tipoValor: string | null;
  unidade: string;
  leitura: number;
  fonteId: string;
};

export type QuintoandarSegmento = {
  segmento: string;
  aluguelM2: number;
  variacaoMensal: number | null;
  variacao12m: number | null;
  fonteId: string;
};

export type CensoBairro = {
  territorioId: string;
  populacaoTotal: number;
  domiciliosTotal: number;
  domiciliosParticularesOcupados: number;
  areaKm2: number | null;
  densidadeDomiciliosKm2: number | null;
  setoresAgregados: number;
};

export type ContextoImoveis = {
  bcb: {
    granularidade: string;
    uf: string;
    periodoReferencia: string | null;
    indicadores: BcbIndicador[];
  };
  quintoandar: {
    granularidade: string;
    cidade: string;
    periodoReferencia: string | null;
    segmentos: QuintoandarSegmento[];
  };
  censo: {
    granularidade: string;
    anoReferencia: number;
    bairros: CensoBairro[];
  };
};

type ContextoImoveisApi = {
  bcb: {
    granularidade: string;
    uf: string;
    periodo_referencia: string | null;
    indicadores: Array<{
      indicador: string;
      categoria: string;
      tipo_valor: string | null;
      unidade: string;
      leitura: number;
      fonte_id: string;
    }>;
  };
  quintoandar: {
    granularidade: string;
    cidade: string;
    periodo_referencia: string | null;
    segmentos: Array<{
      segmento: string;
      aluguel_m2: number;
      variacao_mensal: number | null;
      variacao_12m: number | null;
      fonte_id: string;
    }>;
  };
  censo: {
    granularidade: string;
    ano_referencia: number;
    bairros: Array<{
      territorio_id: string;
      populacao_total: number;
      domicilios_total: number;
      domicilios_particulares_ocupados: number;
      area_km2: number | null;
      densidade_domicilios_km2: number | null;
      setores_agregados: number;
    }>;
  };
};

export function getContextoImoveis(): Promise<ContextoImoveis> {
  return fetchJson<ContextoImoveisApi>("/imoveis/contexto").then((r) => ({
    bcb: {
      granularidade: r.bcb.granularidade,
      uf: r.bcb.uf,
      periodoReferencia: r.bcb.periodo_referencia,
      indicadores: r.bcb.indicadores.map((i) => ({
        indicador: i.indicador,
        categoria: i.categoria,
        tipoValor: i.tipo_valor,
        unidade: i.unidade,
        leitura: i.leitura,
        fonteId: i.fonte_id,
      })),
    },
    quintoandar: {
      granularidade: r.quintoandar.granularidade,
      cidade: r.quintoandar.cidade,
      periodoReferencia: r.quintoandar.periodo_referencia,
      segmentos: r.quintoandar.segmentos.map((s) => ({
        segmento: s.segmento,
        aluguelM2: s.aluguel_m2,
        variacaoMensal: s.variacao_mensal,
        variacao12m: s.variacao_12m,
        fonteId: s.fonte_id,
      })),
    },
    censo: {
      granularidade: r.censo.granularidade,
      anoReferencia: r.censo.ano_referencia,
      bairros: r.censo.bairros.map((b) => ({
        territorioId: b.territorio_id,
        populacaoTotal: b.populacao_total,
        domiciliosTotal: b.domicilios_total,
        domiciliosParticularesOcupados: b.domicilios_particulares_ocupados,
        areaKm2: b.area_km2,
        densidadeDomiciliosKm2: b.densidade_domicilios_km2,
        setoresAgregados: b.setores_agregados,
      })),
    },
  }));
}

// Fatos objetivos sobre a base do Radar Imobiliário (checkpoint 11e) - mesmo
// princípio de getQualidadeDados (comércio): sem nota nem score composto.
export type QualidadeDadosImoveis = {
  alvaras: { total: number; comTerritorioResolvido: number; pctTerritorioResolvido: number };
  cvcos: { total: number; comTerritorioResolvido: number; pctTerritorioResolvido: number };
  loteCadastral: { total: number; semGeometria: number; semTerritorio: number };
  pgvVigenciaInicio: string | null;
  pgvBairrosCobertos: number;
  pgvTotalRegistros: number;
  ultimaAtualizacaoPorFonte: Record<string, string | null>;
};

type QualidadeDadosImoveisApi = {
  alvaras: { total: number; com_territorio_resolvido: number; pct_territorio_resolvido: number };
  cvcos: { total: number; com_territorio_resolvido: number; pct_territorio_resolvido: number };
  lote_cadastral: { total: number; sem_geometria: number; sem_territorio: number };
  pgv_vigencia_inicio: string | null;
  pgv_bairros_cobertos: number;
  pgv_total_registros: number;
  ultima_atualizacao_por_fonte: Record<string, string | null>;
};

export function getQualidadeDadosImoveis(): Promise<QualidadeDadosImoveis> {
  return fetchJson<QualidadeDadosImoveisApi>("/imoveis/qualidade-dados").then((r) => ({
    alvaras: {
      total: r.alvaras.total,
      comTerritorioResolvido: r.alvaras.com_territorio_resolvido,
      pctTerritorioResolvido: r.alvaras.pct_territorio_resolvido,
    },
    cvcos: {
      total: r.cvcos.total,
      comTerritorioResolvido: r.cvcos.com_territorio_resolvido,
      pctTerritorioResolvido: r.cvcos.pct_territorio_resolvido,
    },
    loteCadastral: {
      total: r.lote_cadastral.total,
      semGeometria: r.lote_cadastral.sem_geometria,
      semTerritorio: r.lote_cadastral.sem_territorio,
    },
    pgvVigenciaInicio: r.pgv_vigencia_inicio,
    pgvBairrosCobertos: r.pgv_bairros_cobertos,
    pgvTotalRegistros: r.pgv_total_registros,
    ultimaAtualizacaoPorFonte: r.ultima_atualizacao_por_fonte,
  }));
}

export function getQualidadeDados(): Promise<QualidadeDados> {
  return fetchJson<QualidadeDadosApi>("/qualidade-dados").then((r) => ({
    totalEstabelecimentos: r.total_estabelecimentos,
    geocodificadosAlta: r.geocodificados_alta,
    geocodificadosMedia: r.geocodificados_media,
    geocodificadosBaixa: r.geocodificados_baixa,
    naoGeocodificados: r.nao_geocodificados,
    pctLocalizacaoValida: r.pct_localizacao_valida,
    coberturaTemporal: {
      mesInicio: r.cobertura_temporal.mes_inicio,
      mesFim: r.cobertura_temporal.mes_fim,
    },
    ultimaAtualizacao: r.ultima_atualizacao,
  }));
}
