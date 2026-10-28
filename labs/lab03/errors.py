"""Перетворення помилок шару даних на HTTP-відповіді."""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from labs.lab03.repository import ConflictError, NotFoundError
from labs.lab03.schemas import ErrorRead

logger = logging.getLogger("lab03.api")

NOT_FOUND = {404: {"model": ErrorRead, "description": "Не знайдено"}}
CONFLICT = {409: {"model": ErrorRead, "description": "Конфлікт даних"}}


@contextmanager
def translate_errors() -> Iterator[None]:
    """Перетворити винятки репозиторію на HTTPException."""
    try:
        yield
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        logger.exception("Помилка бази даних: %s", exc)
        raise HTTPException(
            status_code=500, detail="Внутрішня помилка сервера"
        ) from exc
