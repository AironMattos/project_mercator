"""Carrega o resultado do geocodebr (CSV produzido por geocode_lindoia.R) em
experimental.geocodificacao_piloto_geocodebr. Roda fora de src/ de propósito,
mesmo padrão do piloto 1 - script descartável, não é código de produção.

status é derivado do prefixo de tipo_resultado ('d'=deterministico,
'p'=probabilistico - semantica documentada do proprio pacote), porque a
coluna nativa 'empate' so vem com resultado_completo=TRUE, que quebra nesta
versao do geocodebr (0.6.4) com um erro de binder do duckdb - bug real do
pacote, reproduzido com e sem resolver_empates. lat NULL (nao ocorreu nesta
amostra) vira falha.
"""
import os

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _database_url_psycopg2() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")


def montar_endereco(row) -> str:
    partes = [
        str(row["logradouro"]).strip(),
        str(row["numero"]).strip(),
        str(row["localidade"]).strip(),
        str(row["cep"]).strip(),
        "Curitiba, PR, Brasil",
    ]
    return ", ".join(p for p in partes if p and p != "nan")


def classificar_status(row) -> str:
    if pd.isna(row["lat"]) or pd.isna(row["lon"]):
        return "falha"
    tipo = str(row["tipo_resultado"])
    if tipo.startswith("p"):
        return "ambiguo"
    return "sucesso"


def main():
    df = pd.read_csv("experimental/geocodificacao_piloto/resultado_geocodebr_todos.csv", dtype=str)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    conn = psycopg2.connect(_database_url_psycopg2())
    with conn.cursor() as cur:
        cur.execute("TRUNCATE experimental.geocodificacao_piloto_geocodebr")

    lote = []
    contagem = {"sucesso": 0, "falha": 0, "ambiguo": 0}
    for _, row in df.iterrows():
        status = classificar_status(row)
        contagem[status] += 1
        ponto_wkt = None
        if not pd.isna(row["lat"]):
            ponto_wkt = f"SRID=4326;POINT({row['lon']} {row['lat']})"
        lote.append(
            (
                row["entidade_id"],
                montar_endereco(row),
                ponto_wkt,
                status,
                row["precisao"] if not pd.isna(row["precisao"]) else None,
            )
        )

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO experimental.geocodificacao_piloto_geocodebr
                (entidade_id, endereco_usado, ponto, status, precisao)
            VALUES %s
            """,
            lote,
            template="(%s, %s, ST_GeogFromText(%s), %s, %s)",
        )
    conn.commit()
    conn.close()
    print("carregado:", contagem, "total:", len(lote))


if __name__ == "__main__":
    main()
