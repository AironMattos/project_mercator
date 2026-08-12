from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cnae:
    """Uma subclasse da Classificação Nacional de Atividades Econômicas
    (CNAE 2.3), conforme a tabela oficial do IBGE.
    """

    codigo_cnae: str
    descricao: str
    secao: str
    divisao: str
    grupo: str
    classe: str
    subclasse: str

    def __post_init__(self) -> None:
        if not self.codigo_cnae:
            raise ValueError("codigo_cnae não pode ser vazio")
        if not self.descricao:
            raise ValueError("descricao não pode ser vazia")
