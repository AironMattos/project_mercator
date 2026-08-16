from __future__ import annotations

import hashlib

# Componentes da impressão digital, na ordem fixa em que entram no hash -
# seção 8 do prompt de referência do Radar de Anúncios: "impressao_digital
# = hash(bairro, area, quartos, vagas, andar, condominio)". area_util_m2 é
# arredondada para o m² inteiro antes do hash - duas fontes raramente
# reportam a mesma metragem com a casa decimal idêntica, e um anúncio da
# mesma unidade em fontes diferentes já diverge nisso na prática (achado
# esperado, não hipotético: ver campo "65m2" vs. "51m2 privativos" no
# mesmo imóvel real inspecionado no checkpoint 12a). Sem esse
# arredondamento, a resolução entre fontes nunca casaria nada.
_PRECISAO_AREA_M2 = 1


def calcular_impressao_digital(
    territorio_id: str,
    area_util_m2: float,
    quartos: int | None,
    vagas: int | None,
    andar: int | None,
    condominio: float | None,
) -> str:
    """Hash determinístico dos atributos físicos de um imóvel - usado tanto
    pra resolução entre fontes (seção 8.1: o mesmo imóvel anunciado em
    Apolar e Chaves na Mão não pode contar duas vezes) quanto pra detecção
    de reanúncio (seção 5: o mesmo imóvel volta à oferta com preço maior).

    `condominio` entra arredondado à centena (R$100) - o valor do
    condomínio costuma ser reportado com pequena variação entre
    publicações da mesma unidade (reajuste no período entre anúncios,
    arredondamento da imobiliária) sem que isso signifique um imóvel
    diferente; arredondar demais (ex.: ao milhar) colidiria unidades
    realmente diferentes do mesmo prédio.

    `None` em quartos/vagas/andar/condomínio entra como o literal "?" no
    hash, nunca é tratado como zero - "não informado" e "informado como
    zero" precisam gerar impressões diferentes (um imóvel com 0 vagas
    reportado não é o mesmo cluster de um sem essa informação)."""
    area_arredondada = round(area_util_m2 / _PRECISAO_AREA_M2) * _PRECISAO_AREA_M2
    condominio_arredondado = None if condominio is None else round(condominio / 100) * 100

    partes = [
        territorio_id,
        str(area_arredondada),
        _componente_opcional(quartos),
        _componente_opcional(vagas),
        _componente_opcional(andar),
        _componente_opcional(condominio_arredondado),
    ]
    chave = "|".join(partes)
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:32]


def _componente_opcional(valor: int | float | None) -> str:
    return "?" if valor is None else str(valor)
