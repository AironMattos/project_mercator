from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entidade:
    """Quem: uma unidade identificável pela fonte que a reportou (ex.: um
    alvará comercial). entidade_id é um candidato gerado localmente; se a
    entidade já existir no banco (mesmo tipo_entidade + identificador_fonte),
    o id efetivamente usado é o já existente, não este.
    """

    tipo_entidade: str
    identificador_fonte: str
    entidade_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.tipo_entidade:
            raise ValueError("tipo_entidade não pode ser vazio")
        if not self.identificador_fonte:
            raise ValueError("identificador_fonte não pode ser vazio")
