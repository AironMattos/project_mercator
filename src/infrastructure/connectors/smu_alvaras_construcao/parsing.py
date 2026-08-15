from __future__ import annotations

import re
from html import unescape

# Ordem confirmada contra o relatório real (checkpoint 11a) - o relatório
# de "Alvará da Construção" tem as primeiras 34 colunas; o de "CVCO" tem
# as mesmas 34 mais "Área Vistoria" (35ª). Mapeamento por posição, não
# por texto de cabeçalho - mais robusto a variação de entidade HTML no
# cabeçalho em si.
COLUNAS = (
    "indicacao_fiscal",
    "inscricao_imobiliaria",
    "data_criacao_alvara",
    "data_inicio_obra",
    "data_conclusao_obra",
    "logradouro",
    "numero",
    "bairro",
    "grupo_zoneamento",
    "abrangencia",
    "quantidade_pavimentos",
    "quantidade_unidades_residenciais",
    "quantidade_unidades_nao_residenciais",
    "numero_alvara",
    "usos_alvara",
    "sub_usos_alvara",
    "finalidade",
    "materiais",
    "metragem_area_remanescente",
    "metragem_construida_lote",
    "numero_capacs_utilizadas",
    "aca_area_adicional_construcao",
    "area_liberada",
    "metragem_area_reforma_alvara",
    "quantidade_blocos_alvara",
    "quantidade_sub_solo_alvara",
    "autor_projeto",
    "numero_registro_crea_cau_au",
    "responsavel_tecnico",
    "numero_registro_crea_cau_rt",
    "firma_construtora",
    "numero_cvco",
    "tipo_vistoria",
    "data_vistoria",
    "area_vistoria",
)

_LINHA_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELULA_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def celula_ou_none(texto_bruto: str) -> str | None:
    texto = unescape(texto_bruto).replace("\xa0", " ").strip()
    return texto or None


def normalizar_indicacao_fiscal(texto: str | None) -> str | None:
    """Remove os pontos separadores que o relatório da SMU usa
    ("12.006.027") - a Indicação Fiscal do GeoCuritiba/Lote Cadastral é
    só dígitos ("12006027"). Achado real, encontrado rodando o pipeline
    contra dado real do checkpoint 11c: sem essa normalização, 0% das
    linhas resolviam território, mesmo a chave sendo a mesma - só o
    formato divergia entre as duas fontes.
    """
    if not texto:
        return None
    apenas_digitos = re.sub(r"\D", "", texto)
    return apenas_digitos or None


def parse_tabela(html: str) -> list[dict[str, str | None]]:
    """Extrai as linhas de dado do HTML/MSO (Excel salvo como HTML) que o
    relatório da SMU devolve. A primeira linha (<tr>) é o cabeçalho -
    descartada aqui, o mapeamento de coluna é por posição (ver COLUNAS).
    """
    linhas_brutas = _LINHA_RE.findall(html)
    registros = []
    for linha in linhas_brutas[1:]:  # pula o cabeçalho
        celulas = [celula_ou_none(c) for c in _CELULA_RE.findall(linha)]
        if not celulas or all(c is None for c in celulas):
            continue
        registros.append(dict(zip(COLUNAS, celulas)))
    return registros
