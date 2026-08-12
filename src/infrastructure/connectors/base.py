from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass
class RawSnapshot:
    """Dado bruto capturado de uma fonte, antes de qualquer transformação."""

    fonte_id: str
    capturado_em: datetime
    snapshot_ref: str
    conteudo: Any


class Connector(Protocol):
    """Contrato que toda fonte de dado deve implementar.

    A detecção de evento NÃO acontece aqui - isso é responsabilidade central
    da plataforma (src/domain/event/), não de um conector individual.
    """

    fonte_id: str
    cadencia: str

    def fetch(self) -> RawSnapshot:
        """Busca o dado bruto e grava, sem transformar, na Raw Zone."""
        ...

    def normalize(self, snapshot: RawSnapshot) -> list[Any]:
        """Transforma o bruto em registros no schema canônico."""
        ...
