"""Orquestra calcular_correlacao_cruzada em duas etapas (checkpoint 12g,
seção 3.1 do prompt de referência, primeira trava obrigatória): "exija
que a relação se sustente no agregado da cidade antes de reportar
qualquer relação por bairro". Puro - recebe séries já montadas (dict de
território → série), não sabe de onde vieram."""
from __future__ import annotations

from dataclasses import dataclass

from analytics.features import PontoMensal
from analytics.features.cross.defasagem import (
    LAG_MAXIMO_PADRAO,
    ResultadoDefasagem,
    calcular_correlacao_cruzada,
    defasagem_mais_forte,
)


@dataclass(frozen=True)
class AnaliseDefasagem:
    resultados: list[ResultadoDefasagem]
    defasagem_maxima: ResultadoDefasagem | None


def analisar_defasagem_cidade(
    serie_comercio_cidade: list[PontoMensal],
    serie_anuncios_cidade: list[PontoMensal],
    *,
    lag_maximo: int = LAG_MAXIMO_PADRAO,
) -> AnaliseDefasagem:
    """Etapa 1 - agregado da cidade inteira, correção de Bonferroni
    sobre só os `2*lag_maximo+1` lags testados aqui (nenhum bairro ainda
    entrou na conta)."""
    resultados = calcular_correlacao_cruzada(
        serie_comercio_cidade, serie_anuncios_cidade, lag_maximo=lag_maximo
    )
    return AnaliseDefasagem(resultados=resultados, defasagem_maxima=defasagem_mais_forte(resultados))


def analisar_defasagem_por_bairro(
    analise_cidade: AnaliseDefasagem,
    series_comercio_por_bairro: dict[str, list[PontoMensal]],
    series_anuncios_por_bairro: dict[str, list[PontoMensal]],
    *,
    lag_maximo: int = LAG_MAXIMO_PADRAO,
) -> dict[str, AnaliseDefasagem] | None:
    """Etapa 2 - só roda se a etapa 1 encontrou uma defasagem
    significativa; caso contrário devolve `None` (a feature de leitura
    cruzada por bairro simplesmente não existe pra esta cidade agora -
    "isso é um resultado válido, não uma falha").

    A correção de Bonferroni aqui usa o número TOTAL de testes
    realizados nesta chamada (todos os bairros × todos os lags) - seção
    3.1: "~75 bairros × 13 defasagens × 2 direções... mais de 1.900
    testes", não cada bairro se corrigindo isoladamente como se fosse a
    única comparação feita."""
    if analise_cidade.defasagem_maxima is None:
        return None

    bairros = sorted(set(series_comercio_por_bairro) & set(series_anuncios_por_bairro))
    n_testes_totais = len(bairros) * (2 * lag_maximo + 1)
    if n_testes_totais == 0:
        return {}

    resultado: dict[str, AnaliseDefasagem] = {}
    for territorio_id in bairros:
        resultados = calcular_correlacao_cruzada(
            series_comercio_por_bairro[territorio_id],
            series_anuncios_por_bairro[territorio_id],
            lag_maximo=lag_maximo,
            n_testes=n_testes_totais,
        )
        resultado[territorio_id] = AnaliseDefasagem(
            resultados=resultados, defasagem_maxima=defasagem_mais_forte(resultados)
        )
    return resultado
