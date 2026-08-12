from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from analytics.features.models import ContagemEventos
from domain.event import Evento

TIPOS_CONSIDERADOS = frozenset(
    {"PRIMEIRA_OBSERVACAO", "ABERTURA_CONFIRMADA", "DESAPARECIMENTO"}
)


def calcular_contagem_por_bairro_categoria_mes(
    eventos: Iterable[Evento],
) -> list[ContagemEventos]:
    """Conta PRIMEIRA_OBSERVACAO, ABERTURA_CONFIRMADA e DESAPARECIMENTO por
    bairro, categoria e mês. Regra pura - recebe os eventos já carregados,
    não sabe nada de banco.

    Até a auditoria de 2026-08-12, essa contagem só incluía
    PRIMEIRA_OBSERVACAO e DESAPARECIMENTO - isso fazia o campo "aberturas"
    exposto pela API (feature_repository.consultar_metricas_comercio) somar
    só entidades de confiança BAIXA ("nunca vista antes, sem prova de
    quando abriu"), excluindo justamente ABERTURA_CONFIRMADA (confiança
    ALTA, abertura genuína confirmada por INICIO_ATIVIDADE). Corrigido
    incluindo ABERTURA_CONFIRMADA aqui.

    A métrica mais simples possível: nada de quociente locacional, nada de
    Signal Engine - só contagem, um evento por linha.
    """
    contadores: dict[tuple[str | None, str | None, date, str], int] = {}

    for evento in eventos:
        if evento.event_type not in TIPOS_CONSIDERADOS:
            continue
        mes = date(evento.data_evento.year, evento.data_evento.month, 1)
        categoria_id = evento.payload.get("categoria_id")
        chave = (evento.territorio_id, categoria_id, mes, evento.event_type)
        contadores[chave] = contadores.get(chave, 0) + 1

    return [
        ContagemEventos(
            territorio_id=territorio_id,
            categoria_id=categoria_id,
            mes=mes,
            event_type=event_type,
            contagem=contagem,
        )
        for (territorio_id, categoria_id, mes, event_type), contagem in contadores.items()
    ]
