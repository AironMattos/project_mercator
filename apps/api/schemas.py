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


# --- Radar Imobiliário (checkpoint 11e) ---------------------------------


class MetricaConstrucaoOut(BaseModel):
    """Alvará e CVCO sempre em campos separados, nunca somados numa
    métrica única de "atividade construtiva" (seção 3.1 do prompt de
    referência do Radar Imobiliário: respondem perguntas diferentes -
    "onde vai mudar" vs. "onde já mudou")."""

    territorio_id: str | None
    mes: date | None
    alvaras_aprovados: int
    area_licenciada_m2: float
    cvcos_concluidos: int
    area_concluida_m2: float
    # Só preenchidos no modo agregado por bairro (sem territorio_id no
    # filtro) - por mês a amostra é sempre pequena demais pra sustentar
    # uma mediana (ver PISO_MINIMO_PARES_DEFASAGEM). motivo_indisponivel
    # segue o mesmo vocabulário de indicadores.py
    # ("historico_insuficiente"), nunca escondendo um bairro com poucos
    # pares atrás de um número calculado sobre amostra fraca.
    defasagem_mediana_dias: float | None = None
    pares_alvara_cvco: int | None = None
    motivo_indisponivel_defasagem: str | None = None


class ValorReferenciaBairroOut(BaseModel):
    """Valor venal (PGV) por bairro - tipo_valor/componente/fonte_id
    sempre explícitos (regra das quatro grandezas, seção 1 do prompt de
    referência). Sem baseline/variacao_pct de propósito: PGV não é série
    temporal (seção 5, trava "PGV não é série temporal") - só nível e
    vigência."""

    territorio_id: str
    valor_m2_mediano: float
    tipo_valor: str
    componente: str
    quantidade_registros: int
    fonte_id: str
    metodologia: str | None
    vigencia_inicio: date


class ZoneamentoOut(BaseModel):
    objectid_fonte: int
    territorio_id: str | None
    cd_zona: str
    sg_zona: str
    nm_zona: str
    nm_grupo: str | None
    legislacao: str | None
    data_versao: str | None
    data_atualizacao: str | None
    geometry: dict[str, Any] | None


class BcbIndicadorOut(BaseModel):
    indicador: str
    categoria: str
    tipo_valor: str | None
    unidade: str
    leitura: float
    fonte_id: str


class ContextoBcbOut(BaseModel):
    granularidade: str = "uf"
    uf: str
    periodo_referencia: date | None
    indicadores: list[BcbIndicadorOut]


class QuintoandarSegmentoOut(BaseModel):
    segmento: str
    aluguel_m2: float
    variacao_mensal: float | None
    variacao_12m: float | None
    fonte_id: str


class ContextoQuintoandarOut(BaseModel):
    granularidade: str = "cidade"
    cidade: str
    periodo_referencia: date | None
    segmentos: list[QuintoandarSegmentoOut]


class CensoBairroOut(BaseModel):
    territorio_id: str
    populacao_total: int
    domicilios_total: int
    domicilios_particulares_ocupados: int
    area_km2: float | None
    densidade_domicilios_km2: float | None
    setores_agregados: int


class ContextoCensoOut(BaseModel):
    # "agregado por bairro" porque a fonte real é por setor censitário,
    # somado aqui - nunca implica um levantamento independente por
    # bairro (ver domain/contexto/models.py).
    granularidade: str = "setor_censitario_agregado_por_bairro"
    ano_referencia: int
    bairros: list[CensoBairroOut]


class ContextoImoveisOut(BaseModel):
    bcb: ContextoBcbOut
    quintoandar: ContextoQuintoandarOut
    censo: ContextoCensoOut


class ResolucaoTerritorioOut(BaseModel):
    total: int
    com_territorio_resolvido: int
    pct_territorio_resolvido: float


class LoteCadastralQualidadeOut(BaseModel):
    total: int
    sem_geometria: int
    sem_territorio: int


