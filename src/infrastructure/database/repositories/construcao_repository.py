from __future__ import annotations

from datetime import date
from statistics import median

from sqlalchemy import Date, Numeric, case, cast, func, select
from sqlalchemy.orm import Session, aliased

from analytics.features.indicadores import MOTIVO_HISTORICO_INSUFICIENTE
from infrastructure.database.orm.fato_evento_territorial import FatoEventoTerritorial
from infrastructure.database.orm.observacao_entidade import ObservacaoEntidade

# Pares alvará->CVCO abaixo disso não sustentam uma mediana confiável -
# mesmo espírito do piso mínimo de volume do checkpoint 10d
# (BASELINE_MINIMO_RANKING em indicadores.py), aplicado aqui a uma
# contagem de pares observados, não a um baseline de série temporal.
PISO_MINIMO_PARES_DEFASAGEM = 3


def _area_numerica_expr():
    """Metragem Construída Lote (ALVARA_APROVADO) / Área Vistoria
    (OBRA_CONCLUIDA) - a fonte grava as duas como texto em formato
    decimal brasileiro ("111,40"), nunca numérico (checkpoint 11c/11e).
    """
    evento = FatoEventoTerritorial
    obs = ObservacaoEntidade
    campo = case(
        (
            evento.event_type == "ALVARA_APROVADO",
            obs.atributos["metragem_construida_lote"].astext,
        ),
        (
            evento.event_type == "OBRA_CONCLUIDA",
            obs.atributos["area_vistoria"].astext,
        ),
        else_=None,
    )
    campo_com_ponto = func.replace(campo, ",", ".")
    return cast(func.nullif(campo_com_ponto, ""), Numeric)


