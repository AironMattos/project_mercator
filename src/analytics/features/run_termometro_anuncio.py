"""Materializa analytics.termometro_anuncio (checkpoint 12f - Radar de
Anúncios, termômetro de aquecimento por bairro/tipologia/operação).

**Limitação de dado real, documentada, não escondida**: com o histórico
atual (essencialmente um snapshot por fonte, ver checkpoint 12e), só as
métricas de "estoque atual" são computáveis de verdade - novos_anuncios/
encerrados vêm de eventos reais gravados, mas rotação da oferta,
renovação, permanência mediana, pressão de preço e o quadrante de
aquecimento exigem histórico (estoque de início de mês, ciclos de vida
completos, ou baseline de 3+ meses) que ainda não existe. Essas colunas
ficam `NULL` - nunca um número inventado sobre uma base fraca, mesma
disciplina de `analytics/features/indicadores.py`. Voltam a ficar
preenchidas sozinhas conforme mais snapshots semanais forem processados,
sem mudança de código.

Uso:
    python -m analytics.features.run_termometro_anuncio
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone

from analytics.features.anuncio_termometro import (
    calcular_estatistica_preco,
    calcular_novos_por_mil_domicilios,
    contar_novos_anuncios,
)
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.contexto_censo_repository import (
    consultar_agregado_por_bairro,
)
from infrastructure.database.repositories.termometro_repository import (
    consultar_contagem_eventos_por_celula,
    consultar_estoque_e_precos_ativos,
    substituir_termometro,
)
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TIPOS_EVENTO_CELULA = ("ANUNCIO_PUBLICADO", "REANUNCIO", "ANUNCIO_ENCERRADO")


def _mes_atual() -> date:
    hoje = date.today()
    return date(hoje.year, hoje.month, 1)


def _montar_linhas(
    estoque_rows: list[dict],
    eventos_por_celula: dict[tuple[str | None, str, str, date], list[str]],
    domicilios_por_territorio: dict[str, int],
    mes: date,
) -> list[dict]:
    grupos: dict[tuple[str | None, str, str], dict] = defaultdict(
        lambda: {"n": 0, "precos": [], "precos_m2": []}
    )
    for r in estoque_rows:
        chave = (r["territorio_id"], r["tipologia"], r["operacao"])
        g = grupos[chave]
        g["n"] += 1
        if r["preco"] is not None:
            g["precos"].append(r["preco"])
            if r["area_util_m2"]:
                g["precos_m2"].append(r["preco"] / r["area_util_m2"])

    chaves_evento_no_mes = {
        (territorio_id, tipologia, operacao)
        for (territorio_id, tipologia, operacao, mes_evento) in eventos_por_celula
        if mes_evento == mes
    }
    todas_chaves = set(grupos) | chaves_evento_no_mes

    linhas: list[dict] = []
    for territorio_id, tipologia, operacao in todas_chaves:
        g = grupos.get((territorio_id, tipologia, operacao), {"n": 0, "precos": [], "precos_m2": []})
        tipos_evento_mes = eventos_por_celula.get((territorio_id, tipologia, operacao, mes), [])

        novos = contar_novos_anuncios(tipos_evento_mes)
        encerrados = sum(1 for t in tipos_evento_mes if t == "ANUNCIO_ENCERRADO")
        estoque = g["n"]

        domicilios = domicilios_por_territorio.get(territorio_id) if territorio_id else None
        preco_stats = calcular_estatistica_preco(g["precos"])
        preco_m2_stats = calcular_estatistica_preco(g["precos_m2"])

        linhas.append(
            {
                "territorio_id": territorio_id,
                "tipologia": tipologia,
                "operacao": operacao,
                "mes": mes,
                "novos_anuncios": novos,
                "encerrados": encerrados,
                "estoque": estoque,
                "novos_por_mil_domicilios": calcular_novos_por_mil_domicilios(novos, domicilios),
                # Rotação/renovação/permanência/pressão de preço/quadrante
                # exigem histórico que ainda não existe (ver docstring do
                # módulo) - NULL de propósito, não 0.
                "rotacao_oferta": None,
                "renovacao": None,
                "permanencia_mediana_dias": None,
                "pressao_preco_pct_subiu": None,
                "pressao_preco_pct_desceu": None,
                "pressao_preco_variacao_mediana_pct": None,
                "preco_mediano": preco_stats.mediana,
                "preco_p25": preco_stats.p25,
                "preco_p75": preco_stats.p75,
                "preco_m2_mediano": preco_m2_stats.mediana,
                "preco_m2_p25": preco_m2_stats.p25,
                "preco_m2_p75": preco_m2_stats.p75,
                "amostra_preco_suficiente": preco_stats.motivo_indisponivel is None,
                "quadrante": None,
            }
        )
    return linhas


def main() -> None:
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    total_celulas = 0

    try:
        mes = _mes_atual()
        with get_session() as session:
            estoque_rows = consultar_estoque_e_precos_ativos(session)
            eventos_por_celula = consultar_contagem_eventos_por_celula(
                session, TIPOS_EVENTO_CELULA
            )
            domicilios_por_territorio = {
                r["territorio_id"]: r["domicilios_total"]
                for r in consultar_agregado_por_bairro(session)
            }

        linhas = _montar_linhas(estoque_rows, eventos_por_celula, domicilios_por_territorio, mes)

        with get_session() as session:
            total_celulas = substituir_termometro(session, linhas)

        logger.info("célula(s) gravada(s): %d", total_celulas)
        with_amostra = sum(1 for linha in linhas if linha["amostra_preco_suficiente"])
        logger.info(
            "%d/%d células com amostra de preço suficiente (>= 30 anúncios)",
            with_amostra,
            len(linhas),
        )

        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id="termometro_anuncio",
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=len(estoque_rows),
                    registros_gravados=total_celulas,
                    registros_com_falha=0,
                )
            )
    except Exception:
        status = "falha"
        logger.exception("falha ao materializar termometro_anuncio")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id="termometro_anuncio",
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=0,
                    registros_gravados=total_celulas,
                    registros_com_falha=0,
                )
            )
        raise


if __name__ == "__main__":
    main()
