"""Consultas que alimentam a interface do Radar de Anúncios (checkpoint
12i, seção 10 do prompt de referência). Lêem ao vivo de
`consultar_estoque_e_precos_ativos` (mesma base de "estoque atual" do
termômetro, checkpoint 12f) em vez da tabela materializada
`analytics.termometro_anuncio` quando o filtro é "todos os tipos" -
mediana não soma entre tipologias, então agregar por bairro sem quebra
de tipologia precisa recalcular a partir do preço bruto, não somar
medianas já calculadas por célula."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.features.anuncio_termometro import calcular_estatistica_preco
from infrastructure.database.orm.observacao_anuncio import (
    ObservacaoAnuncio as ObservacaoAnuncioORM,
)
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.termometro_repository import (
    consultar_estoque_e_precos_ativos,
)

FONTES_ANUNCIO = ("apolar_anuncios", "chavesnamao_anuncios")


def _agrupar_por_bairro(
    linhas: list[dict], *, operacao: str, tipologia: str | None
) -> dict[str | None, dict]:
    filtradas = [
        linha
        for linha in linhas
        if linha["operacao"] == operacao and (tipologia is None or linha["tipologia"] == tipologia)
    ]
    grupos: dict[str | None, dict] = defaultdict(lambda: {"n": 0, "precos": [], "precos_m2": []})
    for linha in filtradas:
        g = grupos[linha["territorio_id"]]
        g["n"] += 1
        if linha["preco"] is not None:
            g["precos"].append(linha["preco"])
            if linha["area_util_m2"]:
                g["precos_m2"].append(linha["preco"] / linha["area_util_m2"])
    return grupos


def consultar_termometro_por_bairro(
    session: Session, *, operacao: str, tipologia: str | None = None
) -> list[dict]:
    """Uma linha por bairro (estoque, preço mediano/P25/P75, preço/m²
    mediano) - a base do mapa e da lista principal (seção 10). Quadrante
    de aquecimento fica sempre `None` aqui (precisa de baseline
    histórica que ainda não existe, ver checkpoint 12f/12g) - o motivo é
    exposto pra API/UI nunca ficar em silêncio sobre por quê."""
    linhas = consultar_estoque_e_precos_ativos(session)
    grupos = _agrupar_por_bairro(linhas, operacao=operacao, tipologia=tipologia)

    resultado = []
    for territorio_id, g in grupos.items():
        if territorio_id is None:
            continue
        preco_stats = calcular_estatistica_preco(g["precos"])
        preco_m2_stats = calcular_estatistica_preco(g["precos_m2"])
        resultado.append(
            {
                "territorio_id": territorio_id,
                "estoque": g["n"],
                "preco_mediano": preco_stats.mediana,
                "preco_p25": preco_stats.p25,
                "preco_p75": preco_stats.p75,
                "preco_m2_mediano": preco_m2_stats.mediana,
                "amostra_preco_suficiente": preco_stats.motivo_indisponivel is None,
            }
        )
    return resultado


def consultar_resumo_bairro(
    session: Session, territorio_id: str, *, operacao: str, tipologia: str | None = None
) -> dict:
    """Mesmos campos de `consultar_termometro_por_bairro`, um bairro só -
    reaproveita a mesma agregação (sem duplicar a query)."""
    linhas = consultar_estoque_e_precos_ativos(session)
    grupos = _agrupar_por_bairro(linhas, operacao=operacao, tipologia=tipologia)
    g = grupos.get(territorio_id, {"n": 0, "precos": [], "precos_m2": []})

    preco_stats = calcular_estatistica_preco(g["precos"])
    preco_m2_stats = calcular_estatistica_preco(g["precos_m2"])
    return {
        "territorio_id": territorio_id,
        "estoque": g["n"],
        "preco_mediano": preco_stats.mediana,
        "preco_p25": preco_stats.p25,
        "preco_p75": preco_stats.p75,
        "preco_m2_mediano": preco_m2_stats.mediana,
        "amostra_preco_suficiente": preco_stats.motivo_indisponivel is None,
    }


def consultar_procedencia(session: Session, *, dias_periodo: int = 30) -> list[dict]:
    """Painel de procedência ampliado (seção 10): por fonte, data do
    último snapshot, cadência, quantos anúncios foram observados no
    período, taxa de classificação de tipologia (fração que não caiu em
    `nao_classificado`) e taxa de resolução de bairro."""
    obs = ObservacaoAnuncioORM
    corte = date.today() - timedelta(days=dias_periodo)

    resultado = []
    for fonte_id in FONTES_ANUNCIO:
        total = session.execute(
            select(func.count()).where(
                obs.fonte_id == fonte_id, obs.observado_em >= corte
            )
        ).scalar() or 0
        classificados = session.execute(
            select(func.count()).where(
                obs.fonte_id == fonte_id,
                obs.observado_em >= corte,
                obs.tipologia != "nao_classificado",
            )
        ).scalar() or 0
        resolvidos = session.execute(
            select(func.count()).where(
                obs.fonte_id == fonte_id,
                obs.observado_em >= corte,
                obs.territorio_id.isnot(None),
            )
        ).scalar() or 0
        ultima_execucao = session.execute(
            select(func.max(PipelineRun.finalizado_em)).where(
                PipelineRun.conector_id == fonte_id, PipelineRun.status == "sucesso"
            )
        ).scalar()

        resultado.append(
            {
                "fonte_id": fonte_id,
                "cadencia": "semanal",
                "ultima_atualizacao": ultima_execucao,
                "total_observado_no_periodo": total,
                "taxa_classificacao_tipologia": (classificados / total) if total else None,
                "taxa_resolucao_bairro": (resolvidos / total) if total else None,
            }
        )
    return resultado