def consultar_metricas_construcao(
    session: Session,
    *,
    territorio_id: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[dict]:
    """Alvarás aprovados e CVCOs concluídos por bairro (+ mês, se
    territorio_id for informado), com área licenciada/concluída total -
    sempre em campos separados, nunca somados numa métrica única de
    "atividade construtiva" (ALVARA_APROVADO e OBRA_CONCLUIDA respondem
    perguntas diferentes: "onde vai mudar" vs. "onde já mudou" - seção 3.1
    do prompt de referência do Radar Imobiliário).

    Volume da fonte é pequeno (milhares de eventos, não centenas de
    milhares como comércio) - junta fato_evento_territorial com
    observacao_entidade ao vivo (via origem_observacoes[1], a única
    observação que sustenta um evento de obra - ver
    domain.event.regras.detectar_evento_obra), sem precisar de uma
    feature materializada como analytics.contagem_eventos faz para
    comércio (decisão de escopo, não descuido: reavaliar se o volume
    crescer a ponto de a query ao vivo ficar cara, mesmo critério que
    motivou materializar contagem_inicio_atividade no checkpoint 8).
    """
    evento = FatoEventoTerritorial
    obs = ObservacaoEntidade
    area = _area_numerica_expr()
    mes_expr = cast(func.date_trunc("month", evento.data_evento), Date)

    alvaras_aprovados = (
        func.count().filter(evento.event_type == "ALVARA_APROVADO").label("alvaras_aprovados")
    )
    area_licenciada = (
        func.sum(area).filter(evento.event_type == "ALVARA_APROVADO").label("area_licenciada_m2")
    )
    cvcos_concluidos = (
        func.count().filter(evento.event_type == "OBRA_CONCLUIDA").label("cvcos_concluidos")
    )
    area_concluida = (
        func.sum(area).filter(evento.event_type == "OBRA_CONCLUIDA").label("area_concluida_m2")
    )

    if territorio_id is not None:
        colunas = (
            evento.territorio_id,
            mes_expr.label("mes"),
            alvaras_aprovados,
            area_licenciada,
            cvcos_concluidos,
            area_concluida,
        )
        agrupar_por = (evento.territorio_id, mes_expr)
    else:
        colunas = (
            evento.territorio_id,
            alvaras_aprovados,
            area_licenciada,
            cvcos_concluidos,
            area_concluida,
        )
        agrupar_por = (evento.territorio_id,)

    stmt = (
        select(*colunas)
        .select_from(evento)
        .join(obs, obs.observacao_id == evento.origem_observacoes[1])
        .where(
            evento.entity_type == "obra",
            evento.event_type.in_(("ALVARA_APROVADO", "OBRA_CONCLUIDA")),
        )
    )
    if territorio_id is not None:
        stmt = stmt.where(evento.territorio_id == territorio_id)
    if data_inicio is not None:
        stmt = stmt.where(evento.data_evento >= data_inicio)
    if data_fim is not None:
        stmt = stmt.where(evento.data_evento <= data_fim)

    stmt = stmt.group_by(*agrupar_por).order_by(*agrupar_por)

    resultado = []
    for row in session.execute(stmt):
        resultado.append(
            {
                "territorio_id": row.territorio_id,
                "mes": row.mes if territorio_id is not None else None,
                "alvaras_aprovados": int(row.alvaras_aprovados or 0),
                "area_licenciada_m2": float(row.area_licenciada_m2 or 0),
                "cvcos_concluidos": int(row.cvcos_concluidos or 0),
                "area_concluida_m2": float(row.area_concluida_m2 or 0),
            }
        )
    return resultado


def consultar_defasagem_mediana_por_bairro(
    session: Session, *, territorio_id: str | None = None
) -> list[dict]:
    """Defasagem mediana (em dias) entre ALVARA_APROVADO e OBRA_CONCLUIDA
    do mesmo empreendimento - as duas entidades compartilham entidade_id
    porque identificador_fonte é o mesmo Número Alvará nos dois
    relatórios (checkpoint 11c). **Achado ao rodar contra dado real
    (checkpoint 11e)**: o campo "Data Vistoria" embutido no próprio
    relatório de Alvará (citado como atalho possível no checkpoint 11a)
    está vazio em 100% das 2.214 observações reais processadas - a
    defasagem só é calculável cruzando os dois eventos por entidade_id,
    nunca lendo a mesma linha do relatório de alvará.

    Piso mínimo de volume (mesmo espírito de BASELINE_MINIMO_RANKING,
    checkpoint 10d): bairros com menos de PISO_MINIMO_PARES_DEFASAGEM
    pares não têm mediana calculada - `pares` sempre visível na saída,
    nunca escondido, para quem consome saber o motivo.
    """
    a = aliased(FatoEventoTerritorial)
    c = aliased(FatoEventoTerritorial)
    bairro = func.coalesce(a.territorio_id, c.territorio_id)
    dias = c.data_evento - a.data_evento

    stmt = (
        select(bairro.label("territorio_id"), dias.label("dias"))
        .select_from(a)
        .join(c, c.entidade_id == a.entidade_id)
        .where(
            a.event_type == "ALVARA_APROVADO",
            c.event_type == "OBRA_CONCLUIDA",
            # Guarda de qualidade de dado: CVCO nunca precede o alvará -
            # se acontecer, é um problema na fonte, não um par válido.
            c.data_evento >= a.data_evento,
        )
    )
    if territorio_id is not None:
        stmt = stmt.where(bairro == territorio_id)

    pares_por_bairro: dict[str | None, list[int]] = {}
    for row in session.execute(stmt):
        pares_por_bairro.setdefault(row.territorio_id, []).append(row.dias)

    resultado = []
    for tid, dias_lista in pares_por_bairro.items():
        n = len(dias_lista)
        if n < PISO_MINIMO_PARES_DEFASAGEM:
            resultado.append(
                {
                    "territorio_id": tid,
                    "defasagem_mediana_dias": None,
                    "pares": n,
                    "motivo_indisponivel": MOTIVO_HISTORICO_INSUFICIENTE,
                }
            )
        else:
            resultado.append(
                {
                    "territorio_id": tid,
                    "defasagem_mediana_dias": median(dias_lista),
                    "pares": n,
                    "motivo_indisponivel": None,
                }
            )
    return resultado
