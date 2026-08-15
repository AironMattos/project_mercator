from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from analytics.features.indicadores import MOTIVO_HISTORICO_INSUFICIENTE
from infrastructure.database.repositories.construcao_repository import (
    consultar_defasagem_mediana_por_bairro,
    consultar_metricas_construcao,
)
from infrastructure.database.repositories.contexto_bcb_repository import (
    consultar_ultimo_periodo as consultar_ultimo_periodo_bcb,
)
from infrastructure.database.repositories.contexto_censo_repository import (
    consultar_agregado_por_bairro,
)
from infrastructure.database.repositories.contexto_quintoandar_repository import (
    consultar_ultimo_periodo as consultar_ultimo_periodo_quintoandar,
)
from infrastructure.database.repositories.lote_cadastral_repository import contar_lotes
from infrastructure.database.repositories.observacao_repository import (
    contar_resolucao_territorio_por_fonte,
)
from infrastructure.database.repositories.pipeline_run_repository import (
    ultima_execucao_com_sucesso,
)
from infrastructure.database.repositories.valor_referencia_repository import (
    consultar_valor_venal_mediano_por_bairro,
)
from infrastructure.database.repositories.zoneamento_repository import listar_zoneamento

from dependencies import get_db
from schemas import (
    BcbIndicadorOut,
    CensoBairroOut,
    ContextoBcbOut,
    ContextoCensoOut,
    ContextoImoveisOut,
    ContextoQuintoandarOut,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    LoteCadastralQualidadeOut,
    MetricaConstrucaoOut,
    QualidadeDadosImoveisOut,
    QuintoandarSegmentoOut,
    ResolucaoTerritorioOut,
    ValorReferenciaBairroOut,
)

# Ano de referência do Censo usado neste checkpoint - único vintage
# disponível até uma nova aplicação decenal (ver
# domain.contexto.IndicadorCensitarioSetor).
ANO_CENSO = 2022

# Cada fonte real do Radar Imobiliário, para a data de última atualização
# em GET /imoveis/qualidade-dados - lista fechada e explícita (nunca
# descoberta em runtime), mesmo espírito da lista INDICADORES de
# bcb_mercado_imobiliario/connector.py.
FONTES_IMOVEIS = (
    "smu_alvara_construcao",
    "smu_cvco",
    "ippuc_pgv",
    "geocuritiba_lote_cadastral",
    "geocuritiba_zoneamento",
    "bcb_mercado_imobiliario",
    "quintoandar_indice_aluguel",
    "ibge_censo_setor",
)

MOTIVO_NAO_APLICAVEL_MODO_SERIE = "nao_aplicavel_no_modo_serie_mensal"

router = APIRouter(prefix="/imoveis")


@router.get("/construcao", response_model=list[MetricaConstrucaoOut])
def construcao(
    territorio_id: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    session: Session = Depends(get_db),
) -> list[MetricaConstrucaoOut]:
    """Sem territorio_id: agregado por bairro (período inteiro), com
    defasagem mediana alvará->CVCO anexada por bairro. Com territorio_id:
    série mensal daquele bairro, sem defasagem (amostra mensal pequena
    demais - ver PISO_MINIMO_PARES_DEFASAGEM)."""
    linhas = consultar_metricas_construcao(
        session, territorio_id=territorio_id, data_inicio=data_inicio, data_fim=data_fim
    )

    defasagem_por_bairro = {}
    if territorio_id is None:
        defasagem_por_bairro = {
            d["territorio_id"]: d for d in consultar_defasagem_mediana_por_bairro(session)
        }

    resultado = []
    for linha in linhas:
        if territorio_id is not None:
            # Modo série mensal: defasagem não se aplica por mês (amostra
            # mensal é sempre pequena demais) - motivo próprio, distinto
            # de "não temos pares suficientes ainda" (aplica-se ao modo
            # agregado abaixo), pra nunca deixar um campo None sem dizer
            # por quê (mesmo padrão de MOTIVO_NAO_APLICAVEL_SEM_TERRITORIO
            # em metricas.py).
            defasagem_mediana_dias = pares_alvara_cvco = None
            motivo = MOTIVO_NAO_APLICAVEL_MODO_SERIE
        else:
            defasagem = defasagem_por_bairro.get(linha["territorio_id"])
            if defasagem is None:
                # Bairro sem nenhum par ALVARA_APROVADO/OBRA_CONCLUIDA
                # observado ainda (0 pares) - mesmo motivo de amostra
                # insuficiente, contagem explícita em vez de None sem
                # contexto.
                defasagem_mediana_dias, pares_alvara_cvco = None, 0
                motivo = MOTIVO_HISTORICO_INSUFICIENTE
            else:
                defasagem_mediana_dias = defasagem["defasagem_mediana_dias"]
                pares_alvara_cvco = defasagem["pares"]
                motivo = defasagem["motivo_indisponivel"]

        resultado.append(
            MetricaConstrucaoOut(
                territorio_id=linha["territorio_id"],
                mes=linha["mes"],
                alvaras_aprovados=linha["alvaras_aprovados"],
                area_licenciada_m2=linha["area_licenciada_m2"],
                cvcos_concluidos=linha["cvcos_concluidos"],
                area_concluida_m2=linha["area_concluida_m2"],
                defasagem_mediana_dias=defasagem_mediana_dias,
                pares_alvara_cvco=pares_alvara_cvco,
                motivo_indisponivel_defasagem=motivo,
            )
        )
    return resultado


