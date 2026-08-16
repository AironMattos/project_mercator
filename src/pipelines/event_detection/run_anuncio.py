"""Detecta eventos de anúncio (ANUNCIO_PUBLICADO, PRECO_ALTERADO,
ANUNCIO_ENCERRADO, REANUNCIO) comparando dois snapshots já ingeridos de
uma fonte de anúncio (apolar_anuncios ou chavesnamao_anuncios).

REANUNCIO (checkpoint 12e) cruza cada anúncio "novo" (sem observação
anterior nesta fonte) contra o histórico recente de ANUNCIO_ENCERRADO de
QUALQUER fonte, por impressao_digital (seção 5 do prompt de referência:
"o mesmo imóvel volta à oferta em janela curta") - é
inerentemente cross-fonte, ao contrário do resto da detecção aqui, que
compara duas observações da mesma entidade/fonte. A janela reaproveita
JANELA_PADRAO_DIAS (domain.anuncio.resolucao) - mesmo conceito de "tempo
razoável" da seção 8.1, sem introduzir um segundo número mágico.

Uso:
    python -m pipelines.event_detection.run_anuncio chavesnamao_anuncios 2026-08-08 2026-08-15
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from datetime import date, datetime, timezone

from domain.anuncio import ObservacaoAnuncio
from domain.anuncio.regras import (
    detectar_anuncio_encerrado,
    detectar_eventos_anuncio_par,
    detectar_reanuncio,
)
from domain.anuncio.resolucao import JANELA_PADRAO_DIAS
from domain.event import Evento
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.anuncio_repository import (
    buscar_encerrados_recentes_por_impressao,
    iter_grupos_por_entidade_anuncio,
)
from infrastructure.database.repositories.evento_repository import insert_eventos
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAMANHO_LOTE = 5000


def _gravar_lote(lote: list[Evento]) -> int:
    with get_session() as session:
        return insert_eventos(session, lote)


def _resolver_publicados_ou_reanuncios(
    candidatos: list[ObservacaoAnuncio], data_atual: date
) -> list[Evento]:
    """Decide, em lote (uma consulta pro grupo inteiro, não uma por
    anúncio), quais dos "anúncios novos" (sem observação anterior nesta
    fonte) são na verdade REANUNCIO de um imóvel que tinha
    ANUNCIO_ENCERRADO recente - o resto vira ANUNCIO_PUBLICADO normal.
    Mesma leitura "mais específica do mesmo fato, não um evento
    adicional" já usada em ABERTURA_CONFIRMADA/PRIMEIRA_OBSERVACAO
    (Radar de Comércio, checkpoint 3): nunca os dois eventos pro mesmo
    anúncio."""
    impressoes = {c.impressao_digital for c in candidatos}
    with get_session() as session:
        encerrados_recentes = buscar_encerrados_recentes_por_impressao(
            session, impressoes, JANELA_PADRAO_DIAS, antes_de=data_atual
        )

    eventos: list[Evento] = []
    for candidato in candidatos:
        correspondencia = encerrados_recentes.get(candidato.impressao_digital)
        if correspondencia is not None:
            entidade_anterior_id, preco_anterior = correspondencia
            eventos.append(detectar_reanuncio(candidato, entidade_anterior_id, preco_anterior))
        else:
            eventos.extend(detectar_eventos_anuncio_par(None, candidato))
    return eventos


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "uso: python -m pipelines.event_detection.run_anuncio "
            "<fonte_id> AAAA-MM-DD(anterior) AAAA-MM-DD(atual)"
        )
    fonte_id = sys.argv[1]
    data_anterior = date.fromisoformat(sys.argv[2])
    data_atual = date.fromisoformat(sys.argv[3])

    conector_id = f"event_detection_anuncio_{fonte_id}"
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    contagem: Counter[str] = Counter()
    lote: list[Evento] = []
    candidatos_sem_anterior: list[ObservacaoAnuncio] = []
    total_entidades = 0
    total_eventos = 0

    def _resolver_e_acumular() -> None:
        nonlocal lote, candidatos_sem_anterior
        eventos = _resolver_publicados_ou_reanuncios(candidatos_sem_anterior, data_atual)
        for evento in eventos:
            contagem[evento.event_type] += 1
        lote.extend(eventos)
        candidatos_sem_anterior = []

    try:
        with get_session() as session:
            for _entidade_id, observacoes in iter_grupos_por_entidade_anuncio(
                session, fonte_id, data_anterior, data_atual
            ):
                total_entidades += 1
                obs_anterior = next(
                    (o for o in observacoes if o.observado_em == data_anterior), None
                )
                obs_atual = next((o for o in observacoes if o.observado_em == data_atual), None)

                if obs_atual is None:
                    evento = detectar_anuncio_encerrado(obs_anterior, data_atual)
                    contagem[evento.event_type] += 1
                    lote.append(evento)
                elif obs_anterior is None:
                    candidatos_sem_anterior.append(obs_atual)
                else:
                    eventos = detectar_eventos_anuncio_par(obs_anterior, obs_atual)
                    for evento in eventos:
                        contagem[evento.event_type] += 1
                    lote.extend(eventos)

                if len(candidatos_sem_anterior) >= TAMANHO_LOTE:
                    _resolver_e_acumular()
                if len(lote) >= TAMANHO_LOTE:
                    total_eventos += _gravar_lote(lote)
                    lote = []

        if candidatos_sem_anterior:
            _resolver_e_acumular()
        if lote:
            total_eventos += _gravar_lote(lote)

        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=conector_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=total_entidades,
                    registros_gravados=total_eventos,
                    registros_com_falha=0,
                )
            )

        logger.info("entidades processadas: %d", total_entidades)
        logger.info("eventos gravados: %d", total_eventos)
        for tipo, n in contagem.most_common():
            logger.info("  %s: %d", tipo, n)
    except Exception:
        status = "falha"
        logger.exception("falha na detecção de evento de anúncio")
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=conector_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=total_entidades,
                    registros_gravados=total_eventos,
                    registros_com_falha=0,
                )
            )
        raise


if __name__ == "__main__":
    main()
