from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from domain.contexto import IndicadorCensitarioSetor
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.text import slugify

logger = logging.getLogger(__name__)

DIR_URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
    "Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/"
)
RAW_DIR = Path("data/raw/ibge_censo_setor")

# O arquivo é BR inteiro (não há recorte por UF/município na fonte) e o
# nome carrega uma data de publicação que muda a cada atualização do IBGE
# (ex.: "..._basico_BR_20260520.zip") - resolvido em runtime pela mesma
# disciplina de alvaras_smf._arquivo_mais_recente, nunca hardcoded.
PADRAO_ARQUIVO_BASICO = re.compile(r'href="(Agregados_por_setores_basico_BR[^"]*\.zip)"')

# Código IBGE de Curitiba (7 dígitos) - único município filtrado nesta
# fase (produto é Curitiba-only).
MUNICIPIO_CURITIBA = "4106902"
ANO_REFERENCIA = 2022


class IbgeCensoSetorConnector:
    """Conector do arquivo "básico" (V0001-V0009: população e domicílios
    por tipo) do Censo Demográfico 2022, agregado por setor censitário
    (checkpoint 11d). Fonte estática (só se repete a cada ~10 anos).

    Achado do checkpoint 11d que simplificou o desenho original: o
    arquivo já carrega NM_BAIRRO por setor (não precisa de join
    espacial) - territorio_id é resolvido por slug do nome do bairro,
    mesmo padrão de ippuc_pgv/geocuritiba_cadastro. Também achado: as
    variáveis de "condição de ocupação" (própria/alugada) e "valor do
    aluguel" não existem nos resultados do universo (são variáveis de
    amostra, publicadas em outro lugar/momento) - confirmado lendo o
    dicionário de dados oficial, não presumido (ver
    docs/fontes-imobiliario.md)."""

    fonte_id = "ibge_censo_setor"
    cadencia = "estatica"

    def __init__(
        self,
        dir_url: str = DIR_URL,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        self._dir_url = dir_url
        self._session = session or requests.Session()
        self._raw_dir = raw_dir

    def fetch(self, nome_arquivo: str | None = None) -> RawSnapshot:
        nome_arquivo = nome_arquivo or self._arquivo_mais_recente()
        url = self._dir_url + nome_arquivo

        capturado_em = datetime.now(timezone.utc)
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self._raw_dir / nome_arquivo
        if zip_path.exists():
            logger.info("arquivo já baixado, reaproveitando: %s", zip_path)
        else:
            with self._session.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)

        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=str(zip_path),
            conteudo=str(zip_path),
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_slug: dict[str, str] | None = None,
    ) -> list[IndicadorCensitarioSetor]:
        territorio_id_por_slug = territorio_id_por_slug or {}
        zip_path = Path(snapshot.conteudo)

        with zipfile.ZipFile(zip_path) as zf:
            nomes_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not nomes_csv:
                raise RuntimeError(f"nenhum CSV encontrado dentro de {zip_path}")
            with zf.open(nomes_csv[0]) as f:
                df = pd.read_csv(
                    io.TextIOWrapper(f, encoding="latin-1"),
                    sep=";",
                    dtype={"CD_SETOR": str, "CD_MUN": str},
                    low_memory=False,
                )

        df = df[df["CD_MUN"] == MUNICIPIO_CURITIBA]

        bairros_nao_casados: set[str] = set()
        resultado = []
        for _, row in df.iterrows():
            nm_bairro = str(row["NM_BAIRRO"]).strip()
            territorio_id = territorio_id_por_slug.get(slugify(nm_bairro))
            if territorio_id is None:
                bairros_nao_casados.add(nm_bairro)

            resultado.append(
                IndicadorCensitarioSetor(
                    setor_censitario=row["CD_SETOR"],
                    territorio_id=territorio_id,
                    municipio_codigo=row["CD_MUN"],
                    area_km2=_decimal_virgula(row["AREA_KM2"]),
                    populacao_total=int(row["v0001"]),
                    domicilios_total=int(row["v0002"]),
                    domicilios_particulares_ocupados=int(row["v0007"]),
                    domicilios_particulares_vagos=int(row["v0009"]),
                    ano_referencia=ANO_REFERENCIA,
                    fonte_id=self.fonte_id,
                    snapshot_ref=snapshot.snapshot_ref,
                )
            )

        if bairros_nao_casados:
            logger.warning(
                "%d bairro(s) do Censo sem correspondência em dim_territorio: %s",
                len(bairros_nao_casados),
                sorted(bairros_nao_casados),
            )
        return resultado

    def _arquivo_mais_recente(self) -> str:
        resp = self._session.get(self._dir_url, timeout=30)
        resp.raise_for_status()
        match = PADRAO_ARQUIVO_BASICO.search(resp.text)
        if not match:
            raise RuntimeError(
                f"não foi possível encontrar o arquivo 'basico' na listagem de {self._dir_url}"
            )
        return match.group(1)


def _decimal_virgula(valor: str) -> float:
    return float(str(valor).replace(",", "."))
