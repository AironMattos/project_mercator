from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import ClassVar

import requests

from domain.entity import Entidade
from domain.observation import ObservacaoEntidade
from infrastructure.connectors.alvaras_smf.parsing import parse_data_br, valor_ou_none
from infrastructure.connectors.base import RawSnapshot
from infrastructure.connectors.smu_alvaras_construcao.parsing import (
    normalizar_indicacao_fiscal,
    parse_tabela,
)

logger = logging.getLogger(__name__)

# HTTP puro, não HTTPS: a porta 443 deste host não responde (achado do
# checkpoint 11a, confirmado com curl -v - timeout de conexão). A porta
# 80 responde normalmente.
BASE_URL = "http://www5.curitiba.pr.gov.br/gtm/pmat_alvaraconstrucao"
URL_FORMULARIO = f"{BASE_URL}/relatoriomensalalvara.aspx"
URL_RELATORIO = f"{BASE_URL}/Default.aspx"
RAW_DIR = Path("data/raw/smu_alvaras_construcao")

_CAMPO_HIDDEN_RE = {
    campo: re.compile(rf'id="{campo}"\s+value="([^"]*)"')
    for campo in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")
}


@dataclass(frozen=True)
class RegistroObra:
    entidade: Entidade
    observacao: ObservacaoEntidade
    bairro_raw: str | None
    territorio_id: str | None


