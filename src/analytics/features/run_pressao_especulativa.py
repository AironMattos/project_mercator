"""Relatório de pressão especulativa (checkpoint 12h, seção 5 do prompt
de referência) - mesmo espírito de `cross/run_leitura_cruzada.py`: não
grava nada (sem endpoint/tela ainda, checkpoint 12i), só imprime os 5
indicadores pra conferência antes de qualquer coisa ir pra interface.

Uso:
    python -m analytics.features.run_pressao_especulativa
"""
from __future__ import annotations

import logging

from analytics.features.anuncio_termometro import calcular_estatistica_preco
from analytics.features.pressao_especulativa import (
    avaliar_preco_sem_contrapartida_fisica,
    calcular_concentracao_ofertante,
    calcular_descolamento_pedido_contratado,
    calcular_oferta_por_domicilio_vago,
    calcular_taxa_reanuncio,
)
from infrastructure.database.repositories.contexto_censo_repository import (
    consultar_agregado_por_bairro,
)
from infrastructure.database.repositories.contexto_quintoandar_repository import (
    consultar_ultimo_periodo,
)
from infrastructure.database.repositories.pressao_especulativa_repository import (
    consultar_contagem_por_ofertante,
    consultar_estoque_total_por_bairro,
    consultar_preco_pedido_m2_mediano_cidade,
    contar_reanuncios_e_encerrados,
    houve_contrapartida_fisica_no_bairro,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _indicador_1_reanuncio() -> None:
    with get_session() as session:
        n_reanuncios, n_encerrados, variacoes = contar_reanuncios_e_encerrados(session)
    resultado = calcular_taxa_reanuncio(n_reanuncios, n_encerrados, variacoes)
    logger.info(
        "1. Reanúncio com preço maior: taxa=%s (%d reanúncios / %d encerrados), "
        "mediana do incremento=%s, motivo_indisponivel=%s",
        resultado.taxa,
        n_reanuncios,
        n_encerrados,
        resultado.mediana_incremento_pct,
        resultado.motivo_indisponivel,
    )


def _indicador_2_preco_sem_contrapartida() -> None:
    # variacao_preco_pct precisa de baseline (checkpoint 12f/12g -
    # histórico ainda insuficiente) - fica None de propósito; o que dá
    # pra demonstrar hoje é o lado real (houve_contrapartida) pros
    # bairros com mais atividade de obra conhecida.
    bairros_teste = ["curitiba-bairro-centro", "curitiba-bairro-batel"]
    with get_session() as session:
        for territorio_id in bairros_teste:
            contrapartida = houve_contrapartida_fisica_no_bairro(session, territorio_id, meses=12)
            resultado = avaliar_preco_sem_contrapartida_fisica(None, contrapartida)
            logger.info(
                "2. Preço sem contrapartida física (%s): houve_contrapartida=%s, "
                "motivo_indisponivel=%s (variação de preço aguarda baseline, "
                "checkpoint 12f/12g)",
                territorio_id,
                contrapartida,
                resultado.motivo_indisponivel,
            )


def _indicador_3_oferta_por_domicilio_vago() -> None:
    with get_session() as session:
        estoque_por_bairro = consultar_estoque_total_por_bairro(session)
        censo = {r["territorio_id"]: r["domicilios_particulares_vagos"] for r in consultar_agregado_por_bairro(session)}

    resultados = []
    for territorio_id, estoque in estoque_por_bairro.items():
        vagos = censo.get(territorio_id)
        resultado = calcular_oferta_por_domicilio_vago(estoque, vagos)
        if resultado.razao is not None:
            resultados.append((territorio_id, resultado))

    resultados.sort(key=lambda item: item[1].razao, reverse=True)
    logger.info("3. Oferta por domicílio vago - top 5 bairros:")
    for territorio_id, resultado in resultados[:5]:
        logger.info(
            "   %s: %.3f (estoque=%d, domicílios vagos=%d)",
            territorio_id,
            resultado.razao,
            resultado.estoque_anuncios,
            resultado.domicilios_vagos,
        )


def _indicador_4_concentracao_ofertante() -> None:
    with get_session() as session:
        contagens = consultar_contagem_por_ofertante(session)
    resultado = calcular_concentracao_ofertante(contagens)
    logger.info(
        "4. Concentração de anunciante: pct_top5=%s, n_ofertantes_distintos=%d, "
        "n_anuncios_com_ofertante_conhecido=%d, motivo_indisponivel=%s",
        resultado.pct_top5_ofertantes,
        resultado.n_ofertantes_distintos,
        resultado.n_anuncios_com_ofertante_conhecido,
        resultado.motivo_indisponivel,
    )


def _indicador_5_descolamento() -> None:
    with get_session() as session:
        precos_m2 = consultar_preco_pedido_m2_mediano_cidade(session, operacao="aluguel")
        periodo_qa, itens_qa = consultar_ultimo_periodo(session, cidade="Curitiba")

    stats = calcular_estatistica_preco(precos_m2)
    indice_qa = next(
        (item["aluguel_m2"] for item in itens_qa if item["segmento"] == "cidade_toda"), None
    )
    resultado = calcular_descolamento_pedido_contratado(stats.mediana, indice_qa)
    logger.info(
        "5. Descolamento pedido/contratado: razão=%s (pedido R$/m²=%s, n=%d; "
        "QuintoAndar R$/m² em %s=%s), motivo_indisponivel=%s",
        resultado.razao,
        stats.mediana,
        stats.n,
        periodo_qa,
        indice_qa,
        resultado.motivo_indisponivel,
    )


def main() -> None:
    logger.info("=== Pressão especulativa (checkpoint 12h) ===")
    _indicador_1_reanuncio()
    _indicador_2_preco_sem_contrapartida()
    _indicador_3_oferta_por_domicilio_vago()
    _indicador_4_concentracao_ofertante()
    _indicador_5_descolamento()


if __name__ == "__main__":
    main()
