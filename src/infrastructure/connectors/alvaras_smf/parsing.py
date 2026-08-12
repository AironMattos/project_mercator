from __future__ import annotations

import math
from datetime import date, datetime

MARCADOR_AUSENTE = "***"


def valor_ou_none(valor: object) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, float) and math.isnan(valor):
        return None
    texto = str(valor).strip()
    if not texto or texto == MARCADOR_AUSENTE:
        return None
    return texto


def parse_data_br(valor: object) -> str | None:
    """Converte data no formato DD/MM/AAAA (como a fonte informa) para ISO
    (AAAA-MM-DD). Retorna None se ausente ou inválida - a fonte tem datas
    inconsistentes e isso não deve derrubar o pipeline.
    """
    texto = valor_ou_none(valor)
    if texto is None:
        return None
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def parse_referencia_arquivo(nome_arquivo: str) -> date:
    """Extrai a data de referência do snapshot a partir do nome do arquivo
    (padrão AAAA-MM-01_Alvaras_-_Base_de_Dados.csv)."""
    prefixo = nome_arquivo.split("_Alvaras_")[0]
    return datetime.strptime(prefixo, "%Y-%m-%d").date()
