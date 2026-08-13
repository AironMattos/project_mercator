from __future__ import annotations

import math
from dataclasses import dataclass

import requests
from shapely.geometry import Point

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ProjectMercator-Geocoding/1.0 (contato: airon.mattos@outlook.com)"

# Distância entre o 1º e o 2º candidato abaixo da qual tratamos como "o
# mesmo lugar, mapeado por dois elementos OSM diferentes" (sucesso, usa o
# de maior importância) em vez de ambiguidade geográfica real - mesmo
# critério validado no Piloto 1.
LIMIAR_MESMO_LOCAL_METROS = 50.0

# 1 req/s - termos de uso do Nominatim público. Quem chama em lote (pipeline
# de resíduo) precisa dormir isso entre chamadas; uma busca interativa de
# usuário (uma chamada ocasional) não precisa.
INTERVALO_MINIMO_ENTRE_CHAMADAS_S = 1.0


@dataclass(frozen=True)
class ResultadoNominatim:
    status: str  # 'sucesso' | 'falha' | 'ambiguo'
    ponto: Point | None
    confianca_bruta: str | None = None


def montar_endereco(logradouro: str | None, numero: str | None, bairro: str | None, cep: str | None) -> str:
    partes = [
        (logradouro or "").strip(),
        _limpar_numero(numero),
        (bairro or "").strip(),
        _limpar_cep(cep),
        "Curitiba, PR, Brasil",
    ]
    return ", ".join(p for p in partes if p)


def _limpar_numero(numero: str | None) -> str:
    if not numero:
        return ""
    numero = numero.strip()
    return str(int(numero)) if numero.isdigit() else numero


def _limpar_cep(cep: str | None) -> str:
    if not cep:
        return ""
    cep = cep.strip()
    if len(cep) == 8 and cep.isdigit():
        return f"{cep[:5]}-{cep[5:]}"
    return cep


def _distancia_aproximada_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = (lat2 - lat1) * 111_320
    dlon = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


def geocodificar(endereco: str, session: requests.Session, *, timeout: float = 15.0) -> ResultadoNominatim:
    """Uma chamada síncrona ao Nominatim público. Quem chama em lote é
    responsável por respeitar o intervalo de 1 req/s entre chamadas
    (INTERVALO_MINIMO_ENTRE_CHAMADAS_S) - esta função não dorme sozinha,
    porque uma busca interativa de usuário não deve pagar esse custo.
    """
    params = {
        "q": endereco,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "br",
        "addressdetails": 1,
    }
    resp = session.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    resultados = resp.json()

    if not resultados:
        return ResultadoNominatim(status="falha", ponto=None)

    primeiro = resultados[0]
    lat1, lon1 = float(primeiro["lat"]), float(primeiro["lon"])
    importancia1 = primeiro.get("importance")

    if len(resultados) == 1:
        confianca = f"importance={importancia1};type={primeiro.get('type')};n_candidatos=1"
        return ResultadoNominatim(status="sucesso", ponto=Point(lon1, lat1), confianca_bruta=confianca)

    segundo = resultados[1]
    lat2, lon2 = float(segundo["lat"]), float(segundo["lon"])
    dist = _distancia_aproximada_metros(lat1, lon1, lat2, lon2)

    if dist <= LIMIAR_MESMO_LOCAL_METROS:
        confianca = (
            f"importance={importancia1};type={primeiro.get('type')};"
            f"n_candidatos={len(resultados)};dist_2o_candidato_m={dist:.1f}"
        )
        return ResultadoNominatim(status="sucesso", ponto=Point(lon1, lat1), confianca_bruta=confianca)

    confianca = f"n_candidatos={len(resultados)};dist_2o_candidato_m={dist:.1f}"
    return ResultadoNominatim(status="ambiguo", ponto=None, confianca_bruta=confianca)
