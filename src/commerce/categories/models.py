from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    """Uma categoria legível de comércio, usada pelo Radar de Comércio.

    É uma classificação própria do projeto - mais grosseira e voltada a
    leitura humana - não uma tradução 1:1 da CNAE oficial.
    """

    categoria_id: str
    nome: str

    def __post_init__(self) -> None:
        if not self.categoria_id:
            raise ValueError("categoria_id não pode ser vazio")
        if not self.nome:
            raise ValueError("nome não pode ser vazio")
