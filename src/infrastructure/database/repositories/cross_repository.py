"""Leituras que cruzam comércio e anúncio sobre o substrato compartilhado
(checkpoint 12g, seção 3 do prompt de referência do Radar de Anúncios) -
vive fora de `commerce/`/pacotes de produto específico de propósito,
mesmo raciocínio de `analytics/features/cross/`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from analytics.features import PontoMensal
from infrastructure.database.orm.fato_evento_territorial import (
    FatoEventoTerritorial as FatoEventoTerritorialORM,
)
from infrastructure.database.orm.territorio import DimTerritorio
from infrastructure.database.repositories.geolocalizacao_repository import eventos_no_raio

TIPOS_EVENTO_NOVOS_ANUNCIOS = ("ANUNCIO_PUBLICADO", "REANUNCIO")


def _mes_seguinte(mes: date, n: int) -> date:
    total = (mes.year * 12 + (mes.month - 1)) + n
    return date(total // 12, total % 12 + 1, 1)


def series_novos_anuncios_todos_bairros(
    session: Session, *, mes_referencia: date, meses_historico: int
) -> dict[str, list[PontoMensal]]:
    """Série mensal de "novos anúncios" (`ANUNCIO_PUBLICADO`+`REANUNCIO`,
    mesma soma de `analytics.features.anuncio_termometro.
    contar_novos_anuncios`) por bairro, lida ao vivo de
    `fato_evento_territorial` (poucos milhares de linhas hoje, sem custo
    de materializar - mesmo raciocínio de `eventos_no_raio`).

    **Nunca zero-preenchida, ao contrário de `series_aberturas_todos_bairros`
    (comércio) - achado real do checkpoint 12g, corrigido antes de
    confiar em qualquer resultado**: zero-preencher aqui faria a série de
    anúncio (hoje com só ~1 mês real de profundidade) virar dezenas de
    meses "com dado" artificialmente, e a primeira execução real deste
    módulo contra o banco encontrou exatamente essa armadilha - uma
    correlação "significativa" espúria em lag=0, sustentada só pelo
    contraste entre um mês real e ~40 zeros fabricados, o tipo de
    correlação por acaso que a seção 3.1 pede pra evitar. Mês sem evento
    de anúncio aqui significa "não temos coleta cobrindo esse mês ainda"
    (mesma leitura de saldo em `feature_repository.
    consultar_saldo_mensal_todos_bairros`), nunca "zero anúncios
    publicados" - a ausência precisa remover o mês do cálculo de
    correlação (via `_alinhar_series`, que já só pareia meses presentes
    nas duas séries), não virar um zero que finge ser dado real."""
    evento = FatoEventoTerritorialORM
    mes_expr = cast(func.date_trunc("month", evento.data_evento), Date)
    stmt = (
        select(evento.territorio_id, mes_expr.label("mes"), func.count())
        .where(
            evento.entity_type == "anuncio_imovel",
            evento.event_type.in_(TIPOS_EVENTO_NOVOS_ANUNCIOS),
        )
        .group_by(evento.territorio_id, mes_expr)
    )
    inicio_janela = _mes_seguinte(mes_referencia, -meses_historico)
    resultado: dict[str, list[PontoMensal]] = {}
    for territorio_id, mes, n in session.execute(stmt):
        if territorio_id is None or not (inicio_janela <= mes <= mes_referencia):
            continue
        resultado.setdefault(territorio_id, []).append(PontoMensal(mes=mes, valor=float(n)))
    return resultado


def serie_novos_anuncios_cidade(
    session: Session, *, mes_referencia: date, meses_historico: int
) -> list[PontoMensal]:
    """Mesma série acima, somada pra cidade inteira - alimenta a etapa 1
    (agregado da cidade) da leitura cruzada, seção 3.1. Mesma disciplina
    de não zero-preencher (ver docstring de `series_novos_anuncios_todos_bairros`)."""
    evento = FatoEventoTerritorialORM
    mes_expr = cast(func.date_trunc("month", evento.data_evento), Date)
    stmt = (
        select(mes_expr.label("mes"), func.count())
        .where(
            evento.entity_type == "anuncio_imovel",
            evento.event_type.in_(TIPOS_EVENTO_NOVOS_ANUNCIOS),
        )
        .group_by(mes_expr)
    )
    inicio_janela = _mes_seguinte(mes_referencia, -meses_historico)
    return [
        PontoMensal(mes=mes, valor=float(n))
        for mes, n in session.execute(stmt)
        if inicio_janela <= mes <= mes_referencia
    ]


def resolver_bairro_do_ponto(session: Session, lat: float, lon: float) -> str | None:
    ponto = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    stmt = select(DimTerritorio.territorio_id).where(
        DimTerritorio.nivel == "bairro", func.ST_Contains(DimTerritorio.geometria, ponto)
    )
    return session.execute(stmt).scalar()


@dataclass(frozen=True)
class ResultadoCoincidenciaEspacial:
    """Seção 3.3 do prompt de referência ("coincidência espacial fina").
    Granularidades **deliberadamente diferentes** entre os dois lados,
    declaradas explicitamente (nunca escondidas atrás de um número só):
    comércio usa geolocalização real ponto-a-ponto (checkpoint 9) dentro
    de `raio_m`; anúncio ainda não tem geocodificação (nenhuma entidade
    `anuncio_imovel` tem `geolocalizacao_entidade` até este checkpoint -
    achado registrado no CLAUDE.md) - o número de anúncios é do bairro
    inteiro que contém o ponto buscado, não um raio de verdade. Reportar
    os dois juntos sob rótulos de granularidade diferentes é mais honesto
    que inventar um ponto aproximado pro anúncio."""

    aberturas_no_raio: int
    desaparecimentos_no_raio: int
    territorio_id_do_ponto: str | None
    novos_anuncios_no_bairro: int
    meses_considerados: int


def consultar_coincidencia_espacial(
    session: Session, *, lat: float, lon: float, raio_m: int, meses: int
) -> ResultadoCoincidenciaEspacial:
    hoje = date.today()
    corte = hoje - timedelta(days=30 * meses)

    eventos_comercio = eventos_no_raio(session, lat=lat, lon=lon, raio_m=raio_m)
    eventos_comercio_no_periodo = [e for e in eventos_comercio if e.data_evento >= corte]
    aberturas = sum(
        1 for e in eventos_comercio_no_periodo if e.event_type in ("ABERTURA_CONFIRMADA", "PRIMEIRA_OBSERVACAO")
    )
    desaparecimentos = sum(
        1 for e in eventos_comercio_no_periodo if e.event_type == "DESAPARECIMENTO"
    )

    territorio_id = resolver_bairro_do_ponto(session, lat, lon)
    novos_anuncios = 0
    if territorio_id is not None:
        evento = FatoEventoTerritorialORM
        stmt = select(func.count()).where(
            evento.entity_type == "anuncio_imovel",
            evento.event_type.in_(TIPOS_EVENTO_NOVOS_ANUNCIOS),
            evento.territorio_id == territorio_id,
            evento.data_evento >= corte,
        )
        novos_anuncios = session.execute(stmt).scalar() or 0

    return ResultadoCoincidenciaEspacial(
        aberturas_no_raio=aberturas,
        desaparecimentos_no_raio=desaparecimentos,
        territorio_id_do_ponto=territorio_id,
        novos_anuncios_no_bairro=novos_anuncios,
        meses_considerados=meses,
    )
