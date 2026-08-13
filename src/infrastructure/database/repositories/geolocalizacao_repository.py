from __future__ import annotations

import uuid
from dataclasses import dataclass

from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from domain.location import ResultadoGeolocalizacao
from infrastructure.database.orm.entidade import Entidade
from infrastructure.database.orm.geolocalizacao_entidade import GeolocalizacaoEntidade
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade
from infrastructure.geocoding.geocodebr_subprocess import EnderecoParaGeocodificar

FONTE_ID = "alvaras_smf"


@dataclass(frozen=True)
class EstabelecimentoNoRaio:
    entidade_id: uuid.UUID
    nome: str | None
    endereco: str | None
    cnae_principal: str | None
    territorio_id: str | None
    confianca: str
    distancia_m: float
    ponto: Point


@dataclass(frozen=True)
class PendenteSegundaPassagem:
    entidade_id: uuid.UUID
    logradouro: str | None
    numero: str | None
    cep: str | None
    bairro: str | None
    ponto_geocodebr: Point | None
    precisao_geocodebr: str | None


def _ultima_observacao_comercio_subquery():
    """Uma linha por entidade tipo_entidade='comercio' com o endereço da
    observação mais recente - endereço não muda entre observações da
    mesma entidade (mesma premissa dos dois pilotos), então geocodificar
    a partir da última observação conhecida é suficiente."""
    tabela = ObservacaoEntidade
    return (
        select(
            tabela.entidade_id,
            tabela.atributos["endereco"].astext.label("logradouro"),
            tabela.atributos["numero"].astext.label("numero"),
            tabela.atributos["cep"].astext.label("cep"),
            tabela.atributos["bairro"].astext.label("bairro"),
        )
        .distinct(tabela.entidade_id)
        .where(tabela.fonte_id == FONTE_ID)
        .order_by(tabela.entidade_id, tabela.observado_em.desc())
        .subquery()
    )


