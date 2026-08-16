"""Restrição estrutural da seção 1 do prompt de referência do Radar de
Anúncios: um anúncio nunca é chamado de "venda" consumada, "vendido" ou
"valorização" em código/schema/UI que descreve dado de anúncio - o produto
mede intenção de mercado (oferta), nunca transação. Barato de escrever,
caro de não ter: sem isso, a regressão só aparece quando alguém lê a tela
de novo e percebe a palavra errada.

Escopo deliberadamente restrito aos arquivos do Radar de Anúncios (não o
repositório inteiro) - "transacao" é um valor de enum legítimo em
domain.valuation (dado de compra financiada do Radar Imobiliário, via BCB)
e não pode ser banido do projeto inteiro, só do vocabulário que descreve
anúncio.
"""
from __future__ import annotations

import ast
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Glob patterns (relativos à raiz do repo) cobrindo o Radar de Anúncios -
# crescem conforme os checkpoints seguintes adicionam conector/API/UI.
# Arquivos que ainda não existem simplesmente não geram match nenhum -
# esse teste não falha por ausência de arquivo, só por vocabulário errado
# num arquivo que existe.
PADROES_ALVO = (
    "src/domain/anuncio/**/*.py",
    "src/infrastructure/connectors/apolar_anuncios/**/*.py",
    "src/infrastructure/connectors/chavesnamao_anuncios/**/*.py",
    "src/pipelines/**/*anuncio*.py",
    "src/pipelines/**/*_anuncio/**/*.py",
    "src/analytics/**/*anuncio*.py",
    "apps/api/routers/anuncios*.py",
    "apps/web/src/**/*[Aa]nuncio*.ts",
    "apps/web/src/**/*[Aa]nuncio*.tsx",
)

# Frases proibidas (seção 1 da tabela do prompt de referência) - normalizadas
# sem acento e em minúsculo antes da comparação, pra "transação"/"transacao"
# e "valorização"/"valorizacao" caírem na mesma checagem.
FRASES_PROIBIDAS = (
    "vendido",
    "venda concretizada",
    "transacao",
    "valorizacao",
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _achados_python(caminho: Path) -> list[tuple[int, str]]:
    """Percorre a AST do arquivo, checando toda string literal exceto
    docstrings (primeira instrução de módulo/classe/função) - comentários
    (`# ...`) nunca entram na AST, então já ficam de fora sem tratamento
    especial; docstrings ficam de fora de propósito, porque são
    exatamente onde este projeto explica a própria regra (usando as
    palavras proibidas para dizer o que não fazer, como este arquivo
    faz)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    posicoes_docstring: set[tuple[int, int]] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(corpo, list) or not corpo:
            continue
        primeira = corpo[0]
        if (
            isinstance(primeira, ast.Expr)
            and isinstance(primeira.value, ast.Constant)
            and isinstance(primeira.value.value, str)
        ):
            posicoes_docstring.add((primeira.value.lineno, primeira.value.col_offset))

    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
            continue
        if (no.lineno, no.col_offset) in posicoes_docstring:
            continue
        normalizado = _normalizar(no.value)
        for frase in FRASES_PROIBIDAS:
            if frase in normalizado:
                achados.append((no.lineno, frase))
    return achados


def _achados_texto_simples(caminho: Path) -> list[tuple[int, str]]:
    """Fallback linha-a-linha para arquivos não-Python (frontend) - ignora
    linhas de comentário `//`, checa o resto contra as mesmas frases."""
    achados: list[tuple[int, str]] = []
    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        sem_comentario = re.sub(r"//.*$", "", linha)
        normalizado = _normalizar(sem_comentario)
        for frase in FRASES_PROIBIDAS:
            if frase in normalizado:
                achados.append((numero, frase))
    return achados


def _arquivos_alvo() -> list[Path]:
    encontrados: set[Path] = set()
    for padrao in PADROES_ALVO:
        encontrados.update(RAIZ.glob(padrao))
    return sorted(encontrados)


def test_nenhum_vocabulario_proibido_em_arquivos_do_radar_de_anuncios():
    arquivos = _arquivos_alvo()
    violacoes: list[str] = []

    for arquivo in arquivos:
        if arquivo.suffix == ".py":
            achados = _achados_python(arquivo)
        else:
            achados = _achados_texto_simples(arquivo)
        for linha, frase in achados:
            violacoes.append(f"{arquivo.relative_to(RAIZ)}:{linha} usa {frase!r}")

    assert not violacoes, (
        "Vocabulário proibido (seção 1 do prompt de referência do Radar de "
        "Anúncios - um anúncio nunca é 'venda'/'vendido'/'transação' "
        "consumada) encontrado:\n" + "\n".join(violacoes)
    )


def test_padroes_alvo_cobrem_pelo_menos_um_arquivo_real():
    # Guarda contra o teste acima passar silenciosamente porque os globs
    # ficaram errados e nunca casam nada - domain/anuncio já existe desde
    # este checkpoint, então pelo menos um arquivo real precisa aparecer.
    assert _arquivos_alvo(), "Nenhum arquivo do Radar de Anúncios encontrado pelos PADROES_ALVO"
