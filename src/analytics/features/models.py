from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ContagemEventos:
    """Contagem de eventos por bairro, categoria, mês e tipo de evento.

    A primeira (e por enquanto única) feature do Radar de Comércio -
    totalmente derivada de events.fato_evento_territorial, recomputável a
    qualquer momento (não é um dado de origem, não precisa de imutabilidade
    como entidade/observação/evento).
    """

    territorio_id: str | None
    categoria_id: str | None
    mes: date
    event_type: str
    contagem: int
