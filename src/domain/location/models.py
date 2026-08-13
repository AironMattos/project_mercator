from __future__ import annotations

import uuid
from dataclasses import dataclass

from shapely.geometry import Point

CONFIANCAS_VALIDAS = frozenset({"alta", "media", "baixa"})

# Único nível de precisão do geocodebr que dispensa a segunda passagem -
# "numero" é casamento no nível de número exato do CNEFE. Todo o resto
# (numero_aproximado, logradouro, cep, localidade, municipio - ver Piloto 2)
# é tratado como não-exato e vai pra fila do Nominatim, mesmo
# numero_aproximado sendo "quase lá": o Piloto 2 mostrou que boa parte dos
# 137 pontos fora do polígono esperado vinha justamente de correspondências
# aproximadas, não só de logradouro/cep/localidade.
PRECISOES_QUE_DISPENSAM_SEGUNDA_PASSAGEM = frozenset({"numero"})

# Limiares de desempate por distância entre os dois pontos, calibrados pelo
# padrão observado no Piloto 2 (mediana de 13m quando os dois concordam;
# nos 66 casos de forte divergência - >500m - o Nominatim bateu o
# geocodebr por 38 a 3 em qual caía dentro do bairro esperado).
LIMIAR_CONCORDANCIA_M = 150.0
LIMIAR_DISCORDANCIA_GRAVE_M = 1000.0


@dataclass(frozen=True)
class DecisaoInicial:
    """Resultado da Etapa 1 (geocodebr), antes de qualquer segunda
    passagem."""

    confianca: str
    precisa_segunda_passagem: bool

    def __post_init__(self) -> None:
        if self.confianca not in CONFIANCAS_VALIDAS:
            raise ValueError(f"confianca inválida: {self.confianca!r}")


@dataclass(frozen=True)
class DecisaoFinal:
    """Resultado depois da reconciliação (Etapa 2, quando aplicável) -
    o que efetivamente vira uma linha de
    canonical.geolocalizacao_entidade."""

    ponto: Point | None
    confianca: str
    distancia_desempate_m: float | None

    def __post_init__(self) -> None:
        if self.confianca not in CONFIANCAS_VALIDAS:
            raise ValueError(f"confianca inválida: {self.confianca!r}")


@dataclass(frozen=True)
class ResultadoGeolocalizacao:
    """O que persiste em canonical.geolocalizacao_entidade para uma
    entidade - junta a decisão final com a proveniência (quais fontes
    contribuíram)."""

    entidade_id: uuid.UUID
    ponto: Point | None
    confianca: str
    fonte_primaria: str
    fonte_secundaria: str | None
    precisao_geocodebr: str | None
    distancia_desempate_m: float | None

    def __post_init__(self) -> None:
        if self.confianca not in CONFIANCAS_VALIDAS:
            raise ValueError(f"confianca inválida: {self.confianca!r}")
        if not self.fonte_primaria:
            raise ValueError("fonte_primaria não pode ser vazia")
