from __future__ import annotations

import math
from collections import Counter
from datetime import date

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analytics.features.servico_indicadores import (
    indicador_aberturas_bairro,
    motivo_indisponivel_combinado,
    periodo_padrao_aberturas,
)
from commerce.cnae import normalizar_codigo_cnae
from infrastructure.database.repositories.categoria_repository import (
    categoria_id_por_codigo_cnae,
    listar_categorias,
)
from infrastructure.database.repositories.geolocalizacao_repository import (
    buscar_no_raio,
    eventos_no_raio,
)
from infrastructure.database.repositories.territorio_repository import (
    nomes_por_territorio_id,
)
from infrastructure.geocoding.nominatim import geocodificar

from dependencies import get_db
from schemas import (
    BuscaRaioOut,
    ComparacaoBairroRaioOut,
    EstabelecimentoRaioOut,
    IndicadorOut,
    PontoOut,
    PontoSerieRaioOut,
    QuebraCategoriaOut,
)

router = APIRouter()

CONFIANCAS_NA_CONTAGEM_PRINCIPAL = {"alta", "media"}
TIPOS_ABERTURA = {"PRIMEIRA_OBSERVACAO", "ABERTURA_CONFIRMADA"}

# Categorias mostradas em quebra_categoria - top N, mesmo padrão de
# quebra_categoria_bairro (limite=5).
LIMITE_QUEBRA_CATEGORIA = 5


def _mes(d: date) -> date:
    return date(d.year, d.month, 1)


