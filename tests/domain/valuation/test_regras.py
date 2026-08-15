import pytest

from domain.valuation import ValorMonetario, media_valor_m2, mediana_valor_m2


def _v(valor_m2, tipo_valor="venal", componente="terreno", fonte_id="ippuc_pgv"):
    return ValorMonetario(
        valor_m2=valor_m2, tipo_valor=tipo_valor, componente=componente, fonte_id=fonte_id
    )


def test_media_valor_m2_de_lista_homogenea():
    valores = [_v(1000.0), _v(2000.0), _v(3000.0)]
    assert media_valor_m2(valores) == 2000.0


def test_mediana_valor_m2_de_lista_homogenea():
    valores = [_v(1000.0), _v(2000.0), _v(9000.0)]
    assert mediana_valor_m2(valores) == 2000.0


def test_media_valor_m2_lista_vazia_rejeitada():
    with pytest.raises(ValueError):
        media_valor_m2([])


def test_mediana_valor_m2_lista_vazia_rejeitada():
    with pytest.raises(ValueError):
        mediana_valor_m2([])


def test_media_valor_m2_mistura_tipo_valor_e_rejeitada():
    valores = [_v(1000.0, tipo_valor="venal"), _v(2000.0, tipo_valor="avaliacao")]
    with pytest.raises(ValueError, match="tipo_valor"):
        media_valor_m2(valores)


def test_media_valor_m2_mistura_componente_e_rejeitada():
    valores = [_v(1000.0, componente="terreno"), _v(2000.0, componente="construcao")]
    with pytest.raises(ValueError, match="componente"):
        media_valor_m2(valores)


def test_mediana_valor_m2_mistura_tipo_valor_e_rejeitada():
    valores = [_v(1000.0, tipo_valor="venal"), _v(2000.0, tipo_valor="transacao")]
    with pytest.raises(ValueError, match="tipo_valor"):
        mediana_valor_m2(valores)


def test_media_valor_m2_mistura_fonte_mas_mesmo_tipo_e_componente_e_permitida():
    # fonte_id diferente não é o mesmo tipo de erro que tipo_valor/componente
    # diferente - duas fontes podem legitimamente reportar o mesmo tipo_valor
    # (ex.: dois bairros vizinhos, cada um com seu polígono da PGV).
    valores = [_v(1000.0, fonte_id="ippuc_pgv"), _v(3000.0, fonte_id="ippuc_pgv_v2")]
    assert media_valor_m2(valores) == 2000.0
