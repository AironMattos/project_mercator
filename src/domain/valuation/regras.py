from __future__ import annotations

from collections.abc import Iterable
from statistics import median

from domain.valuation.models import ValorMonetario


def media_valor_m2(valores: Iterable[ValorMonetario]) -> float:
    """Média simples de valor_m2. Só é permitida dentro do mesmo
    tipo_valor e do mesmo componente - misturar, por exemplo, valor
    venal de terreno com valor de avaliação de construção produz um
    número sintaticamente válido mas sem significado nenhum. A checagem
    fica aqui, não em quem monta o agregado, porque é exatamente o tipo
    de erro que passaria despercebido numa query SQL solta."""
    lista = list(valores)
    if not lista:
        raise ValueError("não é possível calcular média de uma lista vazia")
    _checar_homogeneidade(lista)
    return sum(v.valor_m2 for v in lista) / len(lista)


def mediana_valor_m2(valores: Iterable[ValorMonetario]) -> float:
    """Mesma regra de homogeneidade de media_valor_m2, para mediana."""
    lista = list(valores)
    if not lista:
        raise ValueError("não é possível calcular mediana de uma lista vazia")
    _checar_homogeneidade(lista)
    return median(v.valor_m2 for v in lista)


def _checar_homogeneidade(valores: list[ValorMonetario]) -> None:
    tipos = {v.tipo_valor for v in valores}
    if len(tipos) > 1:
        raise ValueError(
            f"não é possível agregar tipo_valor diferentes na mesma média: "
            f"{sorted(tipos)} - venal, avaliação, anúncio e transação são "
            "grandezas distintas, não intercambiáveis"
        )
    componentes = {v.componente for v in valores}
    if len(componentes) > 1:
        raise ValueError(
            f"não é possível agregar componente diferentes na mesma média: "
            f"{sorted(componentes)} - terreno e construção não são "
            "somáveis/mediáveis juntos sem dupla contagem"
        )
