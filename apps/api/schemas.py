from __future__ import annotations

import uuid
from datetime import date, datetime
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


class QualidadeDadosOut(BaseModel):
    """Fatos objetivos sobre a base, sem nota/score - seção "QUALIDADE DOS
    DADOS" do prompt de referência da fase de inteligência territorial.
    `pct_localizacao_valida` conta confianca alta+media como "válida"
    (mesmo corte de CONFIANCAS_NA_CONTAGEM_PRINCIPAL em busca_raio.py -
    'baixa' é a confiança que já é tratada como "não confiável o
    suficiente pra uso espacial" no resto do produto)."""

    total_estabelecimentos: int
    geocodificados_alta: int
    geocodificados_media: int
    geocodificados_baixa: int
    nao_geocodificados: int
    pct_localizacao_valida: float
    cobertura_temporal: CoberturaTemporalOut
    ultima_atualizacao: datetime | None


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


class RankingOut(BaseModel):
    itens: list[RankingItemOut]
    # Bairros com variacao_pct calculável mas baseline abaixo do piso
    # mínimo de volume (checkpoint 10d) - não competem pelas primeiras
    # posições (ruído estatístico de baixo volume), mas a contagem fica
    # visível aqui, não escondida - mesmo padrão de
    # excluidos_baixa_confianca em busca-raio.
    abaixo_do_piso_volume: int


class RankingCategoriaItemOut(BaseModel):
    categoria_id: str
    nome: str
    valor_atual: float
    baseline: float | None
    variacao_pct: float | None
    tendencia: str | None
    posicao: int
    total: int


class RankingCategoriasOut(BaseModel):
    itens: list[RankingCategoriaItemOut]
    # Mesmo padrão de RankingOut.abaixo_do_piso_volume - visível, não
    # escondido.
    abaixo_do_piso_volume: int


class SinalOut(BaseModel):
    territorio_id: str
    nome: str
    descricao: str
    meses_consecutivos: int


class SinaisOut(BaseModel):
    itens: list[SinalOut]
    # Texto exato do critério usado para gerar `itens` - nunca um score
    # escondido (seção "SINAIS E DESTAQUES" do prompt de referência).
    criterio: str
    periodo_referencia: date | None
    motivo_indisponivel: str | None


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


class ComparacaoOut(BaseModel):
    # Mesmo formato de BairroResumoOut, lado a lado - nenhuma nota/ranking
    # agregado comparando os itens entre si (seção "COMPARAÇÃO" do prompt
    # de referência: a comparação apresenta os dados, não decide "qual
    # bairro é melhor").
    itens: list[BairroResumoOut]


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


class PontoSerieRaioOut(BaseModel):
    mes: date
    aberturas: int
    fechamentos: int


class ComparacaoBairroRaioOut(BaseModel):
    # Mesmo indicador de aberturas exposto em /bairros/{id}/resumo pro
    # bairro majoritário entre os estabelecimentos do raio - dois números
    # com o mesmo rótulo lado a lado, nunca um score comparando os dois
    # (mesmo princípio da seção "COMPARAÇÃO" aplicado aqui).
    territorio_id: str
    nome: str
    aberturas: IndicadorOut


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
    # Investigação por endereço evoluída (checkpoint 11d) - densidade não
    # depende de nenhuma geometria de bairro, só da área do próprio círculo
    # de busca (raio conhecido analiticamente). aberturas/fechamentos/saldo
    # vêm de eventos geolocalizados dentro do raio - histórico real curto
    # (mesma limitação documentada em /metodologia), por isso não têm
    # baseline/tendência aqui, só a contagem do período coberto.
    densidade_km2: float
    aberturas: int
    fechamentos: int
    saldo: int
    # None quando não há estabelecimento nenhum no raio (estoque=0,
    # turnover indefinido - mesma lógica de baseline_zero em indicadores.py,
    # não é "infinito").
    turnover: float | None
    quebra_categoria: list[QuebraCategoriaOut]
    serie_temporal: list[PontoSerieRaioOut]
    # None quando o raio não tem nenhum estabelecimento com bairro
    # resolvido.
    comparacao_bairro: ComparacaoBairroRaioOut | None