def entidades_comercio_pendentes(session: Session, limit: int | None = None) -> list[EnderecoParaGeocodificar]:
    """Entidades tipo_entidade='comercio' que ainda não têm linha em
    geolocalizacao_entidade - a cláusula NOT EXISTS é o que faz a Etapa 1
    do pipeline ser retomável sem parâmetro extra: rodar de novo só pega
    o que falta."""
    ultima_obs = _ultima_observacao_comercio_subquery()
    stmt = (
        select(
            ultima_obs.c.entidade_id,
            ultima_obs.c.logradouro,
            ultima_obs.c.numero,
            ultima_obs.c.cep,
            ultima_obs.c.bairro,
        )
        .join(Entidade, Entidade.entidade_id == ultima_obs.c.entidade_id)
        .where(
            Entidade.tipo_entidade == "comercio",
            ~select(GeolocalizacaoEntidade.entidade_id)
            .where(GeolocalizacaoEntidade.entidade_id == ultima_obs.c.entidade_id)
            .exists(),
        )
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    return [
        EnderecoParaGeocodificar(
            entidade_id=row.entidade_id,
            logradouro=row.logradouro or "",
            numero=row.numero or "",
            cep=row.cep or "",
            bairro=row.bairro or "",
        )
        for row in session.execute(stmt)
    ]


def entidades_pendentes_segunda_passagem(
    session: Session, limit: int | None = None
) -> list[PendenteSegundaPassagem]:
    """Entidades que a Etapa 1 marcou confianca='baixa' provisória e ainda
    não passaram pela Etapa 2 - fonte_secundaria IS NULL é o sinal de
    "ainda não tentamos a segunda passagem" (linhas que nunca precisaram
    dela têm confianca='alta', nunca 'baixa' - sem ambiguidade)."""
    ultima_obs = _ultima_observacao_comercio_subquery()
    stmt = (
        select(
            GeolocalizacaoEntidade.entidade_id,
            ultima_obs.c.logradouro,
            ultima_obs.c.numero,
            ultima_obs.c.cep,
            ultima_obs.c.bairro,
            GeolocalizacaoEntidade.ponto,
            GeolocalizacaoEntidade.precisao_geocodebr,
        )
        .join(ultima_obs, ultima_obs.c.entidade_id == GeolocalizacaoEntidade.entidade_id)
        .where(
            GeolocalizacaoEntidade.confianca == "baixa",
            GeolocalizacaoEntidade.fonte_secundaria.is_(None),
        )
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    resultado = []
    for row in session.execute(stmt):
        resultado.append(
            PendenteSegundaPassagem(
                entidade_id=row.entidade_id,
                logradouro=row.logradouro,
                numero=row.numero,
                cep=row.cep,
                bairro=row.bairro,
                ponto_geocodebr=to_shape(row.ponto) if row.ponto is not None else None,
                precisao_geocodebr=row.precisao_geocodebr,
            )
        )
    return resultado


def upsert_geolocalizacao(session: Session, resultados: list[ResultadoGeolocalizacao]) -> int:
    """Grava o resultado da reconciliação. ON CONFLICT DO UPDATE porque a
    Etapa 1 grava uma linha provisória (confianca='baixa',
    fonte_secundaria=None) que a Etapa 2 depois atualiza com o resultado
    final - mesmo entidade_id, duas gravações em momentos diferentes."""
    if not resultados:
        return 0

    agora_da_segunda_passagem = [r for r in resultados if r.fonte_secundaria is not None]
    ids_segunda_passagem = {r.entidade_id for r in agora_da_segunda_passagem}

    rows = [
        {
            "entidade_id": r.entidade_id,
            "ponto": from_shape(r.ponto, srid=4326) if r.ponto is not None else None,
            "confianca": r.confianca,
            "fonte_primaria": r.fonte_primaria,
            "fonte_secundaria": r.fonte_secundaria,
            "precisao_geocodebr": r.precisao_geocodebr,
            "distancia_desempate_m": r.distancia_desempate_m,
            "revisado_em": func.now() if r.entidade_id in ids_segunda_passagem else None,
        }
        for r in resultados
    ]

    stmt = insert(GeolocalizacaoEntidade).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[GeolocalizacaoEntidade.entidade_id],
        set_={
            "ponto": stmt.excluded.ponto,
            "confianca": stmt.excluded.confianca,
            "fonte_primaria": stmt.excluded.fonte_primaria,
            "fonte_secundaria": stmt.excluded.fonte_secundaria,
            "precisao_geocodebr": stmt.excluded.precisao_geocodebr,
            "distancia_desempate_m": stmt.excluded.distancia_desempate_m,
            "revisado_em": stmt.excluded.revisado_em,
        },
    )
    session.execute(stmt)
    return len(rows)


def contar_por_confianca(session: Session) -> dict[str, int]:
    stmt = select(GeolocalizacaoEntidade.confianca, func.count()).group_by(
        GeolocalizacaoEntidade.confianca
    )
    return {confianca: n for confianca, n in session.execute(stmt)}


def casos_discordancia_grave(session: Session, limiar_m: float = 1000.0) -> list[tuple[uuid.UUID, float]]:
    """Entidades onde geocodebr e Nominatim discordaram gravemente
    (distância > limiar_m) - pra investigação de padrão comum, pedida no
    checkpoint 9c."""
    stmt = select(
        GeolocalizacaoEntidade.entidade_id, GeolocalizacaoEntidade.distancia_desempate_m
    ).where(GeolocalizacaoEntidade.distancia_desempate_m > limiar_m)
    return [(row.entidade_id, float(row.distancia_desempate_m)) for row in session.execute(stmt)]


def buscar_no_raio(session: Session, lat: float, lon: float, raio_m: int) -> list[EstabelecimentoNoRaio]:
    """Todas as entidades tipo_entidade='comercio' com geolocalização
    dentro do raio, de qualquer confiança - filtrar por confiança (o
    corte alta/media vs. baixa da seção 5 do checkpoint 9) é
    responsabilidade de quem chama, não desta função. Não filtra por
    sinal de fechamento/DESAPARECIMENTO - está sob revisão separada
    (checkpoint 9, seção 7); conta toda entidade com observação válida no
    raio, independente disso.

    Entidades sem ponto (confianca aparentemente 'baixa' e geocodificação
    nunca resolvida) nunca aparecem aqui - ST_DWithin não tem como avaliar
    algo sem coordenada. Isso é esperado: são invisíveis pra qualquer
    busca por raio, não "excluídas desta busca" (essas duas coisas viram
    o mesmo dado no relatório, mas por caminhos diferentes).
    """
    tabela_obs = ObservacaoEntidade
    # concat_ws pula partes NULL sem deixar separador solto (ex.: sem
    # número informado -> "R. X - BAIRRO", não "R. X,  - BAIRRO") -
    # endereço de exibição pra lista de resultados (checkpoint 9g).
    logradouro_numero = func.concat_ws(
        ", ",
        tabela_obs.atributos["endereco"].astext,
        tabela_obs.atributos["numero"].astext,
    )
    endereco_expr = func.concat_ws(" - ", logradouro_numero, tabela_obs.atributos["bairro"].astext)

    ultima_obs = (
        select(
            tabela_obs.entidade_id,
            func.coalesce(
                tabela_obs.atributos["nome_fantasia"].astext,
                tabela_obs.atributos["nome_empresarial"].astext,
            ).label("nome"),
            endereco_expr.label("endereco"),
            tabela_obs.atributos["cnae_principal"].astext.label("cnae_principal"),
            tabela_obs.atributos["territorio_id"].astext.label("territorio_id"),
        )
        .distinct(tabela_obs.entidade_id)
        .where(tabela_obs.fonte_id == FONTE_ID)
        .order_by(tabela_obs.entidade_id, tabela_obs.observado_em.desc())
        .subquery()
    )

    ponto_busca = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    distancia_expr = func.ST_Distance(GeolocalizacaoEntidade.ponto, ponto_busca).label("distancia_m")

    stmt = (
        select(
            GeolocalizacaoEntidade.entidade_id,
            GeolocalizacaoEntidade.confianca,
            GeolocalizacaoEntidade.ponto,
            ultima_obs.c.nome,
            ultima_obs.c.endereco,
            ultima_obs.c.cnae_principal,
            ultima_obs.c.territorio_id,
            distancia_expr,
        )
        .join(ultima_obs, ultima_obs.c.entidade_id == GeolocalizacaoEntidade.entidade_id)
        .join(Entidade, Entidade.entidade_id == GeolocalizacaoEntidade.entidade_id)
        .where(
            Entidade.tipo_entidade == "comercio",
            GeolocalizacaoEntidade.ponto.isnot(None),
            func.ST_DWithin(GeolocalizacaoEntidade.ponto, ponto_busca, raio_m),
        )
    )

    resultado = []
    for row in session.execute(stmt):
        resultado.append(
            EstabelecimentoNoRaio(
                entidade_id=row.entidade_id,
                nome=row.nome,
                endereco=row.endereco,
                cnae_principal=row.cnae_principal,
                territorio_id=row.territorio_id,
                confianca=row.confianca,
                distancia_m=float(row.distancia_m),
                ponto=to_shape(row.ponto),
            )
        )
    return resultado