@router.get("/valor-referencia", response_model=list[ValorReferenciaBairroOut])
def valor_referencia(
    territorio_id: str | None = None, session: Session = Depends(get_db)
) -> list[ValorReferenciaBairroOut]:
    """Valor venal mediano de terreno (PGV) por bairro. Nunca "preço" -
    ver corolário da seção 1 do prompt de referência: valor venal é
    referência oficial de tributação, não preço de mercado."""
    linhas = consultar_valor_venal_mediano_por_bairro(session)
    if territorio_id is not None:
        linhas = [linha for linha in linhas if linha["territorio_id"] == territorio_id]
    return [ValorReferenciaBairroOut(**linha) for linha in linhas]


@router.get("/zoneamento", response_model=GeoJsonFeatureCollection)
def zoneamento(
    territorio_id: str | None = None, session: Session = Depends(get_db)
) -> GeoJsonFeatureCollection:
    """Parâmetros construtivos por polígono, com data_versao/
    data_atualizacao explícitos - mesmo padrão de GET /territorios."""
    registros = listar_zoneamento(session, territorio_id=territorio_id)
    features = [
        GeoJsonFeature(
            geometry=mapping(to_shape(z.geometria)) if z.geometria is not None else None,
            properties={
                "objectid_fonte": z.objectid_fonte,
                "territorio_id": z.territorio_id,
                "cd_zona": z.cd_zona,
                "sg_zona": z.sg_zona,
                "nm_zona": z.nm_zona,
                "nm_grupo": z.nm_grupo,
                "legislacao": z.legislacao,
                "data_versao": z.data_versao,
                "data_atualizacao": z.data_atualizacao,
                "fonte_id": z.fonte_id,
            },
        )
        for z in registros
    ]
    return GeoJsonFeatureCollection(features=features)


@router.get("/contexto", response_model=ContextoImoveisOut)
def contexto(session: Session = Depends(get_db)) -> ContextoImoveisOut:
    """Indicadores de contexto de mercado/demografia, cada um com sua
    granularidade real declarada no próprio corpo da resposta - nunca
    apresentar um dado de UF/cidade/setor agregado como se fosse de
    bairro sem dizer isso (seção 6 do prompt de referência)."""
    periodo_bcb, itens_bcb = consultar_ultimo_periodo_bcb(session)
    periodo_qa, itens_qa = consultar_ultimo_periodo_quintoandar(session)
    bairros_censo = consultar_agregado_por_bairro(session)

    return ContextoImoveisOut(
        bcb=ContextoBcbOut(
            uf="PR",
            periodo_referencia=periodo_bcb,
            indicadores=[BcbIndicadorOut(**item) for item in itens_bcb],
        ),
        quintoandar=ContextoQuintoandarOut(
            cidade="Curitiba",
            periodo_referencia=periodo_qa,
            segmentos=[QuintoandarSegmentoOut(**item) for item in itens_qa],
        ),
        censo=ContextoCensoOut(
            ano_referencia=ANO_CENSO,
            bairros=[CensoBairroOut(**item) for item in bairros_censo],
        ),
    )


@router.get("/qualidade-dados", response_model=QualidadeDadosImoveisOut)
def qualidade_dados(session: Session = Depends(get_db)) -> QualidadeDadosImoveisOut:
    """Indicadores objetivos de qualidade da base do Radar Imobiliário -
    mesmo princípio de GET /qualidade-dados (comércio, checkpoint 11a):
    contagens diretas, sem nota nem score composto."""
    total_alvara, resolvido_alvara = contar_resolucao_territorio_por_fonte(
        session, "smu_alvara_construcao"
    )
    total_cvco, resolvido_cvco = contar_resolucao_territorio_por_fonte(session, "smu_cvco")
    lotes = contar_lotes(session)
    valores_pgv = consultar_valor_venal_mediano_por_bairro(session)
    vigencia_pgv = valores_pgv[0]["vigencia_inicio"] if valores_pgv else None

    return QualidadeDadosImoveisOut(
        alvaras=ResolucaoTerritorioOut(
            total=total_alvara,
            com_territorio_resolvido=resolvido_alvara,
            pct_territorio_resolvido=(resolvido_alvara / total_alvara * 100) if total_alvara else 0.0,
        ),
        cvcos=ResolucaoTerritorioOut(
            total=total_cvco,
            com_territorio_resolvido=resolvido_cvco,
            pct_territorio_resolvido=(resolvido_cvco / total_cvco * 100) if total_cvco else 0.0,
        ),
        lote_cadastral=LoteCadastralQualidadeOut(**lotes),
        pgv_vigencia_inicio=vigencia_pgv,
        pgv_bairros_cobertos=len(valores_pgv),
        pgv_total_registros=sum(v["quantidade_registros"] for v in valores_pgv),
        ultima_atualizacao_por_fonte={
            fonte: ultima_execucao_com_sucesso(session, fonte) for fonte in FONTES_IMOVEIS
        },
    )
