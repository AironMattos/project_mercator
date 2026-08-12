from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TIPOS_EVENTO_VALIDOS = frozenset(
    {
        "PRIMEIRA_OBSERVACAO",
        "ABERTURA_CONFIRMADA",
        "DESAPARECIMENTO",
        # reservado: depende de uma segunda fonte que ainda não existe no
        # projeto - nenhuma regra emite este tipo ainda.
        "FECHAMENTO_CONFIRMADO",
        "MUDANCA_CATEGORIA",
    }
)
CONFIANCAS_VALIDAS = frozenset({"alta", "media", "baixa"})


@dataclass(frozen=True)
class Evento:
    """O que foi inferido comparando duas observações. Sempre aponta de
    volta para as observações que o sustentam (origem_observacoes) - um
    evento nunca é gerado "do nada".
    """

    entity_type: str
    event_type: str
    entidade_id: uuid.UUID
    data_evento: date
    confianca: str
    origem_observacoes: tuple[uuid.UUID, ...]
    territorio_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    evento_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.entity_type:
            raise ValueError("entity_type não pode ser vazio")
        if self.event_type not in TIPOS_EVENTO_VALIDOS:
            raise ValueError(
                f"event_type inválido: {self.event_type!r}. "
                f"Deve ser um de {sorted(TIPOS_EVENTO_VALIDOS)}"
            )
        if self.confianca not in CONFIANCAS_VALIDAS:
            raise ValueError(
                f"confianca inválida: {self.confianca!r}. "
                f"Deve ser uma de {sorted(CONFIANCAS_VALIDAS)}"
            )
        if not self.origem_observacoes:
            raise ValueError(
                "origem_observacoes não pode ser vazio - todo evento aponta "
                "para as observações que o sustentam"
            )
