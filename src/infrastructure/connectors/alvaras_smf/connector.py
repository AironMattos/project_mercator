from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from domain.entity import Entidade
from domain.observation import ObservacaoEntidade
from infrastructure.connectors.alvaras_smf.parsing import (
    parse_data_br,
    parse_referencia_arquivo,
    valor_ou_none,
)
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.text import slugify

logger = logging.getLogger(__name__)

DIRETORIO_URL = "http://dadosabertos.c3sl.ufpr.br/curitiba/BaseAlvaras/"
PADRAO_ARQUIVO = re.compile(r'href="((\d{4}-\d{2}-01)_Alvaras_-_Base_de_Dados\.csv)"')
RAW_DIR = Path("data/raw/alvaras_smf")
TAMANHO_CHUNK_LEITURA = 20_000
TAMANHO_CHUNK_DOWNLOAD = 1024 * 1024


@dataclass(frozen=True)
class RegistroNormalizado:
    entidade: Entidade
    observacao: ObservacaoEntidade
    bairro_raw: str | None
    territorio_id: str | None


class AlvarasSmfConnector:
    """Conector da Base de Alvarás (Curitiba/SMF).

    O host oficialmente documentado (mid.curitiba.pr.gov.br) não está mais
    servindo o arquivo (404/403); o próprio catálogo de dados abertos da
    prefeitura aponta hoje para o mirror do C3SL/UFPR. A URL exata do mês
    corrente é sempre resolvida a partir da listagem do diretório - nunca
    hardcoded.
    """

    fonte_id = "alvaras_smf"
    cadencia = "mensal"

    def __init__(
        self,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
        diretorio_url: str = DIRETORIO_URL,
    ) -> None:
        self._session = session or requests.Session()
        self._raw_dir = raw_dir
        self._diretorio_url = diretorio_url

    def fetch(self, nome_arquivo: str | None = None) -> RawSnapshot:
        """Baixa o snapshot. Por padrão resolve o mês mais recente disponível
        no diretório; passar `nome_arquivo` explicitamente permite buscar um
        mês histórico específico (ex.: para detecção de evento, que precisa
        de dois snapshots de meses diferentes).
        """
        nome_arquivo = nome_arquivo or self._arquivo_mais_recente()
        url = self._diretorio_url + nome_arquivo
        referencia = parse_referencia_arquivo(nome_arquivo)

        self._raw_dir.mkdir(parents=True, exist_ok=True)
        destino = self._raw_dir / nome_arquivo

        if destino.exists():
            logger.info("reaproveitando snapshot já baixado: %s", destino)
            return RawSnapshot(
                fonte_id=self.fonte_id,
                capturado_em=datetime.now(timezone.utc),
                snapshot_ref=str(destino),
                conteudo={"path": str(destino), "observado_em": referencia, "url": url},
            )

        logger.info("baixando %s (em streaming, sem carregar em memória)...", url)
        with self._session.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            baixado = 0
            proximo_log_mb = 20
            with open(destino, "wb") as arquivo:
                for chunk in resp.iter_content(chunk_size=TAMANHO_CHUNK_DOWNLOAD):
                    arquivo.write(chunk)
                    baixado += len(chunk)
                    baixado_mb = baixado // (1024 * 1024)
                    if baixado_mb >= proximo_log_mb:
                        if total:
                            logger.info(
                                "baixado %.1f%% (%d/%d MB)",
                                100 * baixado / total,
                                baixado_mb,
                                total // (1024 * 1024),
                            )
                        else:
                            logger.info("baixado %d MB", baixado_mb)
                        proximo_log_mb += 20

        logger.info("download concluído: %s (%d bytes)", destino, baixado)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=datetime.now(timezone.utc),
            snapshot_ref=str(destino),
            conteudo={"path": str(destino), "observado_em": referencia, "url": url},
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_slug: dict[str, str] | None = None,
    ) -> Iterator[RegistroNormalizado]:
        """Gera um RegistroNormalizado por linha, lendo o CSV em chunks -
        nunca carrega o arquivo inteiro (centenas de MB) em memória.

        BAIRRO é resolvido contra dim_territorio via slug; divergências de
        grafia são um problema esperado - ficam registradas em log (uma vez
        por bairro não casado, não uma vez por linha) e a linha segue sendo
        normalizada normalmente, só sem territorio_id.
        """
        territorio_id_por_slug = territorio_id_por_slug or {}
        path = snapshot.conteudo["path"]
        observado_em = snapshot.conteudo["observado_em"]
        bairros_nao_casados: set[str] = set()

        leitor = pd.read_csv(
            path,
            sep=";",
            encoding="latin-1",
            dtype=str,
            na_values=["***"],
            keep_default_na=False,
            chunksize=TAMANHO_CHUNK_LEITURA,
        )

        for chunk in leitor:
            for row in chunk.to_dict(orient="records"):
                registro = self._normalizar_linha(
                    row,
                    observado_em,
                    snapshot.snapshot_ref,
                    territorio_id_por_slug,
                    bairros_nao_casados,
                )
                if registro is not None:
                    yield registro

        if bairros_nao_casados:
            logger.warning(
                "%d bairro(s) do alvará sem correspondência em dim_territorio: %s",
                len(bairros_nao_casados),
                sorted(bairros_nao_casados),
            )

    def _normalizar_linha(
        self,
        row: dict,
        observado_em,
        snapshot_ref: str,
        territorio_id_por_slug: dict[str, str],
        bairros_nao_casados: set[str],
    ) -> RegistroNormalizado | None:
        numero_alvara = valor_ou_none(row.get("NUMERO_DO_ALVARA"))
        if numero_alvara is None:
            logger.warning("linha sem NUMERO_DO_ALVARA ignorada")
            return None

        bairro_raw = valor_ou_none(row.get("BAIRRO"))
        territorio_id = None
        if bairro_raw:
            territorio_id = territorio_id_por_slug.get(slugify(bairro_raw))
            if territorio_id is None:
                bairros_nao_casados.add(bairro_raw)

        atributos = {
            "nome_empresarial": valor_ou_none(row.get("NOME_EMPRESARIAL")),
            "nome_fantasia": valor_ou_none(row.get("NOME_FANTASIA")),
            "numero_do_alvara": numero_alvara,
            "inicio_atividade": parse_data_br(row.get("INICIO_ATIVIDADE")),
            "data_emissao": parse_data_br(row.get("DATA_EMISSAO")),
            "data_expiracao": parse_data_br(row.get("DATA_EXPIRACAO")),
            "endereco": valor_ou_none(row.get("ENDERECO")),
            "numero": valor_ou_none(row.get("NUMERO")),
            "unidade": valor_ou_none(row.get("UNIDADE")),
            "andar": valor_ou_none(row.get("ANDAR")),
            "complemento": valor_ou_none(row.get("COMPLEMENTO")),
            "bairro": bairro_raw,
            "territorio_id": territorio_id,
            "cep": valor_ou_none(row.get("CEP")),
            "cnae_principal": valor_ou_none(row.get("CNAE_ATIVIDADE_PRINCIPAL")),
            "atividade_principal": valor_ou_none(row.get("ATIVIDADE_PRINCIPAL")),
        }

        entidade = Entidade(tipo_entidade="comercio", identificador_fonte=numero_alvara)
        observacao = ObservacaoEntidade(
            entidade_id=entidade.entidade_id,
            observado_em=observado_em,
            atributos=atributos,
            fonte_id=self.fonte_id,
            snapshot_ref=snapshot_ref,
        )
        return RegistroNormalizado(
            entidade=entidade,
            observacao=observacao,
            bairro_raw=bairro_raw,
            territorio_id=territorio_id,
        )

    def _arquivo_mais_recente(self) -> str:
        resp = self._session.get(self._diretorio_url, timeout=30)
        resp.raise_for_status()
        candidatos = PADRAO_ARQUIVO.findall(resp.text)
        if not candidatos:
            raise RuntimeError(
                f"nenhum arquivo '*_Alvaras_-_Base_de_Dados.csv' encontrado em "
                f"{self._diretorio_url} - a fonte pode ter mudado de formato/local"
            )
        candidatos.sort(key=lambda c: c[1])
        return candidatos[-1][0]
