"""Маршрути категорій"""

from typing import Annotated, Any

from fastapi import APIRouter, Path, Response

from labs.lab03 import repository
from labs.lab03.errors import CONFLICT, NOT_FOUND, translate_errors
from labs.lab03.schemas import CategoryCreate, CategoryRead

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=list[CategoryRead],
    summary="Список категорій",
    description="Усі категорії за зростанням id.",
)
def list_categories() -> list[dict[str, Any]]:
    with translate_errors():
        return repository.list_categories()


@router.post(
    "",
    response_model=CategoryRead,
    status_code=201,
    summary="Створити категорію",
    responses={**CONFLICT},
)
def create_category(payload: CategoryCreate) -> dict[str, Any]:
    with translate_errors():
        return repository.create_category(payload.name)


@router.delete(
    "/{category_id}",
    status_code=204,
    summary="Видалити порожню категорію",
    responses={**NOT_FOUND, **CONFLICT},
)
def delete_category(
        category_id: Annotated[int, Path(gt=0, description="Ідентифікатор категорії")],
) -> Response:
    with translate_errors():
        repository.delete_category(category_id)
    return Response(status_code=204)
