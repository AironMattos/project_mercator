from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ObservacaoEntidade:
    """O que sabíamos, e quando. Imutável: uma observação nunca é alterada
    ou apagada depois de gravada - é um retrato fiel do que a fonte
    informava naquele snapshot.
    """

    entidade_id: uuid.UUID
    observado_em: date
    atributos: dict[str, Any]
    fonte_id: str
    snapshot_ref: str
    observacao_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.atributos:
            raise ValueError("atributos não pode ser vazio")
        if not self.fonte_id:
            raise ValueError("fonte_id não pode ser vazio")
        if not self.snapshot_ref:
            raise ValueError("snapshot_ref não pode ser vazio")
