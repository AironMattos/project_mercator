from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from domain.anuncio.models import ClusterImovel

# Janela padrão da seção 8.1 do prompt de referência do Radar de
# Anúncios: "impressao_digital... coincida dentro de uma janela de tempo
# razoável (ex.: 30 dias)".
JANELA_PADRAO_DIAS = 30


@dataclass(frozen=True)
class CandidatoResolucao:
    """Uma entidade candidata a entrar num cluster de imóvel único -
    entrada pura pra `resolver_imoveis`, sem nenhuma dependência de banco."""

    entidade_id: uuid.UUID
    fonte_id: str
    impressao_digital: str
    primeira_observado_em: date


def resolver_imoveis(
    candidatos: list[CandidatoResolucao],
    janela_dias: int = JANELA_PADRAO_DIAS,
) -> list[ClusterImovel]:
    """Agrupa entidades (de uma ou mais fontes) em clusters de imóvel
    físico único, por impressao_digital coincidente dentro da janela de
    tempo - seção 8.1: "o mesmo imóvel físico não conta duas vezes" em
    métricas de volume (novos anúncios, estoque, rotação).

    Regra pura, sem I/O - a query que produz `candidatos` (entidades
    ativas no período, com sua primeira observação conhecida) é
    responsabilidade do pipeline, não desta função.

    Dentro de um mesmo impressao_digital, o agrupamento é por varredura
    ordenada por data: o cluster "ancora" na primeira entidade (mais
    antiga) e absorve qualquer outra cuja primeira observação caia dentro
    de `janela_dias` da âncora: passado esse prazo, uma nova âncora começa
    um cluster novo - mesmo fingerprint reaparecendo bem mais tarde é
    tratado como coincidência de atributos, não o mesmo evento de
    publicação (esse caso, quando é o mesmo imóvel republicado depois de
    ficar fora da oferta, é REANUNCIO - um evento, não uma resolução de
    fonte, ver domain/anuncio/regras.py)."""
    por_impressao: dict[str, list[CandidatoResolucao]] = {}
    for candidato in candidatos:
        por_impressao.setdefault(candidato.impressao_digital, []).append(candidato)

    clusters: list[ClusterImovel] = []
    for impressao_digital, grupo in por_impressao.items():
        clusters.extend(_agrupar_por_janela(impressao_digital, grupo, janela_dias))
    return clusters


def _agrupar_por_janela(
    impressao_digital: str,
    grupo: list[CandidatoResolucao],
    janela_dias: int,
) -> list[ClusterImovel]:
    ordenado = sorted(grupo, key=lambda c: c.primeira_observado_em)
    limite = timedelta(days=janela_dias)

    resultado: list[ClusterImovel] = []
    cluster_atual: list[CandidatoResolucao] = []
    ancora: date | None = None

    for candidato in ordenado:
        if ancora is None or candidato.primeira_observado_em - ancora <= limite:
            if ancora is None:
                ancora = candidato.primeira_observado_em
            cluster_atual.append(candidato)
        else:
            resultado.append(_fechar_cluster(impressao_digital, cluster_atual))
            cluster_atual = [candidato]
            ancora = candidato.primeira_observado_em

    if cluster_atual:
        resultado.append(_fechar_cluster(impressao_digital, cluster_atual))
    return resultado


def _fechar_cluster(impressao_digital: str, membros: list[CandidatoResolucao]) -> ClusterImovel:
    return ClusterImovel(
        entidade_ids=tuple(m.entidade_id for m in membros),
        fontes=tuple(m.fonte_id for m in membros),
        impressao_digital=impressao_digital,
    )