@router.get("/busca-raio", response_model=BuscaRaioOut)
def busca_raio(
    endereco: str = Query(..., min_length=3),
    raio_m: int = Query(..., gt=0, le=5000),
    categoria_id: str | None = None,
    session: Session = Depends(get_db),
) -> BuscaRaioOut:
    """Geocodifica `endereco` ao vivo (Nominatim direto, uma chamada
    ocasional - não é o caminho do geocodebr em lote, ver checkpoint 9
    seção 4) e monta o perfil comercial do microterritório em `raio_m`
    metros (checkpoint 11d, "Investigação por endereço" evoluída): censo de
    estabelecimentos, densidade, aberturas/fechamentos/saldo/turnover do
    período coberto, composição por categoria, série temporal, e uma
    comparação com o bairro onde a maioria dos estabelecimentos do raio
    está. Não filtra por sinal de fechamento fora do critério acima (
    DESAPARECIMENTO está sob revisão separada) - conta toda entidade com
    observação válida no raio.
    """
    endereco_busca = (
        endereco if "curitiba" in endereco.lower() else f"{endereco}, Curitiba, PR, Brasil"
    )

    http = requests.Session()
    try:
        resultado_geocoding = geocodificar(endereco_busca, http)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"falha ao consultar serviço de geocodificação: {e}")

    if resultado_geocoding.status == "falha":
        raise HTTPException(status_code=404, detail=f"endereço não encontrado: {endereco!r}")
    if resultado_geocoding.status == "ambiguo":
        raise HTTPException(
            status_code=422,
            detail=f"endereço ambíguo, mais de um lugar plausível encontrado para {endereco!r} - tente ser mais específico",
        )

    ponto_busca = resultado_geocoding.ponto
    estabelecimentos = buscar_no_raio(session, lat=ponto_busca.y, lon=ponto_busca.x, raio_m=raio_m)

    categoria_por_codigo = categoria_id_por_codigo_cnae(session)

    principais: list[EstabelecimentoRaioOut] = []
    excluidos_baixa_confianca = 0
    contagem_territorio: Counter[str] = Counter()
    for e in estabelecimentos:
        codigo = normalizar_codigo_cnae(e.cnae_principal)
        categoria_do_estabelecimento = categoria_por_codigo.get(codigo)

        if categoria_id is not None and categoria_do_estabelecimento != categoria_id:
            continue

        if e.confianca not in CONFIANCAS_NA_CONTAGEM_PRINCIPAL:
            excluidos_baixa_confianca += 1
            continue

        if e.territorio_id:
            contagem_territorio[e.territorio_id] += 1

        principais.append(
            EstabelecimentoRaioOut(
                entidade_id=e.entidade_id,
                nome=e.nome,
                endereco=e.endereco,
                categoria_id=categoria_do_estabelecimento,
                territorio_id=e.territorio_id,
                distancia_m=e.distancia_m,
                confianca=e.confianca,
                ponto=PontoOut(lat=e.ponto.y, lon=e.ponto.x),
            )
        )

    principais.sort(key=lambda item: item.distancia_m)

    # Densidade não depende de geometria de bairro nenhuma - a área do
    # próprio círculo de busca é conhecida analiticamente (checkpoint 11d,
    # decisão de escopo: evita ter que calcular/armazenar área de bairro).
    area_km2 = math.pi * (raio_m / 1000) ** 2
    densidade_km2 = len(principais) / area_km2

    eventos = eventos_no_raio(session, lat=ponto_busca.y, lon=ponto_busca.x, raio_m=raio_m, categoria_id=categoria_id)
    aberturas = sum(1 for ev in eventos if ev.event_type in TIPOS_ABERTURA)
    fechamentos = sum(1 for ev in eventos if ev.event_type == "DESAPARECIMENTO")
    saldo = aberturas - fechamentos
    turnover = (aberturas + fechamentos) / len(principais) if principais else None

    contagem_categoria: Counter[str | None] = Counter(
        ev.categoria_id for ev in eventos if ev.event_type in TIPOS_ABERTURA
    )
    categorias_por_id = {c.categoria_id: c.nome for c in listar_categorias(session)}
    quebra_categoria = [
        QuebraCategoriaOut(
            categoria_id=cat_id,
            nome=categorias_por_id.get(cat_id, "(sem categoria)") if cat_id else "(sem categoria)",
            contagem=contagem,
        )
        for cat_id, contagem in contagem_categoria.most_common(LIMITE_QUEBRA_CATEGORIA)
    ]

    contagem_mes: Counter[date] = Counter()
    fechamentos_mes: Counter[date] = Counter()
    for ev in eventos:
        mes = _mes(ev.data_evento)
        if ev.event_type in TIPOS_ABERTURA:
            contagem_mes[mes] += 1
        else:
            fechamentos_mes[mes] += 1
    meses = sorted(set(contagem_mes) | set(fechamentos_mes))
    serie_temporal = [
        PontoSerieRaioOut(mes=mes, aberturas=contagem_mes.get(mes, 0), fechamentos=fechamentos_mes.get(mes, 0))
        for mes in meses
    ]

    comparacao_bairro = None
    if contagem_territorio:
        territorio_majoritario, _n = contagem_territorio.most_common(1)[0]
        nomes = nomes_por_territorio_id(session)
        nome_bairro = nomes.get(territorio_majoritario)
        if nome_bairro is not None:
            mes_referencia = periodo_padrao_aberturas(session)
            baseline_aberturas, tendencia_aberturas = indicador_aberturas_bairro(
                session, territorio_id=territorio_majoritario, categoria_id=categoria_id, mes_referencia=mes_referencia
            )
            comparacao_bairro = ComparacaoBairroRaioOut(
                territorio_id=territorio_majoritario,
                nome=nome_bairro,
                aberturas=IndicadorOut(
                    valor_atual=baseline_aberturas.valor_atual,
                    baseline=baseline_aberturas.baseline,
                    variacao_pct=baseline_aberturas.variacao_pct,
                    tendencia=tendencia_aberturas.classificacao,
                    motivo_indisponivel=motivo_indisponivel_combinado(baseline_aberturas, tendencia_aberturas),
                ),
            )

    return BuscaRaioOut(
        endereco_buscado=endereco,
        ponto_busca=PontoOut(lat=ponto_busca.y, lon=ponto_busca.x),
        raio_m=raio_m,
        categoria_id=categoria_id,
        total=len(principais),
        estabelecimentos=principais,
        excluidos_baixa_confianca=excluidos_baixa_confianca,
        densidade_km2=densidade_km2,
        aberturas=aberturas,
        fechamentos=fechamentos,
        saldo=saldo,
        turnover=turnover,
        quebra_categoria=quebra_categoria,
        serie_temporal=serie_temporal,
        comparacao_bairro=comparacao_bairro,
    )
