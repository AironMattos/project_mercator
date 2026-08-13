from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel


class CategoriaOut(BaseModel):
    categoria_id: str
    nome: str


class MetricaComercioOut(BaseModel):
    territorio_id: str | None
    categoria_id: str | None
    mes: date | None
    aberturas: int
    desaparecimentos: int
    saldo: int
    # baseline/variacao_pct/tendencia descrevem o indicador de ABERTURAS
    # calculado sobre INICIO_ATIVIDADE (profundidade real de anos), não o
    # campo "aberturas" acima (que é a contagem por evento de detecção -
    # só tem profundidade real a partir do par de snapshots já
    # comparados). Só vêm preenchidos no modo série temporal (com
    # territorio_id); no modo agregado por bairro (mapa, sem
    # territorio_id) não fazem sentido "por mês" e vêm None com
    # motivo_indisponivel="nao_aplicavel_sem_territorio_id".
    baseline: float | None = None
    variacao_pct: float | None = None
    tendencia: str | None = None
    motivo_indisponivel: str | None = None


class CoberturaTemporalOut(BaseModel):
    mes_inicio: date | None
    mes_fim: date | None


class IndicadorOut(BaseModel):
    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    tendencia: str | None
    motivo_indisponivel: str | None


class PontoSerieOut(BaseModel):
    mes: date
    valor: float


class RankingItemOut(BaseModel):
    territorio_id: str
    nome: str
    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    tendencia: str | None
    posicao: int
    total: int
    # Não estava no formato de resposta do prompt de referência - adicionado
    # pro sparkline do checkpoint 8c/3.1 (12 pontos, ver
    # servico_indicadores.MESES_SPARKLINE). Vazio quando o bairro não tem
    # nenhuma série resolvida (não deveria acontecer pra um item elegível,
    # mas o campo não é opcional pra evitar um "serie: null" no frontend).
    serie: list[PontoSerieOut] = []


class QuebraCategoriaOut(BaseModel):
    categoria_id: str | None
    nome: str
    contagem: int


class BairroResumoOut(BaseModel):
    territorio_id: str
    nome: str
    periodo: date
    aberturas: IndicadorOut
    saldo: IndicadorOut
    posicao_ranking: int | None
    total_ranking: int | None
    quebra_categoria: list[QuebraCategoriaOut]
    serie_temporal: list[MetricaComercioOut]


class GeoJsonFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any] | None
    properties: dict[str, Any]


class GeoJsonFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJsonFeature]


class PontoOut(BaseModel):
    lat: float
    lon: float


class EstabelecimentoRaioOut(BaseModel):
    entidade_id: uuid.UUID
    nome: str | None
    endereco: str | None
    categoria_id: str | None
    territorio_id: str | None
    distancia_m: float
    confianca: str
    ponto: PontoOut


class BuscaRaioOut(BaseModel):
    endereco_buscado: str
    ponto_busca: PontoOut
    raio_m: int
    categoria_id: str | None
    total: int
    estabelecimentos: list[EstabelecimentoRaioOut]
    # Visível, não escondido: quantos estabelecimentos estavam no raio mas
    # com confianca='baixa' (não entram na contagem principal) - checkpoint
    # 9, seção 5.
    excluidos_baixa_confianca: int