class _RelatorioSmuBase:
    """Conector do Relatório Mensal Alvará/CVCO (SMU) - sistema ASP.NET
    WebForms antigo (IIS 6.0), sem API/exportação em lote documentada,
    mas com saída real em .xls (HTML/MSO) via postback do formulário
    (achado do checkpoint 11a - a página original nunca tinha ficado
    fora do ar, a falha era do lado da verificação, não da fonte).

    Duas subclasses (AlvaraConstrucaoConnector/CvcoConnector) reaproveitam
    toda a lógica de submissão/parsing daqui - só o valor de rblRelacao e
    o fonte_id mudam entre os dois relatórios.
    """

    cadencia = "mensal"
    _rbl_relacao: ClassVar[str]

    def __init__(
        self,
        session: requests.Session | None = None,
        raw_dir: Path = RAW_DIR,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session or requests.Session()
        self._raw_dir = raw_dir
        self._base_url = base_url

    def fetch(
        self,
        ano: int | None = None,
        mes_inicio: int = 1,
        mes_fim: int | None = None,
    ) -> RawSnapshot:
        hoje = datetime.now(timezone.utc)
        ano = ano or hoje.year
        mes_fim = mes_fim or (hoje.month if ano == hoje.year else 12)

        campos_ocultos = self._campos_ocultos_do_formulario()
        payload = {
            **campos_ocultos,
            "rblRelacao": self._rbl_relacao,
            "ddlAno": str(ano),
            "ddlMes": str(mes_inicio),
            "ddlMesFinal": str(mes_fim),
            "btnGerarRelatorio": "Gerar Relatório ",
        }
        resp = self._session.post(
            f"{self._base_url}/Default.aspx", data=payload, timeout=180
        )
        resp.raise_for_status()
        resp.encoding = "ISO-8859-1"
        html = resp.text

        capturado_em = datetime.now(timezone.utc)
        referencia = date(ano, mes_inicio, 1)
        snapshot_ref = self._salvar_raw(html, ano, mes_inicio, mes_fim, capturado_em)
        return RawSnapshot(
            fonte_id=self.fonte_id,
            capturado_em=capturado_em,
            snapshot_ref=snapshot_ref,
            conteudo={"html": html, "observado_em": referencia},
        )

    def normalize(
        self,
        snapshot: RawSnapshot,
        territorio_id_por_indicacao_fiscal: dict[str, str] | None = None,
    ) -> Iterator[RegistroObra]:
        territorio_id_por_indicacao_fiscal = territorio_id_por_indicacao_fiscal or {}
        observado_em = snapshot.conteudo["observado_em"]
        linhas = parse_tabela(snapshot.conteudo["html"])

        for linha in linhas:
            registro = self._normalizar_linha(
                linha, observado_em, snapshot.snapshot_ref, territorio_id_por_indicacao_fiscal
            )
            if registro is not None:
                yield registro

    def _normalizar_linha(
        self,
        linha: dict[str, str | None],
        observado_em: date,
        snapshot_ref: str,
        territorio_id_por_indicacao_fiscal: dict[str, str],
    ) -> RegistroObra | None:
        numero_alvara = valor_ou_none(linha.get("numero_alvara"))
        if numero_alvara is None:
            logger.warning("linha sem Número Alvará ignorada")
            return None

        indicacao_fiscal = valor_ou_none(linha.get("indicacao_fiscal"))
        chave_lookup = normalizar_indicacao_fiscal(indicacao_fiscal)
        territorio_id = (
            territorio_id_por_indicacao_fiscal.get(chave_lookup) if chave_lookup else None
        )
        bairro_raw = valor_ou_none(linha.get("bairro"))

        atributos = {
            "indicacao_fiscal": indicacao_fiscal,
            "inscricao_imobiliaria": valor_ou_none(linha.get("inscricao_imobiliaria")),
            "data_criacao_alvara": parse_data_br(linha.get("data_criacao_alvara")),
            "data_inicio_obra": parse_data_br(linha.get("data_inicio_obra")),
            "data_conclusao_obra": parse_data_br(linha.get("data_conclusao_obra")),
            "logradouro": valor_ou_none(linha.get("logradouro")),
            "numero": valor_ou_none(linha.get("numero")),
            "bairro": bairro_raw,
            "territorio_id": territorio_id,
            "grupo_zoneamento": valor_ou_none(linha.get("grupo_zoneamento")),
            "abrangencia": valor_ou_none(linha.get("abrangencia")),
            "quantidade_pavimentos": valor_ou_none(linha.get("quantidade_pavimentos")),
            "quantidade_unidades_residenciais": valor_ou_none(
                linha.get("quantidade_unidades_residenciais")
            ),
            "quantidade_unidades_nao_residenciais": valor_ou_none(
                linha.get("quantidade_unidades_nao_residenciais")
            ),
            "numero_alvara": numero_alvara,
            "usos_alvara": valor_ou_none(linha.get("usos_alvara")),
            "finalidade": valor_ou_none(linha.get("finalidade")),
            "materiais": valor_ou_none(linha.get("materiais")),
            "metragem_construida_lote": valor_ou_none(linha.get("metragem_construida_lote")),
            "firma_construtora": valor_ou_none(linha.get("firma_construtora")),
            "numero_cvco": valor_ou_none(linha.get("numero_cvco")),
            "tipo_vistoria": valor_ou_none(linha.get("tipo_vistoria")),
            "data_vistoria": parse_data_br(linha.get("data_vistoria")),
            "area_vistoria": valor_ou_none(linha.get("area_vistoria")),
        }

        entidade = Entidade(tipo_entidade="obra", identificador_fonte=numero_alvara)
        observacao = ObservacaoEntidade(
            entidade_id=entidade.entidade_id,
            observado_em=observado_em,
            atributos=atributos,
            fonte_id=self.fonte_id,
            snapshot_ref=snapshot_ref,
        )
        return RegistroObra(
            entidade=entidade,
            observacao=observacao,
            bairro_raw=bairro_raw,
            territorio_id=territorio_id,
        )

    def _campos_ocultos_do_formulario(self) -> dict[str, str]:
        resp = self._session.get(f"{self._base_url}/relatoriomensalalvara.aspx", timeout=30)
        resp.raise_for_status()
        resp.encoding = "ISO-8859-1"
        html = resp.text
        campos = {}
        for campo, padrao in _CAMPO_HIDDEN_RE.items():
            match = padrao.search(html)
            if not match:
                raise RuntimeError(
                    f"campo oculto {campo!r} não encontrado no formulário - a "
                    "estrutura da página pode ter mudado"
                )
            campos[campo] = match.group(1)
        return campos

    def _salvar_raw(
        self, html: str, ano: int, mes_inicio: int, mes_fim: int, capturado_em: datetime
    ) -> str:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        nome = f"{self.fonte_id}_{ano}_{mes_inicio:02d}-{mes_fim:02d}_{capturado_em:%Y%m%dT%H%M%S}.html"
        path = self._raw_dir / nome
        path.write_text(html, encoding="utf-8")
        return str(path)


class AlvaraConstrucaoConnector(_RelatorioSmuBase):
    """Relatório "Alvará da Construção" (rblRelacao=1) - fonte de
    ALVARA_APROVADO."""

    fonte_id = "smu_alvara_construcao"
    _rbl_relacao = "1"


class CvcoConnector(_RelatorioSmuBase):
    """Relatório "Certificado de Vistoria de Conclusão de Obra" (CVCO,
    rblRelacao=2) - fonte de OBRA_CONCLUIDA."""

    fonte_id = "smu_cvco"
    _rbl_relacao = "2"
