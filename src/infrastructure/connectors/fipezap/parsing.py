"""Parsing puro (sem I/O, sem pdfplumber) do texto já extraído das páginas
relevantes do informe mensal FipeZAP - checkpoint 12b do Radar de
Anúncios, seção 9 do prompt de referência ("FipeZap: informe mensal em
PDF com os 10 bairros mais representativos por cidade").

Duas fontes de texto dentro do mesmo PDF, extraídas separadamente em
connector.py:
- página "DESTAQUES DO MÊS" (prosa corrida) - de onde vêm as 4 métricas
  de nível cidade. Achado real: a tabela "capitais monitoradas" da mesma
  página, quando extraída via `page.extract_text()`, sai com a ordem dos
  caracteres embaralhada em alguns meses/operações (largura de coluna
  variável do PDF) - a prosa corrida ao lado, no mesmo relatório, sempre
  extrai limpa. Por isso o nível cidade é lido da prosa, não da tabela.
- página com o cabeçalho "CIDADE (UF)" (ex.: "CURITIBA (PR)") - de onde
  vem a lista de bairros mais representativos, que sempre extrai como
  texto legível independente da posição na página.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from domain.contexto import IndicadorFipezapBairro, IndicadorFipezapCidade

# Rentabilidade do aluguel ("4,86%a.a.") nunca tem sinal +/- explícito,
# diferente das 3 variações que este parser busca - por isso o sinal
# obrigatório no regex já filtra esse quinto número sem precisar de um
# tratamento especial pra ele.
_PADRAO_VARIACAO_CIDADE = r"{cidade}\s*\(([+-]\d+,\d+)%\)"
_PADRAO_PRECO_CIDADE = r"{cidade}\s*\(R\$\s*([\d.,]+)\s*/m[²2]\)"

_PADRAO_LINHA_BAIRRO = re.compile(
    r"([A-ZÀ-Ú][A-ZÀ-Ú …]*?)\s+R\$\s*([\d.,]+)\s*/m[²2]\s+([+-]\d+,\d+)%"
)


@dataclass(frozen=True)
class KpisCidade:
    variacao_mensal: float | None
    variacao_acumulada_ano: float | None
    variacao_12m: float | None
    preco_medio_m2: float | None


@dataclass(frozen=True)
class LinhaBairro:
    bairro_nome: str
    preco_medio_m2: float
    variacao_12m: float | None


def _percentual_para_fracao(texto: str) -> float:
    """'+0,08' -> 0.0008 - mesma escala (fração, não ponto percentual)
    já usada por domain.contexto.IndicadorAluguelMercado."""
    return float(texto.replace(",", ".")) / 100.0


def _preco(texto: str, operacao: str) -> float:
    """Formato de preço diverge por operação na aparência (venda usa
    ponto como separador de milhar sem decimais, ex. '17.525'; locação
    usa vírgula decimal sem separador de milhar, ex. '54,2' - valores
    sempre abaixo de 100) mas a transformação é a mesma nos dois casos:
    remover ponto (nunca é decimal aqui) e trocar vírgula por ponto
    decimal. `operacao` fica como parâmetro só para deixar a intenção
    explícita no call site, não porque o parsing difere de fato."""
    limpo = texto.strip()
    return float(limpo.replace(".", "").replace(",", "."))


def extrair_kpis_cidade(texto_pagina_destaques: str, cidade: str = "Curitiba") -> KpisCidade:
    """As 3 variações (mês, ano corrente, 12 meses) aparecem nessa ordem
    em 3 parágrafos narrativos distintos e sempre nessa sequência -
    confirmado nos relatórios de venda e locação reais do checkpoint
    12b. Uma eventual 4ª ocorrência com sinal (não deveria existir nesses
    parágrafos) seria ignorada silenciosamente - aceito como limitação
    conhecida de um parser por regex sobre prosa, não sobre uma tabela
    estruturada."""
    padrao_var = re.compile(_PADRAO_VARIACAO_CIDADE.format(cidade=re.escape(cidade)))
    variacoes = padrao_var.findall(texto_pagina_destaques)

    padrao_preco = re.compile(_PADRAO_PRECO_CIDADE.format(cidade=re.escape(cidade)))
    preco_match = padrao_preco.search(texto_pagina_destaques)

    mensal = _percentual_para_fracao(variacoes[0]) if len(variacoes) >= 1 else None
    ano = _percentual_para_fracao(variacoes[1]) if len(variacoes) >= 2 else None
    doze_meses = _percentual_para_fracao(variacoes[2]) if len(variacoes) >= 3 else None
    preco = _preco(preco_match.group(1), operacao="venda") if preco_match else None
    # _preco() com operacao="venda" aqui é deliberado - o preço de nível
    # cidade nesta prosa nunca usa o formato decimal curto de locação
    # (é sempre "R$ 11.761/m²", nunca "R$ 48,91/m²" na frase narrativa,
    # mesmo no relatório de locação - conferido nos dois PDFs reais).

    return KpisCidade(
        variacao_mensal=mensal,
        variacao_acumulada_ano=ano,
        variacao_12m=doze_meses,
        preco_medio_m2=preco,
    )


def extrair_bairros(texto_pagina_cidade: str, operacao: str) -> list[LinhaBairro]:
    """Extrai a lista de bairros mais representativos da página
    dedicada de uma cidade (ex.: "CURITIBA (PR)"). Posição da tabela na
    página varia entre venda/locação (achado real) - por isso varre
    todas as linhas do texto por padrão, em vez de assumir um intervalo
    fixo."""
    resultado: list[LinhaBairro] = []
    for linha in texto_pagina_cidade.splitlines():
        # busca (não âncora no início) porque rótulos de legenda de
        # gráfico ("Preço médio", "Sem informação") às vezes vêm colados
        # à mesma linha de uma linha de dado real (achado real do
        # checkpoint 12b) - o grupo do nome exige só maiúscula/espaço,
        # então esses rótulos (com minúscula) nunca entram na captura.
        m = _PADRAO_LINHA_BAIRRO.search(linha.strip())
        if not m:
            continue
        nome, preco_bruto, variacao_bruta = m.groups()
        resultado.append(
            LinhaBairro(
                bairro_nome=nome.strip(),
                preco_medio_m2=_preco(preco_bruto, operacao),
                variacao_12m=_percentual_para_fracao(variacao_bruta),
            )
        )
    return resultado


def encontrar_pagina_destaques(paginas_texto: list[str]) -> str | None:
    """Localiza a página "DESTAQUES DO MÊS" (prosa corrida com os KPIs de
    cidade) por cabeçalho, não por índice fixo - a posição já variou
    entre os relatórios reais inspecionados no checkpoint 12b (sempre
    perto do início, mas não vale travar num número de página)."""
    for texto in paginas_texto:
        primeira_linha = next((linha.strip() for linha in texto.splitlines() if linha.strip()), "")
        if primeira_linha.upper().startswith("DESTAQUES DO MÊS"):
            return texto
    return None


def encontrar_pagina_cidade(paginas_texto: list[str], cidade: str) -> str | None:
    """Localiza a página cujo cabeçalho é exatamente "CIDADE (UF)" (ex.:
    "CURITIBA (PR)") - não basta a cidade aparecer em algum lugar da
    página (ela também aparece em gráficos comparativos de outras
    páginas), por isso a checagem é na primeira linha não vazia."""
    cidade_upper = cidade.upper()
    for texto in paginas_texto:
        linhas = [linha for linha in texto.splitlines() if linha.strip()]
        if not linhas:
            continue
        primeira = linhas[0].strip()
        if primeira.startswith(cidade_upper) and "(" in primeira and ")" in primeira:
            return texto
    return None


def resolver_territorio_bairro(
    bairro_nome: str, territorio_id_por_slug: dict[str, str]
) -> str | None:
    """Melhor esforço: tenta o nome como veio; se terminar truncado com
    "…" (achado real do checkpoint 12b - ver módulo), tenta casar por
    prefixo contra os slugs conhecidos. Só resolve por prefixo quando
    exatamente um bairro bate - prefixo ambíguo fica None, nunca um
    palpite."""
    from infrastructure.connectors.text import slugify

    slug = slugify(bairro_nome.rstrip("…").strip())
    if bairro_nome.endswith("…"):
        candidatos = [
            territorio_id
            for nome_slug, territorio_id in territorio_id_por_slug.items()
            if nome_slug.startswith(slug)
        ]
        return candidatos[0] if len(candidatos) == 1 else None
    return territorio_id_por_slug.get(slug)


def montar_indicadores(
    paginas_por_operacao: dict[str, list[str]],
    periodo_referencia: date,
    snapshot_ref_por_operacao: dict[str, str],
    territorio_id_por_slug: dict[str, str],
    fonte_id: str,
    cidade: str = "Curitiba",
) -> list[IndicadorFipezapCidade | IndicadorFipezapBairro]:
    """Orquestra as funções puras acima sobre o texto já extraído (uma
    lista de páginas) de cada operação - separado de `connector.py` para
    ser testável sem PDF real (nenhuma dependência de pdfplumber aqui)."""
    resultado: list[IndicadorFipezapCidade | IndicadorFipezapBairro] = []

    for operacao, paginas_texto in paginas_por_operacao.items():
        snapshot_ref = snapshot_ref_por_operacao[operacao]

        pagina_destaques = encontrar_pagina_destaques(paginas_texto)
        if pagina_destaques is not None:
            kpis = extrair_kpis_cidade(pagina_destaques, cidade=cidade)
            if kpis.preco_medio_m2 is not None:
                resultado.append(
                    IndicadorFipezapCidade(
                        cidade=cidade,
                        operacao=operacao,
                        periodo_referencia=periodo_referencia,
                        preco_medio_m2=kpis.preco_medio_m2,
                        variacao_mensal=kpis.variacao_mensal,
                        variacao_acumulada_ano=kpis.variacao_acumulada_ano,
                        variacao_12m=kpis.variacao_12m,
                        fonte_id=fonte_id,
                        snapshot_ref=snapshot_ref,
                    )
                )

        pagina_cidade = encontrar_pagina_cidade(paginas_texto, cidade)
        if pagina_cidade is None:
            continue

        for linha in extrair_bairros(pagina_cidade, operacao=operacao):
            resultado.append(
                IndicadorFipezapBairro(
                    cidade=cidade,
                    operacao=operacao,
                    periodo_referencia=periodo_referencia,
                    bairro_nome=linha.bairro_nome,
                    preco_medio_m2=linha.preco_medio_m2,
                    variacao_12m=linha.variacao_12m,
                    territorio_id=resolver_territorio_bairro(
                        linha.bairro_nome, territorio_id_por_slug
                    ),
                    fonte_id=fonte_id,
                    snapshot_ref=snapshot_ref,
                )
            )

    return resultado
