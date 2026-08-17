from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from domain.anuncio import OPERACOES_VALIDAS
from infrastructure.database.repositories.anuncio_interface_repository import (
    consultar_procedencia,
    consultar_resumo_bairro,
    consultar_termometro_por_bairro,
)
from infrastructure.database.repositories.construcao_repository import (
    consultar_metricas_construcao,
)
from infrastructure.database.repositories.valor_referencia_repository import (
    consultar_valor_venal_mediano_por_bairro,
)

from dependencies import get_db
from schemas import ProcedenciaFonteOut, ResumoBairroAnuncioOut, TermometroBairroOut

router = APIRouter(prefix="/anuncios")


def _validar_operacao(operacao: str) -> None:
    if operacao not in OPERACOES_VALIDAS:
        raise HTTPException(
            status_code=422,
            detail=f"operacao inválida: {operacao!r}. Deve ser uma de {sorted(OPERACOES_VALIDAS)}",
        )


@router.get("/termometro", response_model=list[TermometroBairroOut])
def termometro(
    operacao: str, tipologia: str | None = None, session: Session = Depends(get_db)
) -> list[TermometroBairroOut]:
    """Estoque e preço pedido por bairro (checkpoint 12f/12i) - base do
    mapa principal. `quadrante` sempre `None` (ver schema)."""
    _validar_operacao(operacao)
    linhas = consultar_termometro_por_bairro(session, operacao=operacao, tipologia=tipologia)
    return [TermometroBairroOut(**linha) for linha in linhas]


@router.get("/bairros/{territorio_id}/resumo", response_model=ResumoBairroAnuncioOut)
def bairro_resumo(
    territorio_id: str,
    operacao: str,
    tipologia: str | None = None,
    session: Session = Depends(get_db),
) -> ResumoBairroAnuncioOut:
    """Painel de bairro (checkpoint 12i, seção 10) - reaproveita
    `/imoveis/construcao` e `/imoveis/valor-referencia` pro contexto de
    construção/valor venal, filtrado pro mesmo bairro, em vez de
    duplicar essas consultas."""
    resumo = consultar_resumo_bairro(
        session, territorio_id, operacao=operacao, tipologia=tipologia
    )

    construcao = consultar_metricas_construcao(
        session, territorio_id=None, data_inicio=None, data_fim=None
    )
    construcao_bairro = next((c for c in construcao if c["territorio_id"] == territorio_id), None)

    valor_venal = consultar_valor_venal_mediano_por_bairro(session)
    valor_venal_bairro = next(
        (v for v in valor_venal if v["territorio_id"] == territorio_id), None
    )

    return ResumoBairroAnuncioOut(
        territorio_id=territorio_id,
        operacao=operacao,
        tipologia=tipologia,
        estoque=resumo["estoque"],
        preco_mediano=resumo["preco_mediano"],
        preco_p25=resumo["preco_p25"],
        preco_p75=resumo["preco_p75"],
        preco_m2_mediano=resumo["preco_m2_mediano"],
        amostra_preco_suficiente=resumo["amostra_preco_suficiente"],
        construcao_alvaras_aprovados=(
            construcao_bairro["alvaras_aprovados"] if construcao_bairro else None
        ),
        construcao_cvcos_concluidos=(
            construcao_bairro["cvcos_concluidos"] if construcao_bairro else None
        ),
        valor_venal_m2_mediano=(
            valor_venal_bairro["valor_m2_mediano"] if valor_venal_bairro else None
        ),
    )


@router.get("/procedencia", response_model=list[ProcedenciaFonteOut])
def procedencia(session: Session = Depends(get_db)) -> list[ProcedenciaFonteOut]:
    """Painel de procedência ampliado (checkpoint 12i, seção 10) -
    Apolar e Chaves na Mão sempre separados, nunca uma média silenciosa
    (seção 1.2)."""
    linhas = consultar_procedencia(session)
    return [ProcedenciaFonteOut(**linha) for linha in linhas]