class QualidadeDadosImoveisOut(BaseModel):
    """Mesmo princípio de QualidadeDadosOut (comércio): fatos crus, sem
    nota nem score composto - seção "QUALIDADE DOS DADOS" (trava
    metodológica) do prompt de referência do Radar Imobiliário."""

    alvaras: ResolucaoTerritorioOut
    cvcos: ResolucaoTerritorioOut
    lote_cadastral: LoteCadastralQualidadeOut
    pgv_vigencia_inicio: date | None
    # Nomes deliberadamente distintos: "bairros_cobertos" é quantos
    # bairros têm pelo menos uma microrregião da PGV; "total_registros" é
    # a soma de microrregiões somadas em todos os bairros - os dois
    # números são reais e diferentes (achado do checkpoint 11c: um bairro
    # comum tem várias microrregiões), nunca colapsados num só.
    pgv_bairros_cobertos: int
    pgv_total_registros: int
    ultima_atualizacao_por_fonte: dict[str, datetime | None]


class TermometroBairroOut(BaseModel):
    """Uma linha do termômetro por bairro (checkpoint 12i, seção 2/10 do
    prompt de referência do Radar de Anúncios) - estoque e preço são
    reais (snapshot atual); `quadrante` fica sempre `None` hoje porque
    depende de baseline histórica que ainda não existe (ver
    checkpoint 12f/12g) - `motivo_indisponivel_quadrante` explica por
    quê, nunca um campo `None` em silêncio."""

    territorio_id: str
    estoque: int
    preco_mediano: float | None
    preco_p25: float | None
    preco_p75: float | None
    preco_m2_mediano: float | None
    amostra_preco_suficiente: bool
    quadrante: str | None = None
    motivo_indisponivel_quadrante: str = "historico_insuficiente"


class ResumoBairroAnuncioOut(BaseModel):
    """Painel de bairro do Radar de Anúncios (checkpoint 12i) - ordem dos
    campos aqui não importa pro schema, mas importa pra UI (seção 10:
    "preço mediano → variação 12m → estoque e sua variação → permanência
    mediana → quadrante → leitura cruzada → contexto de construção/valor
    venal"). Cada métrica indisponível vem com seu próprio motivo, nunca
    um None mudo."""

    territorio_id: str
    operacao: str
    tipologia: str | None

    estoque: int
    preco_mediano: float | None
    preco_p25: float | None
    preco_p75: float | None
    preco_m2_mediano: float | None
    amostra_preco_suficiente: bool

    variacao_preco_12m_pct: float | None = None
    motivo_indisponivel_variacao: str = "historico_insuficiente"
    estoque_variacao_pct: float | None = None
    motivo_indisponivel_estoque_variacao: str = "historico_insuficiente"
    permanencia_mediana_dias: float | None = None
    motivo_indisponivel_permanencia: str = "historico_insuficiente"
    quadrante: str | None = None
    motivo_indisponivel_quadrante: str = "historico_insuficiente"
    leitura_cruzada_defasagem_meses: int | None = None
    motivo_indisponivel_leitura_cruzada: str = "amostra_insuficiente"

    construcao_alvaras_aprovados: int | None
    construcao_cvcos_concluidos: int | None
    valor_venal_m2_mediano: float | None


class ProcedenciaFonteOut(BaseModel):
    """Painel de procedência ampliado (checkpoint 12i, seção 10) - por
    fonte: última atualização, cadência, volume observado no período e
    as duas taxas de qualidade (classificação de tipologia, resolução de
    bairro), separado por Apolar e por Chaves na Mão - nunca uma média
    silenciosa entre as duas (seção 1.2)."""

    fonte_id: str
    cadencia: str
    ultima_atualizacao: datetime | None
    total_observado_no_periodo: int
    taxa_classificacao_tipologia: float | None
    taxa_resolucao_bairro: float | None
