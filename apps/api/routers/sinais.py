from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    MESES_SINAL_SALDO_NEGATIVO,
    montar_sinais_saldo_negativo,
)
from infrastructure.database.repositories.territorio_repository import (
    nomes_por_territorio_id,
)

from dependencies import get_db
from schemas import SinalOut, SinaisOut

router = APIRouter()

CRITERIO_SALDO_NEGATIVO = (
    f"Saldo líquido (aberturas - fechamentos) negativo nos {MESES_SINAL_SALDO_NEGATIVO} "
    "meses fechados mais recentes."
)


@router.get("/sinais", response_model=SinaisOut)
def sinais(session: Session = Depends(get_db)) -> SinaisOut:
    """Destaques interpretativos com critério explícito e fixo (seção
    "SINAIS E DESTAQUES" do prompt de referência da fase de inteligência
    territorial) - nunca um score oculto decidindo o que aparece. Hoje a
    base só tem 1-2 meses reais de fato_evento_territorial (ver
    "Notas operacionais" no CLAUDE.md), então o critério de 4 meses
    consecutivos normalmente não encontra nenhum bairro elegível ainda -
    `motivo_indisponivel` comunica isso, em vez de uma lista vazia sem
    explicação.
    """
    sinalizados, mes_referencia = montar_sinais_saldo_negativo(session)
    nomes = nomes_por_territorio_id(session)

    motivo_indisponivel = None
    if mes_referencia is None:
        motivo_indisponivel = "historico_insuficiente"

    return SinaisOut(
        itens=[
            SinalOut(
                territorio_id=territorio_id,
                nome=nomes.get(territorio_id, territorio_id),
                descricao=(
                    f"{nomes.get(territorio_id, territorio_id)} apresentou saldo líquido "
                    f"negativo nos últimos {MESES_SINAL_SALDO_NEGATIVO} meses."
                ),
                meses_consecutivos=MESES_SINAL_SALDO_NEGATIVO,
            )
            for territorio_id in sinalizados
        ],
        criterio=CRITERIO_SALDO_NEGATIVO,
        periodo_referencia=mes_referencia,
        motivo_indisponivel=motivo_indisponivel,
    )
