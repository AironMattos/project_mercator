from __future__ import annotations

import uuid
from datetime import date

from domain.anuncio.models import ObservacaoAnuncio
from domain.event.models import Evento

ENTITY_TYPE_ANUNCIO = "anuncio_imovel"


def detectar_eventos_anuncio_par(
    anterior: ObservacaoAnuncio | None,
    atual: ObservacaoAnuncio,
) -> list[Evento]:
    """Dado o par (observação anterior do mesmo anúncio, ou None; atual),
    decide quais eventos resultam. Regra pura, mesma forma de
    detectar_eventos_par (domain/event/regras.py) para comércio, mas
    especializada em ObservacaoAnuncio (tabela dedicada, não o
    entidade/atributos genérico).

    Sem `anterior`: é a primeira vez que vemos este anúncio em qualquer
    snapshot já processado -> ANUNCIO_PUBLICADO, confiança alta (ao
    contrário do comércio, não há ambiguidade "abertura confirmada vs.
    primeira observação" aqui - o próprio anúncio é a prova de que a
    oferta foi publicada, não uma inferência sobre uma data de início de
    atividade separada).

    Com `anterior`: PRECO_ALTERADO quando o preço pedido mudou -
    confiança alta (o preço é um fato direto do anúncio, não uma
    inferência), com a direção e a variação percentual no payload."""
    if anterior is None:
        return [
            Evento(
                entity_type=ENTITY_TYPE_ANUNCIO,
                event_type="ANUNCIO_PUBLICADO",
                entidade_id=atual.entidade_id,
                territorio_id=atual.territorio_id,
                data_evento=atual.observado_em,
                confianca="alta",
                origem_observacoes=(atual.observacao_id,),
                payload={"operacao": atual.operacao, "tipologia": atual.tipologia},
            )
        ]

    eventos: list[Evento] = []
    if (
        anterior.preco is not None
        and atual.preco is not None
        and anterior.preco != atual.preco
    ):
        variacao_pct = (atual.preco - anterior.preco) / anterior.preco
        eventos.append(
            Evento(
                entity_type=ENTITY_TYPE_ANUNCIO,
                event_type="PRECO_ALTERADO",
                entidade_id=atual.entidade_id,
                territorio_id=atual.territorio_id,
                data_evento=atual.observado_em,
                confianca="alta",
                origem_observacoes=(anterior.observacao_id, atual.observacao_id),
                payload={
                    "preco_anterior": anterior.preco,
                    "preco_atual": atual.preco,
                    "variacao_pct": variacao_pct,
                    "direcao": "aumento" if variacao_pct > 0 else "reducao",
                },
            )
        )
    return eventos


def detectar_anuncio_encerrado(
    ultima_observacao_conhecida: ObservacaoAnuncio,
    data_snapshot_atual: date,
) -> Evento:
    """Constrói o evento de anúncio encerrado - o anúncio não aparece mais
    no snapshot atual. Confiança sempre "baixa": um anúncio some da oferta
    por venda, aluguel, retirada, expiração ou republicação sob outro
    identificador - indistinguíveis de fora (seção 1 do prompt de
    referência: nunca chamar isso de "venda"). Quem decide QUE o anúncio
    desapareceu é o pipeline (diferença de conjunto entre dois snapshots),
    esta função só monta o Evento a partir dessa premissa."""
    return Evento(
        entity_type=ENTITY_TYPE_ANUNCIO,
        event_type="ANUNCIO_ENCERRADO",
        entidade_id=ultima_observacao_conhecida.entidade_id,
        territorio_id=ultima_observacao_conhecida.territorio_id,
        data_evento=data_snapshot_atual,
        confianca="baixa",
        origem_observacoes=(ultima_observacao_conhecida.observacao_id,),
        payload={
            "operacao": ultima_observacao_conhecida.operacao,
            "tipologia": ultima_observacao_conhecida.tipologia,
            "ultimo_preco": ultima_observacao_conhecida.preco,
        },
    )


def detectar_reanuncio(
    nova_observacao: ObservacaoAnuncio,
    entidade_anterior_id: uuid.UUID,
    preco_anterior: float | None,
) -> Evento:
    """Constrói REANUNCIO - o pipeline já identificou (por
    impressao_digital coincidente, ver domain/anuncio/resolucao.py) que
    este é um imóvel que tinha um anúncio ANUNCIO_ENCERRADO recente e
    voltou à oferta como uma entidade nova. Confiança "media": a
    coincidência de impressao_digital é um indício forte, não uma
    identidade certa (dois imóveis genuinamente diferentes podem colidir
    na impressão digital, ver limitação documentada em
    impressao_digital.py). `variacao_pct` no payload fica None quando o
    preço anterior não é conhecido - nunca vira 0 nem é omitido, seção 5
    do prompt de referência mede especificamente reanúncio COM preço
    maior, então essa informação precisa estar sempre visível quando
    existir."""
    variacao_pct = (
        (nova_observacao.preco - preco_anterior) / preco_anterior
        if preco_anterior and nova_observacao.preco is not None
        else None
    )
    return Evento(
        entity_type=ENTITY_TYPE_ANUNCIO,
        event_type="REANUNCIO",
        entidade_id=nova_observacao.entidade_id,
        territorio_id=nova_observacao.territorio_id,
        data_evento=nova_observacao.observado_em,
        confianca="media",
        origem_observacoes=(nova_observacao.observacao_id,),
        payload={
            "entidade_anterior_id": str(entidade_anterior_id),
            "preco_anterior": preco_anterior,
            "preco_atual": nova_observacao.preco,
            "variacao_pct": variacao_pct,
        },
    )
