from __future__ import annotations

import csv
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "pipelines" / "geocoding" / "geocode_batch.R"
)


@dataclass(frozen=True)
class EnderecoParaGeocodificar:
    entidade_id: uuid.UUID
    logradouro: str
    numero: str
    cep: str
    bairro: str


@dataclass(frozen=True)
class ResultadoGeocodebr:
    entidade_id: uuid.UUID
    lat: float | None
    lon: float | None
    precisao: str | None
    tipo_resultado: str | None


def _rscript_path() -> str:
    # Caminho da instalação do R nesta máquina - não está no PATH por
    # padrão no Windows. Documentado em .env.example.
    return os.environ.get("MERCATOR_RSCRIPT_PATH", "Rscript")


def geocodificar_lote(enderecos: list[EnderecoParaGeocodificar]) -> list[ResultadoGeocodebr]:
    """Chama o geocodebr via subprocesso R sobre um lote de endereços -
    grava CSV de entrada, roda geocode_batch.R, lê o CSV de saída de
    volta. A integração com R é só essa troca de arquivos; nada de R
    embutido no processo Python, nunca chamado no caminho de uma
    requisição HTTP (só por pipelines de batch)."""
    if not enderecos:
        return []

    with tempfile.TemporaryDirectory(prefix="mercator_geocodebr_") as tmpdir:
        entrada = Path(tmpdir) / "entrada.csv"
        saida = Path(tmpdir) / "saida.csv"

        with entrada.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["entidade_id", "logradouro", "numero", "cep", "localidade", "municipio", "estado"]
            )
            for e in enderecos:
                writer.writerow(
                    [str(e.entidade_id), e.logradouro, e.numero, e.cep, e.bairro, "Curitiba", "PR"]
                )

        resultado = subprocess.run(
            [_rscript_path(), str(_SCRIPT_PATH), str(entrada), str(saida)],
            capture_output=True,
            text=True,
        )
        if resultado.returncode != 0:
            raise RuntimeError(
                f"geocode_batch.R falhou (exit {resultado.returncode}):\n{resultado.stderr}"
            )

        return _ler_resultado(saida)


def _ler_resultado(caminho: Path) -> list[ResultadoGeocodebr]:
    resultados = []
    with caminho.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            resultados.append(
                ResultadoGeocodebr(
                    entidade_id=uuid.UUID(row["entidade_id"]),
                    lat=float(row["lat"]) if row["lat"] else None,
                    lon=float(row["lon"]) if row["lon"] else None,
                    precisao=row["precisao"] or None,
                    tipo_resultado=row["tipo_resultado"] or None,
                )
            )
    return resultados
