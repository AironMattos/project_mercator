import math
from datetime import date

import pytest

from analytics.features import PontoMensal
from analytics.features.cross.defasagem import (
    MOTIVO_AMOSTRA_INSUFICIENTE,
    calcular_correlacao_cruzada,
    defasagem_mais_forte,
)


def _mes(i: int) -> date:
    total = (2022 * 12 + 0) + i
    return date(total // 12, total % 12 + 1, 1)


def _serie_aperiodica(n: int) -> list[float]:
    # sin(i) para i inteiro não é periódico dentro de uma janela pequena
    # (2π é irracional) - evita o aliasing que uma senoide "de verdade"
    # causaria ao testar vários lags, e ainda soma uma tendência linear
    # pra parecer menos um padrão de teste artificial.
    return [math.sin(i) * 10 + i * 0.3 for i in range(n)]


def test_correlacao_encontra_o_lag_verdadeiro():
    valores = _serie_aperiodica(48)
    comercio = [PontoMensal(mes=_mes(i), valor=valores[i]) for i in range(48)]
    # anuncio[i] = comercio_valor[i-3] -> comercio antecede anuncio em 3 meses
    anuncio = [PontoMensal(mes=_mes(i), valor=valores[i - 3]) for i in range(3, 48)]

    resultados = calcular_correlacao_cruzada(comercio, anuncio, lag_maximo=12)
    mais_forte = defasagem_mais_forte(resultados)

    assert mais_forte is not None
    assert mais_forte.lag_meses == 3
    assert mais_forte.coeficiente == pytest.approx(1.0, abs=1e-6)
    assert mais_forte.significativo is True


def test_correlacao_intervalo_de_confianca_nunca_contem_zero_quando_significativo():
    valores = _serie_aperiodica(48)
    comercio = [PontoMensal(mes=_mes(i), valor=valores[i]) for i in range(48)]
    anuncio = [PontoMensal(mes=_mes(i), valor=valores[i - 3]) for i in range(3, 48)]

    resultados = calcular_correlacao_cruzada(comercio, anuncio, lag_maximo=12)
    lag3 = next(r for r in resultados if r.lag_meses == 3)
    assert lag3.intervalo_confianca is not None
    baixo, alto = lag3.intervalo_confianca
    assert not (baixo <= 0 <= alto)


def test_correlacao_amostra_insuficiente_fica_indisponivel():
    curta_comercio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]
    curta_anuncio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]

    resultados = calcular_correlacao_cruzada(curta_comercio, curta_anuncio, lag_maximo=12)
    for r in resultados:
        assert r.coeficiente is None
        assert r.significativo is False
        assert r.motivo_indisponivel == MOTIVO_AMOSTRA_INSUFICIENTE


def test_correlacao_serie_constante_fica_indisponivel_nao_zero():
    # variância zero não é "sem correlação" (r=0), é indefinido
    constante = [PontoMensal(mes=_mes(i), valor=50.0) for i in range(30)]
    variavel = [PontoMensal(mes=_mes(i), valor=_serie_aperiodica(30)[i]) for i in range(30)]

    resultados = calcular_correlacao_cruzada(constante, variavel, lag_maximo=6)
    lag0 = next(r for r in resultados if r.lag_meses == 0)
    assert lag0.coeficiente is None
    assert lag0.motivo_indisponivel == MOTIVO_AMOSTRA_INSUFICIENTE


def test_correlacao_ruido_puro_normalmente_nao_significativo_apos_bonferroni():
    # duas séries sem relação real - com correção de Bonferroni sobre 25
    # lags, o IC não deveria "achar" significância por acaso aqui
    valores_a = _serie_aperiodica(48)
    valores_b = [math.cos(i * 1.7) * 5 + (i % 7) for i in range(48)]
    comercio = [PontoMensal(mes=_mes(i), valor=valores_a[i]) for i in range(48)]
    anuncio = [PontoMensal(mes=_mes(i), valor=valores_b[i]) for i in range(48)]

    resultados = calcular_correlacao_cruzada(comercio, anuncio, lag_maximo=12)
    significativos = [r for r in resultados if r.significativo]
    assert significativos == []


def test_correlacao_n_testes_explicito_e_usado_na_correcao():
    valores = _serie_aperiodica(48)
    comercio = [PontoMensal(mes=_mes(i), valor=valores[i]) for i in range(48)]
    anuncio = [PontoMensal(mes=_mes(i), valor=valores[i - 3]) for i in range(3, 48)]

    resultados_padrao = calcular_correlacao_cruzada(comercio, anuncio, lag_maximo=12)
    resultados_corrigido = calcular_correlacao_cruzada(
        comercio, anuncio, lag_maximo=12, n_testes=1900
    )

    lag3_padrao = next(r for r in resultados_padrao if r.lag_meses == 3)
    lag3_corrigido = next(r for r in resultados_corrigido if r.lag_meses == 3)
    assert lag3_padrao.n_testes == 25
    assert lag3_corrigido.n_testes == 1900
    # IC mais amplo (mais testes corrigidos) - a distância até a borda
    # do intervalo cresce com n_testes, mesmo mantendo o mesmo r
    largura_padrao = lag3_padrao.intervalo_confianca[1] - lag3_padrao.intervalo_confianca[0]
    largura_corrigida = lag3_corrigido.intervalo_confianca[1] - lag3_corrigido.intervalo_confianca[0]
    assert largura_corrigida >= largura_padrao


def test_defasagem_mais_forte_none_quando_nada_significativo():
    curta_comercio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]
    curta_anuncio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]
    resultados = calcular_correlacao_cruzada(curta_comercio, curta_anuncio, lag_maximo=6)
    assert defasagem_mais_forte(resultados) is None
