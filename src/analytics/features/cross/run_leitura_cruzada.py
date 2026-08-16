"""Relatório da leitura cruzada comércio × anúncio (checkpoint 12g,
seção 3 do prompt de referência) - "reporte os coeficientes e intervalos
de confiança antes de expor qualquer coisa na interface" (seção 12).
Não grava nada no banco (ainda não há endpoint/tela pra isso, checkpoint
12i) - só imprime o relatório, mesmo espírito de conferência visual de
run_contagem_eventos.py.

Uso:
    python -m analytics.features.cross.run_leitura_cruzada
"""
from __future__ import annotations

import logging
from datetime import date

from analytics.features.cross.servico_defasagem import (
    analisar_defasagem_cidade,
    analisar_defasagem_por_bairro,
)
from infrastructure.database.repositories.cross_repository import (
    consultar_coincidencia_espacial,
    serie_novos_anuncios_cidade,
    series_novos_anuncios_todos_bairros,
)
from infrastructure.database.repositories.indicador_repository import (
    MESES_HISTORICO_PADRAO,
    series_aberturas_todos_bairros,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _mes_atual() -> date:
    hoje = date.today()
    return date(hoje.year, hoje.month, 1)


def _relatorio_defasagem() -> None:
    mes = _mes_atual()
    with get_session() as session:
        series_comercio_bairro = series_aberturas_todos_bairros(
            session, categoria_id=None, mes_referencia=mes, meses_historico=MESES_HISTORICO_PADRAO
        )
        series_anuncio_bairro = series_novos_anuncios_todos_bairros(
            session, mes_referencia=mes, meses_historico=MESES_HISTORICO_PADRAO
        )
        serie_anuncio_cidade = serie_novos_anuncios_cidade(
            session, mes_referencia=mes, meses_historico=MESES_HISTORICO_PADRAO
        )

    serie_comercio_cidade = []
    if series_comercio_bairro:
        n_meses = len(next(iter(series_comercio_bairro.values())))
        for i in range(n_meses):
            mes_i = next(iter(series_comercio_bairro.values()))[i].mes
            total = sum(serie[i].valor for serie in series_comercio_bairro.values())
            from analytics.features import PontoMensal

            serie_comercio_cidade.append(PontoMensal(mes=mes_i, valor=total))

    analise_cidade = analisar_defasagem_cidade(serie_comercio_cidade, serie_anuncio_cidade)

    logger.info("=== 3.1 Defasagem cruzada - agregado da cidade ===")
    meses_com_dado_comercio = sum(1 for p in serie_comercio_cidade if p.valor > 0)
    meses_com_dado_anuncio = sum(1 for p in serie_anuncio_cidade if p.valor > 0)
    logger.info(
        "meses com aberturas de comércio > 0: %d | meses com novos anúncios > 0: %d",
        meses_com_dado_comercio,
        meses_com_dado_anuncio,
    )
    if analise_cidade.defasagem_maxima is None:
        logger.info(
            "resultado: NENHUMA defasagem significativa no agregado da cidade - "
            "trava 1 da seção 3.1 impede reportar qualquer relação por bairro. "
            "Resultado válido (não é falha): a série de anúncios ainda tem profundidade "
            "de ~1 mês real, muito abaixo do piso mínimo de %d meses sobrepostos "
            "necessário pra testar defasagem até 12 meses." % 12
        )
    else:
        r = analise_cidade.defasagem_maxima
        logger.info(
            "resultado: defasagem máxima em lag=%d meses, r=%.3f, IC95=%s, n=%d",
            r.lag_meses,
            r.coeficiente,
            r.intervalo_confianca,
            r.n_pontos,
        )
        resultado_bairro = analisar_defasagem_por_bairro(
            analise_cidade, series_comercio_bairro, series_anuncio_bairro
        )
        logger.info("bairros com defasagem calculada: %d", len(resultado_bairro or {}))


def _relatorio_coincidencia_espacial() -> None:
    logger.info("=== 3.3 Coincidência espacial fina ===")
    # mesmo ponto real já usado nos testes de busca por raio do Radar de
    # Comércio (checkpoint 9d) - reaproveitado aqui só pra ter um ponto
    # geolocalizado de verdade, não um endereço novo.
    lat, lon = -25.434271, -49.263226
    with get_session() as session:
        resultado = consultar_coincidencia_espacial(session, lat=lat, lon=lon, raio_m=1000, meses=12)
    logger.info(
        "raio 1km em (%.6f, %.6f): %d aberturas / %d desaparecimentos de comércio "
        "(ponto-a-ponto, últimos %d meses); bairro do ponto: %s, %d novos anúncios "
        "nesse bairro (granularidade diferente - anúncio ainda não tem geocodificação)",
        lat,
        lon,
        resultado.aberturas_no_raio,
        resultado.desaparecimentos_no_raio,
        resultado.meses_considerados,
        resultado.territorio_id_do_ponto,
        resultado.novos_anuncios_no_bairro,
    )


def main() -> None:
    _relatorio_defasagem()
    _relatorio_coincidencia_espacial()


if __name__ == "__main__":
    main()
