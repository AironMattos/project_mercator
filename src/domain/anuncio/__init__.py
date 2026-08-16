from __future__ import annotations

from domain.anuncio.impressao_digital import calcular_impressao_digital
from domain.anuncio.models import (
    OPERACOES_VALIDAS,
    TIPOLOGIAS_VALIDAS,
    ClusterImovel,
    ObservacaoAnuncio,
)
from domain.anuncio.regras import (
    detectar_anuncio_encerrado,
    detectar_eventos_anuncio_par,
    detectar_reanuncio,
)
from domain.anuncio.resolucao import (
    JANELA_PADRAO_DIAS,
    CandidatoResolucao,
    resolver_imoveis,
)
from domain.anuncio.taxonomia import NAO_CLASSIFICADO, NOMES_TIPOLOGIA, normalizar_tipologia

__all__ = [
    "OPERACOES_VALIDAS",
    "TIPOLOGIAS_VALIDAS",
    "ClusterImovel",
    "ObservacaoAnuncio",
    "calcular_impressao_digital",
    "detectar_anuncio_encerrado",
    "detectar_eventos_anuncio_par",
    "detectar_reanuncio",
    "JANELA_PADRAO_DIAS",
    "CandidatoResolucao",
    "resolver_imoveis",
    "NAO_CLASSIFICADO",
    "NOMES_TIPOLOGIA",
    "normalizar_tipologia",
]
