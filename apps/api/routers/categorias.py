from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from infrastructure.database.repositories.categoria_repository import (
    listar_categorias,
)

from dependencies import get_db
from schemas import CategoriaOut

router = APIRouter()


@router.get("/categorias", response_model=list[CategoriaOut])
def listar(session: Session = Depends(get_db)) -> list[CategoriaOut]:
    return [
        CategoriaOut(categoria_id=c.categoria_id, nome=c.nome)
        for c in listar_categorias(session)
    ]
