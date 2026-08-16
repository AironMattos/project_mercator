"""Pressão especulativa (checkpoint 12h, seção 5 do prompt de
referência) - "você quer entender como a cidade lida com especulação
imobiliária. O produto pode medir fenômenos associados a isso. O
produto não pode chamar nada de especulação". Cinco indicadores
mensuráveis, cada um nomeado pelo que ele é - nenhum score composto,
nenhum rótulo interpretativo agregado.

Puro (sem I/O), mesmo estilo pequeno-e-testável de
`anuncio_termometro.py`/`indicadores.py`. Quem monta os números reais
(consultas SQL) é responsabilidade do repositório/relatório."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

MOTIVO_AMOSTRA_INSUFICIENTE = "amostra_insuficiente"
MOTIVO_SEM_DADO = "sem_dado"

# Mesmo piso da seção 2.2 (analytics/features/anuncio_termometro) -
# concentração de ofertante e mediana de incremento de reanúncio são tão
# sensíveis a amostra pequena quanto preço mediano.
PISO_MINIMO_AMOSTRA = 30


@dataclass(frozen=True)
class TaxaReanuncio:
    """Indicador 1 (seção 5) - "reanúncio com preço maior". `taxa` =
    REANUNCIO ÷ ANUNCIO_ENCERRADO no mesmo período (que fração do que
    saiu de oferta voltou) - não confundir com uma taxa sobre o estoque
    total, que mediria outra coisa."""

    taxa: float | None
    mediana_incremento_pct: float | None
    n_reanuncios: int
    n_encerrados: int
    motivo_indisponivel: str | None


def calcular_taxa_reanuncio(
    n_reanuncios: int, n_encerrados: int, variacoes_incremento_pct: list[float]
) -> TaxaReanuncio:
    """`variacoes_incremento_pct` são as `variacao_pct` de cada REANUNCIO
    com preço conhecido nos dois lados (payload de `detectar_reanuncio`)
    - a mediana usa só os valores **positivos** (a seção 5 pede
    especificamente "reanúncio com preço MAIOR", não a mediana de toda
    variação de reanúncio, que incluiria repescagens mais baratas)."""
    taxa = (n_reanuncios / n_encerrados) if n_encerrados > 0 else None
    incrementos_positivos = [v for v in variacoes_incremento_pct if v > 0]
    mediana = statistics.median(incrementos_positivos) if incrementos_positivos else None
    motivo = None if (taxa is not None or mediana is not None) else MOTIVO_SEM_DADO
    return TaxaReanuncio(
        taxa=taxa,
        mediana_incremento_pct=mediana,
        n_reanuncios=n_reanuncios,
        n_encerrados=n_encerrados,
        motivo_indisponivel=motivo,
    )


@dataclass(frozen=True)
class OfertaPorDomicilioVago:
    """Indicador 3 (seção 5) - "oferta alta com ocupação baixa". Anúncios
    ativos ÷ domicílios particulares vagos (Censo 2022) por bairro -
    padrão observado, interpretação fica com quem lê (seção 3.2 do
    prompt de referência aplicada aqui também: "deixar a interpretação
    para quem lê")."""

    razao: float | None
    estoque_anuncios: int
    domicilios_vagos: int | None
    motivo_indisponivel: str | None


def calcular_oferta_por_domicilio_vago(
    estoque_anuncios: int, domicilios_vagos: int | None
) -> OfertaPorDomicilioVago:
    if not domicilios_vagos:
        return OfertaPorDomicilioVago(
            razao=None,
            estoque_anuncios=estoque_anuncios,
            domicilios_vagos=domicilios_vagos,
            motivo_indisponivel=MOTIVO_SEM_DADO,
        )
    return OfertaPorDomicilioVago(
        razao=estoque_anuncios / domicilios_vagos,
        estoque_anuncios=estoque_anuncios,
        domicilios_vagos=domicilios_vagos,
        motivo_indisponivel=None,
    )


@dataclass(frozen=True)
class ConcentracaoOfertante:
    """Indicador 4 (seção 5) - "concentração de anunciante". Mede
    concentração de oferta sem identificar ninguém: `ofertante_hash` é
    anonimizado e irreversível (domain.anuncio.models), nunca exposto -
    só a contagem por hash entra aqui, nunca o hash em si na saída."""

    pct_top5_ofertantes: float | None
    n_ofertantes_distintos: int
    n_anuncios_com_ofertante_conhecido: int
    motivo_indisponivel: str | None


def calcular_concentracao_ofertante(contagem_por_ofertante: list[int]) -> ConcentracaoOfertante:
    """`contagem_por_ofertante` é uma lista com um item por
    `ofertante_hash` distinto, cada um a contagem de anúncios ativos
    daquele ofertante (nunca o hash em si - só a magnitude)."""
    n_total = sum(contagem_por_ofertante)
    n_distintos = len(contagem_por_ofertante)
    if n_total < PISO_MINIMO_AMOSTRA:
        return ConcentracaoOfertante(
            pct_top5_ofertantes=None,
            n_ofertantes_distintos=n_distintos,
            n_anuncios_com_ofertante_conhecido=n_total,
            motivo_indisponivel=MOTIVO_AMOSTRA_INSUFICIENTE,
        )
    top5 = sorted(contagem_por_ofertante, reverse=True)[:5]
    return ConcentracaoOfertante(
        pct_top5_ofertantes=sum(top5) / n_total,
        n_ofertantes_distintos=n_distintos,
        n_anuncios_com_ofertante_conhecido=n_total,
        motivo_indisponivel=None,
    )


@dataclass(frozen=True)
class DescolamentoPedidoContratado:
    """Indicador 5 (seção 5) - "descolamento entre pedido e contratado".
    `razao` > 1 significa que o preço pedido mediano está acima do
    índice de contratos reais (QuintoAndar) - "a medida mais direta de
    'está se pedindo mais do que o mercado paga'"."""

    razao: float | None
    preco_pedido_mediano_m2: float | None
    indice_contratado_m2: float | None
    motivo_indisponivel: str | None


def calcular_descolamento_pedido_contratado(
    preco_pedido_mediano_m2: float | None, indice_contratado_m2: float | None
) -> DescolamentoPedidoContratado:
    if not preco_pedido_mediano_m2 or not indice_contratado_m2:
        return DescolamentoPedidoContratado(
            razao=None,
            preco_pedido_mediano_m2=preco_pedido_mediano_m2,
            indice_contratado_m2=indice_contratado_m2,
            motivo_indisponivel=MOTIVO_SEM_DADO,
        )
    return DescolamentoPedidoContratado(
        razao=preco_pedido_mediano_m2 / indice_contratado_m2,
        preco_pedido_mediano_m2=preco_pedido_mediano_m2,
        indice_contratado_m2=indice_contratado_m2,
        motivo_indisponivel=None,
    )


@dataclass(frozen=True)
class PrecoSemContrapartidaFisica:
    """Indicador 2 (seção 5) - "preço pedido subindo sem contrapartida
    física". `variacao_preco_pct` vem da baseline de preço do termômetro
    (checkpoint 12f/indicadores.py - ainda sem histórico suficiente
    hoje, ver CLAUDE.md). `houve_contrapartida` é True se houve
    ALVARA_APROVADO, OBRA_CONCLUIDA ou ZONEAMENTO_ALTERADO no bairro no
    mesmo período (Checkpoint 11, Radar Imobiliário - "aqui o
    Checkpoint 11 finalmente vira insumo analítico, não decoração")."""

    preco_subiu_sem_contrapartida: bool | None
    variacao_preco_pct: float | None
    houve_contrapartida: bool | None
    motivo_indisponivel: str | None


def avaliar_preco_sem_contrapartida_fisica(
    variacao_preco_pct: float | None, houve_contrapartida: bool | None
) -> PrecoSemContrapartidaFisica:
    if variacao_preco_pct is None:
        return PrecoSemContrapartidaFisica(
            preco_subiu_sem_contrapartida=None,
            variacao_preco_pct=None,
            houve_contrapartida=houve_contrapartida,
            motivo_indisponivel=MOTIVO_AMOSTRA_INSUFICIENTE,
        )
    preco_subiu = variacao_preco_pct > 0
    resultado = preco_subiu and not bool(houve_contrapartida)
    return PrecoSemContrapartidaFisica(
        preco_subiu_sem_contrapartida=resultado,
        variacao_preco_pct=variacao_preco_pct,
        houve_contrapartida=houve_contrapartida,
        motivo_indisponivel=None,
    )
