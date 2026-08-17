from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    anuncios,
    bairros,
    busca_raio,
    categorias,
    imoveis,
    metodologia,
    metricas,
    ranking,
    sinais,
    territorios,
)

load_dotenv()

_DEFAULT_ORIGINS = ["http://localhost:3000"]


def _cors_origins() -> list[str]:
    """CORS_ORIGINS: lista separada por vírgula. Sempre inclui localhost:3000
    (dev), mas em produção precisa também da URL do Vercel - configurar via
    variável de ambiente na plataforma de deploy, não hardcoded aqui.
    """
    origins_env = os.environ.get("CORS_ORIGINS", "")
    origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    for origem in _DEFAULT_ORIGINS:
        if origem not in origins:
            origins.append(origem)
    return origins


# A partir do checkpoint 11e (Radar Imobiliário, /imoveis/...) esta API
# serve os dois produtos - título atualizado de "Radar de Comércio API"
# pra não sugerir que /imoveis é secundário/fora do escopo.
app = FastAPI(title="Mercator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(territorios.router)
app.include_router(categorias.router)
app.include_router(metricas.router)
app.include_router(ranking.router)
app.include_router(bairros.router)
app.include_router(busca_raio.router)
app.include_router(metodologia.router)
app.include_router(sinais.router)
app.include_router(imoveis.router)
app.include_router(anuncios.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
