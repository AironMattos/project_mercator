from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

NIVEIS_VALIDOS = frozenset({"bairro", "rua", "grid", "cidade"})


@dataclass(frozen=True)
class Territorio:
    """Uma unidade territorial com identidade, geometria e hierarquia própria.

    Território é uma dimensão de primeira classe - nunca uma string solta.
    """

    territorio_id: str
    nivel: str
    nome: str
    geometria: BaseGeometry | None = None
    nome_alternativo: tuple[str, ...] = field(default_factory=tuple)
    territorio_pai_id: str | None = None
    cidade_id: str = "curitiba"

    def __post_init__(self) -> None:
        if not self.territorio_id:
            raise ValueError("territorio_id não pode ser vazio")
        if self.nivel not in NIVEIS_VALIDOS:
            raise ValueError(
                f"nivel inválido: {self.nivel!r}. Deve ser um de {sorted(NIVEIS_VALIDOS)}"
            )
        if not self.nome:
            raise ValueError("nome não pode ser vazio")
        if self.geometria is not None and self.geometria.is_empty:
            raise ValueError(f"geometria vazia para território {self.territorio_id!r}")
