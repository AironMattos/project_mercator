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

export function getMetricasComercio(
  filtros: MetricasComercioFiltros = {},
): Promise<MetricaComercio[]> {
  return fetchJson<MetricaComercio[]>("/metricas/comercio", {
    territorio_id: filtros.territorioId,
    categoria_id: filtros.categoriaId,
    data_inicio: filtros.dataInicio,
    data_fim: filtros.dataFim,
  });
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
