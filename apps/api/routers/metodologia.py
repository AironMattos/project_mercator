from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from infrastructure.database.repositories.feature_repository import (
    consultar_cobertura_temporal,
)
from infrastructure.database.repositories.geolocalizacao_repository import (
    contar_entidades_comercio,
    contar_por_confianca,
)
from infrastructure.database.repositories.pipeline_run_repository import (
    ultima_execucao_com_sucesso,
)

from dependencies import get_db
from schemas import CoberturaTemporalOut, QualidadeDadosOut

router = APIRouter()


@router.get("/qualidade-dados", response_model=QualidadeDadosOut)
def qualidade_dados(session: Session = Depends(get_db)) -> QualidadeDadosOut:
    """Indicadores objetivos de qualidade da base - nunca um "índice de
    confiança" composto (restrição central da seção "QUALIDADE DOS DADOS"
    do prompt de referência): cada número aqui é uma contagem direta,
    reproduzível, sem ponderação nem normalização escondida.
    """
    total = contar_entidades_comercio(session)
    por_confianca = contar_por_confianca(session)
    alta = por_confianca.get("alta", 0)
    media = por_confianca.get("media", 0)
    baixa = por_confianca.get("baixa", 0)
    nao_geocodificados = max(0, total - (alta + media + baixa))

    pct_localizacao_valida = ((alta + media) / total * 100) if total > 0 else 0.0

    mes_inicio, mes_fim = consultar_cobertura_temporal(session)

    return QualidadeDadosOut(
        total_estabelecimentos=total,
        geocodificados_alta=alta,
        geocodificados_media=media,
        geocodificados_baixa=baixa,
        nao_geocodificados=nao_geocodificados,
        pct_localizacao_valida=pct_localizacao_valida,
        cobertura_temporal=CoberturaTemporalOut(mes_inicio=mes_inicio, mes_fim=mes_fim),
        ultima_atualizacao=ultima_execucao_com_sucesso(session),
    )
