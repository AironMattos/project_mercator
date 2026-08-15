"""Orquestra os conectores smu_alvaras_construcao (Alvará da Construção +
CVCO): fetch -> normalize -> grava entidade/observação.

Detecção de evento (ALVARA_APROVADO/OBRA_CONCLUIDA) é uma etapa
separada - python -m pipelines.event_detection.run_obra - mesmo padrão
de separação já usado pelo comércio (run_alvaras_smf.py só ingere,
event_detection/run_comercio.py detecta evento lendo de volta do banco).
Isso evita um bug real de "observacao_id órfão": se a observação já
existisse (reprocessamento), o INSERT é ignorado (idempotência), mas o
objeto em memória teria um observacao_id novo que nunca foi persistido -
um evento construído a partir dele apontaria pra um id inexistente.

Uso:
    python -m pipelines.ingestion.run_smu_alvaras_construcao 2026 1 7
    (ano, mês inicial, mês final - todos opcionais, default: ano/mês
    corrente)
"""
from __future__ import annotations

import logging
import sys
from dataclasses import replace
from datetime import datetime, timezone

from infrastructure.connectors.smu_alvaras_construcao import (
    AlvaraConstrucaoConnector,
    CvcoConnector,
    RegistroObra,
)
from infrastructure.connectors.smu_alvaras_construcao.parsing import (
    normalizar_indicacao_fiscal,
    parse_tabela,
)
from infrastructure.database.orm.pipeline_run import PipelineRun
from infrastructure.database.repositories.entidade_repository import upsert_entidades
from infrastructure.database.repositories.lote_cadastral_repository import (
    territorio_id_por_indicacao_fiscal,
)
from infrastructure.database.repositories.observacao_repository import insert_observacoes
from infrastructure.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _territorio_lookup_para_snapshot(html: str) -> dict[str, str]:
    linhas = parse_tabela(html)
    indicacoes = {
        normalizar_indicacao_fiscal(l.get("indicacao_fiscal"))
        for l in linhas
        if l.get("indicacao_fiscal")
    }
    indicacoes.discard(None)
    with get_session() as session:
        return territorio_id_por_indicacao_fiscal(session, list(indicacoes))


def _gravar_registros(registros: list[RegistroObra]) -> int:
    with get_session() as session:
        mapa = upsert_entidades(session, [r.entidade for r in registros])

        observacoes = []
        for r in registros:
            entidade_id_real = mapa[(r.entidade.tipo_entidade, r.entidade.identificador_fonte)]
            observacao = r.observacao
            if entidade_id_real != observacao.entidade_id:
                observacao = replace(observacao, entidade_id=entidade_id_real)
            observacoes.append(observacao)

        return insert_observacoes(session, observacoes)


def _processar(connector, ano, mes_inicio, mes_fim) -> None:
    iniciado_em = datetime.now(timezone.utc)
    status = "sucesso"
    lidos = gravados = falhas = 0

    try:
        logger.info(
            "buscando relatório %s (%s a %s/%s)...",
            connector.fonte_id, mes_inicio, mes_fim, ano,
        )
        snapshot = connector.fetch(ano=ano, mes_inicio=mes_inicio, mes_fim=mes_fim)
        territorio_lookup = _territorio_lookup_para_snapshot(snapshot.conteudo["html"])
        logger.info(
            "%d indicações fiscais resolvidas contra lote_cadastral", len(territorio_lookup)
        )

        registros = list(
            connector.normalize(snapshot, territorio_id_por_indicacao_fiscal=territorio_lookup)
        )
        lidos = len(registros)
        gravados = _gravar_registros(registros)
        falhas = lidos - gravados
        resolvidos = sum(1 for r in registros if r.territorio_id)
        logger.info(
            "%s: %d lidos, %d observações gravadas, %d território resolvido (%.1f%%)",
            connector.fonte_id,
            lidos,
            gravados,
            resolvidos,
            100 * resolvidos / lidos if lidos else 0,
        )

        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
    except Exception:
        status = "falha"
        logger.exception("falha ao rodar o conector %s", connector.fonte_id)
        with get_session() as session:
            session.add(
                PipelineRun(
                    conector_id=connector.fonte_id,
                    iniciado_em=iniciado_em,
                    finalizado_em=datetime.now(timezone.utc),
                    status=status,
                    registros_lidos=lidos,
                    registros_gravados=gravados,
                    registros_com_falha=falhas,
                )
            )
        raise


def main() -> None:
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else None
    mes_inicio = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    mes_fim = int(sys.argv[3]) if len(sys.argv) > 3 else None

    _processar(AlvaraConstrucaoConnector(), ano, mes_inicio, mes_fim)
    _processar(CvcoConnector(), ano, mes_inicio, mes_fim)


if __name__ == "__main__":
    main()
