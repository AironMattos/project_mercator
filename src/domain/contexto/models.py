from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Segmentos publicados pelo Índice QuintoAndar/Imovelweb (checkpoint 11d) -
# 'city' vira o agregado da cidade toda, os demais são por dormitórios. Lista
# fechada porque o CSV público não documenta se outros valores podem
# aparecer no futuro (ex.: "4+") - um valor novo deve ser um achado
# investigado, não um segmento silenciosamente ignorado.
SEGMENTOS_ALUGUEL_VALIDOS = frozenset(
    {"cidade_toda", "1_dormitorio", "2_dormitorios", "3_dormitorios"}
)


@dataclass(frozen=True)
class IndicadorAluguelMercado:
    """Uma leitura mensal do Índice QuintoAndar/Imovelweb de aluguel para
    uma cidade - deliberadamente fora de domain/valuation: aluguel é uma
    grandeza econômica diferente das quatro que
    domain.valuation.TIPOS_VALOR_VALIDOS cobre (venal/avaliação/anúncio/
    transação, todas sobre preço de COMPRA de imóvel) - nunca rotular
    aluguel_m2 como um desses tipo_valor.

    aluguel_m2 é inferido como R$/m² por mês (não confirmado em texto
    explícito na documentação pública da QuintoAndar - magnitude
    conferida por checkpoint 11d contra `relatorio_cv.csv`, que dá preço
    de venda por m² na mesma ordem de grandeza esperada para o retorno de
    aluguel residencial brasileiro; ver docs/fontes-imobiliario.md)."""

    cidade: str
    periodo_referencia: date
    segmento: str
    aluguel_m2: float
    fonte_id: str
    snapshot_ref: str
    variacao_mensal: float | None = None
    variacao_12m: float | None = None

    def __post_init__(self) -> None:
        if not self.cidade:
            raise ValueError("cidade não pode ser vazia")
        if self.segmento not in SEGMENTOS_ALUGUEL_VALIDOS:
            raise ValueError(
                f"segmento inválido: {self.segmento!r}. "
                f"Deve ser um de {sorted(SEGMENTOS_ALUGUEL_VALIDOS)}"
            )
        if self.aluguel_m2 < 0:
            raise ValueError("aluguel_m2 não pode ser negativo")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")


# Índice FipeZAP (checkpoint 12b) publica dois relatórios mensais
# separados por operação - nunca combine variação/preço de venda com o
# de locação no mesmo agregado, mesmo espírito de nunca misturar
# tipo_valor (domain.valuation) ou operacao (domain.anuncio).
OPERACOES_FIPEZAP_VALIDAS = frozenset({"venda", "locacao"})


@dataclass(frozen=True)
class IndicadorFipezapCidade:
    """Leitura mensal do Índice FipeZAP para uma cidade inteira (seção 9
    do prompt de referência do Radar de Anúncios, checkpoint 12b) - a
    "segunda régua" de validação para o preço pedido calculado a partir
    dos anúncios coletados (Apolar/Chaves na Mão).

    **Nunca exposta via API pública nem redistribuída** - a Fipe não
    publica licença de redistribuição para este dado (só o PDF mensal em
    si, de acesso público); uso é estritamente interno, para comparar
    contra o preço pedido mediano calculado pelo produto. Essa restrição
    é responsabilidade da camada de API/UI (nunca construir um endpoint
    público que devolva isto), não algo que este dataclass force
    sozinho.
    """

    cidade: str
    operacao: str
    periodo_referencia: date
    preco_medio_m2: float
    fonte_id: str
    snapshot_ref: str
    variacao_mensal: float | None = None
    variacao_acumulada_ano: float | None = None
    variacao_12m: float | None = None

    def __post_init__(self) -> None:
        if not self.cidade:
            raise ValueError("cidade não pode ser vazia")
        if self.operacao not in OPERACOES_FIPEZAP_VALIDAS:
            raise ValueError(
                f"operacao inválida: {self.operacao!r}. "
                f"Deve ser uma de {sorted(OPERACOES_FIPEZAP_VALIDAS)}"
            )
        if self.preco_medio_m2 < 0:
            raise ValueError("preco_medio_m2 não pode ser negativo")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")


