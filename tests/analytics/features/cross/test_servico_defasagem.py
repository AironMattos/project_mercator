import math
from datetime import date

from analytics.features import PontoMensal
from analytics.features.cross.servico_defasagem import (
    analisar_defasagem_cidade,
    analisar_defasagem_por_bairro,
)


def _mes(i: int) -> date:
    total = (2022 * 12 + 0) + i
    return date(total // 12, total % 12 + 1, 1)


def _serie_aperiodica(n: int, semente: float = 0.0) -> list[float]:
    return [math.sin(i + semente) * 10 + i * 0.3 for i in range(n)]


def _par_com_lag(n: int, lag: int, semente: float = 0.0):
    valores = _serie_aperiodica(n, semente)
    a = [PontoMensal(mes=_mes(i), valor=valores[i]) for i in range(n)]
    b = [PontoMensal(mes=_mes(i), valor=valores[i - lag]) for i in range(lag, n)]
    return a, b


def test_analise_cidade_encontra_defasagem_significativa():
    comercio, anuncio = _par_com_lag(48, lag=3)
    analise = analisar_defasagem_cidade(comercio, anuncio, lag_maximo=12)
    assert analise.defasagem_maxima is not None
    assert analise.defasagem_maxima.lag_meses == 3


def test_bairro_nao_roda_quando_cidade_nao_e_significativa():
    curta_comercio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]
    curta_anuncio = [PontoMensal(mes=_mes(i), valor=float(i)) for i in range(5)]
    analise_cidade = analisar_defasagem_cidade(curta_comercio, curta_anuncio, lag_maximo=6)
    assert analise_cidade.defasagem_maxima is None

    resultado_bairro = analisar_defasagem_por_bairro(
        analise_cidade,
        {"bairro-x": curta_comercio},
        {"bairro-x": curta_anuncio},
        lag_maximo=6,
    )
    assert resultado_bairro is None


def test_bairro_roda_quando_cidade_e_significativa_e_usa_correcao_da_cidade_inteira():
    comercio_cidade, anuncio_cidade = _par_com_lag(48, lag=3)
    analise_cidade = analisar_defasagem_cidade(comercio_cidade, anuncio_cidade, lag_maximo=12)
    assert analise_cidade.defasagem_maxima is not None

    comercio_a, anuncio_a = _par_com_lag(48, lag=3, semente=1.0)
    comercio_b, anuncio_b = _par_com_lag(48, lag=3, semente=2.0)

    resultado = analisar_defasagem_por_bairro(
        analise_cidade,
        {"bairro-a": comercio_a, "bairro-b": comercio_b},
        {"bairro-a": anuncio_a, "bairro-b": anuncio_b},
        lag_maximo=12,
    )

    assert resultado is not None
    assert set(resultado) == {"bairro-a", "bairro-b"}
    # correção usa o total de testes (2 bairros x 25 lags), não 25 isolado
    algum_resultado = resultado["bairro-a"].resultados[0]
    assert algum_resultado.n_testes == 2 * 25


def test_bairro_so_inclui_bairros_com_as_duas_series():
    comercio_cidade, anuncio_cidade = _par_com_lag(48, lag=3)
    analise_cidade = analisar_defasagem_cidade(comercio_cidade, anuncio_cidade, lag_maximo=12)

    comercio_a, anuncio_a = _par_com_lag(48, lag=3, semente=1.0)
    resultado = analisar_defasagem_por_bairro(
        analise_cidade,
        {"bairro-a": comercio_a, "bairro-sem-anuncio": comercio_a},
        {"bairro-a": anuncio_a},
        lag_maximo=12,
    )
    assert resultado is not None
    assert set(resultado) == {"bairro-a"}
