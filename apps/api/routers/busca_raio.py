from __future__ import annotations

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from commerce.cnae import normalizar_codigo_cnae
from infrastructure.database.repositories.categoria_repository import categoria_id_por_codigo_cnae
from infrastructure.database.repositories.geolocalizacao_repository import buscar_no_raio
from infrastructure.geocoding.nominatim import geocodificar

from dependencies import get_db
from schemas import BuscaRaioOut, EstabelecimentoRaioOut, PontoOut

router = APIRouter()

CONFIANCAS_NA_CONTAGEM_PRINCIPAL = {"alta", "media"}


@router.get("/busca-raio", response_model=BuscaRaioOut)
def busca_raio(
    endereco: str = Query(..., min_length=3),
    raio_m: int = Query(..., gt=0, le=5000),
    categoria_id: str | None = None,
    session: Session = Depends(get_db),
) -> BuscaRaioOut:
    """Geocodifica `endereco` ao vivo (Nominatim direto, uma chamada
    ocasional - não é o caminho do geocodebr em lote, ver checkpoint 9
    seção 4) e lista estabelecimentos em `raio_m` metros. Não filtra por
    sinal de fechamento (DESAPARECIMENTO está sob revisão separada) -
    conta toda entidade com observação válida no raio.
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
    for e in estabelecimentos:
        codigo = normalizar_codigo_cnae(e.cnae_principal)
        categoria_do_estabelecimento = categoria_por_codigo.get(codigo)

        if categoria_id is not None and categoria_do_estabelecimento != categoria_id:
            continue

        if e.confianca not in CONFIANCAS_NA_CONTAGEM_PRINCIPAL:
            excluidos_baixa_confianca += 1
            continue

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

    return BuscaRaioOut(
        endereco_buscado=endereco,
        ponto_busca=PontoOut(lat=ponto_busca.y, lon=ponto_busca.x),
        raio_m=raio_m,
        categoria_id=categoria_id,
        total=len(principais),
        estabelecimentos=principais,
        excluidos_baixa_confianca=excluidos_baixa_confianca,
    )
