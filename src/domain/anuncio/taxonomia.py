from __future__ import annotations

from domain.anuncio.models import TIPOLOGIAS_VALIDAS

# Tradução de string bruta -> tipologia canônica, nunca um `if` disperso no
# parser de cada conector (mesma disciplina de dim_cnae -> dim_categoria,
# checkpoint 4). Lista pequena e explícita de propósito: cobre os termos
# reais observados nos slugs de URL da Apolar e da Chaves na Mão (seção 6
# do prompt de referência do Radar de Anúncios) - "comercialresidencial"
# (Apolar) e variações compostas entram como chave própria, não via regex
# genérico, para o mapeamento continuar auditável a olho.
_MAPEAMENTO: dict[str, str] = {
    "apartamento": "apartamento",
    "apto": "apartamento",
    "flat": "apartamento",
    "casa": "casa",
    "casaemcondominio": "casa",
    "sobrado": "sobrado",
    "kitnet": "kitnet_studio",
    "studio": "kitnet_studio",
    "loft": "kitnet_studio",
    "cobertura": "cobertura",
    "penthouse": "cobertura",
    "terreno": "terreno",
    "lote": "terreno",
    "comercialresidencial": "terreno",
    "salacomercial": "sala_comercial",
    "sala": "sala_comercial",
    "loja": "sala_comercial",
    "conjuntocomercial": "sala_comercial",
    "galpao": "galpao",
    "barracao": "galpao",
    "chacara": "chacara_sitio",
    "sitio": "chacara_sitio",
    "fazenda": "chacara_sitio",
}

NAO_CLASSIFICADO = "nao_classificado"

# Rótulos legíveis, usados só para semear canonical.dim_tipologia_imovel
# (pipelines.ingestion.run_tipologias_imovel) - a validação de domínio em
# si usa TIPOLOGIAS_VALIDAS, nunca estas strings.
NOMES_TIPOLOGIA: dict[str, str] = {
    "apartamento": "Apartamento",
    "casa": "Casa",
    "sobrado": "Sobrado",
    "kitnet_studio": "Kitnet/Studio",
    "cobertura": "Cobertura",
    "terreno": "Terreno",
    "sala_comercial": "Sala comercial",
    "galpao": "Galpão",
    "chacara_sitio": "Chácara/Sítio",
    NAO_CLASSIFICADO: "Não classificado",
}


def normalizar_tipologia(bruto: str) -> str:
    """Normaliza uma string de tipologia bruta (ex.: slug de URL, campo de
    formulário da fonte) para uma das TIPOLOGIAS_VALIDAS. Regra pura, sem
    I/O - remove espaço/hífen/acento simples e casa contra o mapeamento
    explícito acima; o que não casar vira NAO_CLASSIFICADO, nunca é
    descartado silenciosamente (mesmo tratamento de CNAE não normalizável
    no Radar de Comércio - fica visível no relatório de qualidade, não
    escondido em "outros")."""
    chave = _normalizar_chave(bruto)
    tipologia = _MAPEAMENTO.get(chave, NAO_CLASSIFICADO)
    assert tipologia in TIPOLOGIAS_VALIDAS
    return tipologia


def _normalizar_chave(bruto: str) -> str:
    sem_acento = (
        bruto.lower()
        .replace("á", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("õ", "o")
        .replace("ô", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return "".join(ch for ch in sem_acento if ch.isalnum())
