from __future__ import annotations

from datetime import date

from domain.event.models import Evento
from domain.observation import ObservacaoEntidade


def detectar_eventos_par(
    anterior: ObservacaoEntidade | None,
    atual: ObservacaoEntidade,
    entity_type: str,
) -> list[Evento]:
    """Dado o par (observação anterior da mesma entidade, ou None; observação
    atual) decide quais eventos resultam. Regra pura - não sabe nada de
    banco, testável sem I/O.

    Quando `anterior` é None, a entidade está aparecendo pela primeira vez
    em qualquer snapshot que já processamos. Duas leituras são possíveis
    para esse mesmo fato:
    - se o INICIO_ATIVIDADE reportado cai no mês imediatamente anterior ao
      deste snapshot, temos um sinal forte de abertura genuína ->
      ABERTURA_CONFIRMADA (confiança alta). O snapshot é datado no dia 1º
      do mês (ex.: 2026-08-01) mas reflete o estado consolidado até o fim
      do mês ANTERIOR (julho) - confirmado empiricamente: ao comparar
      2026-07-01 com 2026-08-01, as entidades que aparecem pela primeira
      vez em agosto têm INICIO_ATIVIDADE concentrado em julho, não agosto;
    - caso contrário (negócio mais antigo que só agora entrou no nosso
      radar, ou sem INICIO_ATIVIDADE informado), não dá pra confirmar
      quando abriu -> PRIMEIRA_OBSERVACAO (confiança baixa).
    As duas são mutuamente exclusivas: nunca emitimos as duas para a mesma
    observação, já que ABERTURA_CONFIRMADA é uma leitura mais específica e
    mais confiável do mesmo fato (primeira aparição).
    """
    territorio_id = atual.atributos.get("territorio_id")

    if anterior is None:
        if _abriu_no_periodo_do_snapshot(atual):
            return [
                Evento(
                    entity_type=entity_type,
                    event_type="ABERTURA_CONFIRMADA",
                    entidade_id=atual.entidade_id,
                    territorio_id=territorio_id,
                    data_evento=atual.observado_em,
                    confianca="alta",
                    origem_observacoes=(atual.observacao_id,),
                )
            ]
        return [
            Evento(
                entity_type=entity_type,
                event_type="PRIMEIRA_OBSERVACAO",
                entidade_id=atual.entidade_id,
                territorio_id=territorio_id,
                data_evento=atual.observado_em,
                confianca="baixa",
                origem_observacoes=(atual.observacao_id,),
            )
        ]

    eventos: list[Evento] = []
    cnae_anterior = anterior.atributos.get("cnae_principal")
    cnae_atual = atual.atributos.get("cnae_principal")
    if cnae_anterior and cnae_atual and cnae_anterior != cnae_atual:
        eventos.append(
            Evento(
                entity_type=entity_type,
                event_type="MUDANCA_CATEGORIA",
                entidade_id=atual.entidade_id,
                territorio_id=territorio_id,
                data_evento=atual.observado_em,
                confianca="media",
                origem_observacoes=(anterior.observacao_id, atual.observacao_id),
                payload={"cnae_anterior": cnae_anterior, "cnae_atual": cnae_atual},
            )
        )
    return eventos


def detectar_desaparecimento(
    ultima_observacao_conhecida: ObservacaoEntidade,
    entity_type: str,
    data_snapshot_atual: date,
) -> Evento:
    """Constrói o evento de desaparecimento. Quem decide QUE a entidade
    desapareceu é o pipeline (comparando o conjunto de entidades do
    snapshot anterior contra o do snapshot atual) - esta função só sabe
    montar o Evento a partir dessa premissa já estabelecida.
    """
    return Evento(
        entity_type=entity_type,
        event_type="DESAPARECIMENTO",
        entidade_id=ultima_observacao_conhecida.entidade_id,
        territorio_id=ultima_observacao_conhecida.atributos.get("territorio_id"),
        data_evento=data_snapshot_atual,
        confianca="baixa",
        origem_observacoes=(ultima_observacao_conhecida.observacao_id,),
    )


_CAMPO_DATA_POR_EVENTO_OBRA = {
    "ALVARA_APROVADO": "data_criacao_alvara",
    "OBRA_CONCLUIDA": "data_vistoria",
}


def detectar_evento_obra(
    observacao: ObservacaoEntidade, event_type: str, entity_type: str = "obra"
) -> Evento | None:
    """Deriva um evento de obra (ALVARA_APROVADO ou OBRA_CONCLUIDA) direto
    de uma única observação - diferente do comércio, que precisa comparar
    dois snapshots (anterior/atual) para inferir o que aconteceu. Aqui não
    há inferência: o relatório de origem (SMU) já informa a data exata do
    fato (Data Criação Alvará / Data Vistoria) linha a linha, então a
    observação sozinha já é prova suficiente - por isso confiança é
    sempre "alta" e origem_observacoes aponta só para essa observação.

    event_type decide qual campo de data usar - quem chama sabe qual
    relatório gerou a observação (smu_alvara_construcao ou smu_cvco) e
    pede o evento correspondente; a função não adivinha pelo fonte_id.

    Devolve None quando a data relevante não está presente (ex.: CVCO sem
    Data Vistoria preenchida) - sem essa data não há o que datar o
    evento, e um evento sem data não é uma opção válida no domínio.
    """
    campo_data = _CAMPO_DATA_POR_EVENTO_OBRA.get(event_type)
    if campo_data is None:
        raise ValueError(
            f"event_type não suportado para obra: {event_type!r}. "
            f"Deve ser um de {sorted(_CAMPO_DATA_POR_EVENTO_OBRA)}"
        )

    data_bruta = observacao.atributos.get(campo_data)
    if not data_bruta:
        return None

    return Evento(
        entity_type=entity_type,
        event_type=event_type,
        entidade_id=observacao.entidade_id,
        territorio_id=observacao.atributos.get("territorio_id"),
        data_evento=date.fromisoformat(data_bruta),
        confianca="alta",
        origem_observacoes=(observacao.observacao_id,),
    )


def _abriu_no_periodo_do_snapshot(observacao: ObservacaoEntidade) -> bool:
    inicio = observacao.atributos.get("inicio_atividade")
    if not inicio:
        return False
    inicio_data = date.fromisoformat(inicio)
    mes_coberto = _mes_anterior(observacao.observado_em)
    return (inicio_data.year, inicio_data.month) == mes_coberto


def _mes_anterior(referencia: date) -> tuple[int, int]:
    if referencia.month == 1:
        return referencia.year - 1, 12
    return referencia.year, referencia.month - 1
