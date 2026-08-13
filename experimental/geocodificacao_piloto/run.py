"""Piloto de geocodificação — mede taxa de acerto e viabilidade de tempo/
custo do Nominatim antes de comprometer a base inteira de alvarás ou o
modelo canônico a essa incerteza. Escreve só em experimental.*, nunca em
canonical.* - roda fora de src/ de propósito, sem importar nada do
pacote `mercator` (não é código de produção, é uma medição descartável).

Uso:
    python experimental/geocodificacao_piloto/run.py <territorio_id>

Respeita o limite de 1 req/s do Nominatim (dorme 1s depois de cada
chamada, nunca paralelo) e identifica o cliente via User-Agent, conforme
a política de uso do serviço.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ProjectMercator-GeocodingPilot/1.0 (contato: airon.mattos@outlook.com)"
SERVICO = "nominatim"
FONTE_ID = "alvaras_smf"

# Distância entre o 1º e o 2º candidato abaixo da qual tratamos como "o
# mesmo lugar, mapeado por dois elementos OSM diferentes" (sucesso, usa o
# de maior importância) em vez de ambiguidade geográfica real (dois
# lugares genuinamente diferentes competindo).
LIMIAR_MESMO_LOCAL_METROS = 50.0


def _database_url_psycopg2() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+psycopg2://", "postgresql://")


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


def montar_endereco(endereco: str | None, numero: str | None, bairro: str | None, cep: str | None) -> str:
    partes = [
        (endereco or "").strip(),
        _limpar_numero(numero),
        (bairro or "").strip(),
        _limpar_cep(cep),
        "Curitiba, PR, Brasil",
    ]
    return ", ".join(p for p in partes if p)


@dataclass
class ResultadoGeocoding:
    status: str  # 'sucesso' | 'falha' | 'ambiguo'
    lat: float | None
    lon: float | None
    confianca: str | None


def _distancia_aproximada_metros(lat1, lon1, lat2, lon2) -> float:
    # Aproximação plana suficiente para distinguir "mesmo local" de
    # "lugares diferentes" numa escala de dezenas/centenas de metros -
    # não usada para nada além dessa triagem local em Python.
    import math

    dlat = (lat2 - lat1) * 111_320
    dlon = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


def geocodificar(endereco: str, session: requests.Session) -> ResultadoGeocoding:
    params = {
        "q": endereco,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "br",
        "addressdetails": 1,
    }
    resp = session.get(NOMINATIM_URL, params=params, timeout=15)
    resp.raise_for_status()
    resultados = resp.json()

    if not resultados:
        return ResultadoGeocoding(status="falha", lat=None, lon=None, confianca=None)

    primeiro = resultados[0]
    lat1, lon1 = float(primeiro["lat"]), float(primeiro["lon"])
    importancia1 = primeiro.get("importance")

    if len(resultados) == 1:
        confianca = (
            f"importance={importancia1};type={primeiro.get('type')};category={primeiro.get('category')};"
            f"place_rank={primeiro.get('place_rank')};n_candidatos=1"
        )
        return ResultadoGeocoding(status="sucesso", lat=lat1, lon=lon1, confianca=confianca)

    segundo = resultados[1]
    lat2, lon2 = float(segundo["lat"]), float(segundo["lon"])
    dist = _distancia_aproximada_metros(lat1, lon1, lat2, lon2)

    if dist <= LIMIAR_MESMO_LOCAL_METROS:
        confianca = (
            f"importance={importancia1};type={primeiro.get('type')};category={primeiro.get('category')};"
            f"place_rank={primeiro.get('place_rank')};n_candidatos={len(resultados)};dist_2o_candidato_m={dist:.1f}"
        )
        return ResultadoGeocoding(status="sucesso", lat=lat1, lon=lon1, confianca=confianca)

    confianca = (
        f"n_candidatos={len(resultados)};dist_2o_candidato_m={dist:.1f};"
        f"importancias={[r.get('importance') for r in resultados]}"
    )
    return ResultadoGeocoding(status="ambiguo", lat=None, lon=None, confianca=confianca)


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            "uso: python experimental/geocodificacao_piloto/run.py <territorio_id> [limite_teste]"
        )
    territorio_id = sys.argv[1]
    limite_teste = int(sys.argv[2]) if len(sys.argv) == 3 else None

    conn = psycopg2.connect(_database_url_psycopg2())
    conn.autocommit = False

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Pino no snapshot mais recente explicitamente (não só "a
        # observação mais recente de cada entidade que já passou por
        # esse bairro alguma vez") - uma DISTINCT ON sem esse pino
        # incluiria entidades cujo bairro atual já não é mais este (ex.:
        # estava aqui em julho, mudou/desapareceu em agosto), usando
        # endereço desatualizado.
        cur.execute(
            "SELECT MAX(observado_em) AS snapshot FROM canonical.observacao_entidade WHERE fonte_id = %s",
            (FONTE_ID,),
        )
        snapshot_mais_recente = cur.fetchone()["snapshot"]
        logger.info("snapshot mais recente: %s", snapshot_mais_recente)

        cur.execute(
            """
            SELECT
                entidade_id,
                atributos->>'endereco' AS endereco,
                atributos->>'numero' AS numero,
                atributos->>'bairro' AS bairro,
                atributos->>'cep' AS cep
            FROM canonical.observacao_entidade
            WHERE fonte_id = %s
              AND observado_em = %s
              AND atributos->>'territorio_id' = %s
            """,
            (FONTE_ID, snapshot_mais_recente, territorio_id),
        )
        entidades = cur.fetchall()

    if limite_teste is not None:
        entidades = entidades[:limite_teste]
        logger.info("MODO TESTE - limitado a %d entidades", limite_teste)

    logger.info("%d entidades (deduplicadas) para geocodificar em %s", len(entidades), territorio_id)

    http = requests.Session()
    http.headers["User-Agent"] = USER_AGENT

    contagem = {"sucesso": 0, "falha": 0, "ambiguo": 0}
    lote: list[tuple] = []

    for i, row in enumerate(entidades, start=1):
        endereco_usado = montar_endereco(row["endereco"], row["numero"], row["bairro"], row["cep"])

        try:
            resultado = geocodificar(endereco_usado, http)
        except requests.RequestException as e:
            logger.warning("erro de rede pra entidade %s: %s - gravando como falha", row["entidade_id"], e)
            resultado = ResultadoGeocoding(status="falha", lat=None, lon=None, confianca=f"erro_rede:{e}")

        contagem[resultado.status] += 1

        ponto_wkt = f"SRID=4326;POINT({resultado.lon} {resultado.lat})" if resultado.lat is not None else None
        lote.append(
            (
                row["entidade_id"],
                endereco_usado,
                ponto_wkt,
                resultado.status,
                resultado.confianca,
                SERVICO,
            )
        )

        if i % 50 == 0 or i == len(entidades):
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO experimental.geocodificacao_piloto
                        (entidade_id, endereco_usado, ponto, status, confianca_geocoding, servico)
                    VALUES %s
                    """,
                    lote,
                    template="(%s, %s, ST_GeogFromText(%s), %s, %s, %s)",
                )
            conn.commit()
            logger.info(
                "%d/%d processadas (sucesso=%d falha=%d ambiguo=%d)",
                i, len(entidades), contagem["sucesso"], contagem["falha"], contagem["ambiguo"],
            )
            lote = []

        time.sleep(1.0)  # limite de 1 req/s do Nominatim - nunca paralelizar

    conn.close()
    logger.info("concluído: %s", contagem)


if __name__ == "__main__":
    main()