@dataclass(frozen=True)
class IndicadorFipezapBairro:
    """Um dos "bairros mais representativos" de uma cidade no Índice
    FipeZAP (checkpoint 12b, mesma restrição de uso interno do
    `IndicadorFipezapCidade` acima). A própria Fipe declara, no rodapé do
    relatório, que não publica dado mais granular que esta lista curta -
    "a Fipe não divulga informações detalhadas ou tabelas de preço médio
    por zona, distrito ou bairro" - então este é o teto de granularidade
    disponível na fonte, não uma amostra arbitrária escolhida por este
    projeto.

    `bairro_nome` é o nome exatamente como impresso no PDF - achado real
    do checkpoint 12b: o relatório às vezes trunca nomes longos com "…"
    (ex.: "CIDADE INDUSTRIAL DE…" em vez de "CIDADE INDUSTRIAL DE
    CURITIBA"), inconsistentemente entre venda e locação do mesmo mês.
    `territorio_id` é melhor esforço (None quando não resolvido, nunca
    inventado - mesmo tratamento de bairro não resolvido do resto do
    projeto)."""

    cidade: str
    operacao: str
    periodo_referencia: date
    bairro_nome: str
    preco_medio_m2: float
    fonte_id: str
    snapshot_ref: str
    variacao_12m: float | None = None
    territorio_id: str | None = None

    def __post_init__(self) -> None:
        if not self.cidade:
            raise ValueError("cidade não pode ser vazia")
        if self.operacao not in OPERACOES_FIPEZAP_VALIDAS:
            raise ValueError(
                f"operacao inválida: {self.operacao!r}. "
                f"Deve ser uma de {sorted(OPERACOES_FIPEZAP_VALIDAS)}"
            )
        if not self.bairro_nome:
            raise ValueError("bairro_nome não pode ser vazio")
        if self.preco_medio_m2 < 0:
            raise ValueError("preco_medio_m2 não pode ser negativo")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")


@dataclass(frozen=True)
class IndicadorCensitarioSetor:
    """Um setor censitário do Censo 2022 (agregados básicos - domicílios/
    população), checkpoint 11d. territorio_id é resolvido por nome de
    bairro (mesmo padrão slugify de ippuc_pgv/geocuritiba_cadastro) - o
    Censo já carrega NM_BAIRRO por setor (achado do checkpoint 11d,
    diferente do desenho original que previa precisar de join espacial);
    None quando o nome não bate contra dim_territorio, nunca inventado.

    Sem geometria do setor nesta tabela, de propósito (comece simples):
    o checkpoint 11d só precisa dos atributos por setor para alimentar a
    métrica de densidade do checkpoint 11e via soma por bairro, não de um
    polígono por setor - a malha espacial fica documentada como
    disponível, não buscada aqui (ver docs/fontes-imobiliario.md)."""

    setor_censitario: str
    municipio_codigo: str
    area_km2: float
    populacao_total: int
    domicilios_total: int
    domicilios_particulares_ocupados: int
    domicilios_particulares_vagos: int
    ano_referencia: int
    fonte_id: str
    snapshot_ref: str
    territorio_id: str | None = None

    def __post_init__(self) -> None:
        if not self.setor_censitario:
            raise ValueError("setor_censitario não pode ser vazio")
        if not self.municipio_codigo:
            raise ValueError("municipio_codigo não pode ser vazio")
        if self.area_km2 < 0:
            raise ValueError("area_km2 não pode ser negativa")
        if self.populacao_total < 0:
            raise ValueError("populacao_total não pode ser negativo")
        if self.domicilios_total < 0:
            raise ValueError("domicilios_total não pode ser negativo")
        if self.domicilios_particulares_ocupados < 0:
            raise ValueError("domicilios_particulares_ocupados não pode ser negativo")
        if self.domicilios_particulares_vagos < 0:
            raise ValueError("domicilios_particulares_vagos não pode ser negativo")
        if self.ano_referencia <= 0:
            raise ValueError("ano_referencia inválido")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")
