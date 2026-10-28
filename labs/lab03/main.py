"""FastAPI-застосунок ЛР №3"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from labs.lab03.config import APP_DESCRIPTION, APP_TITLE
from labs.lab03.database import initialize_database
from labs.lab03.routers import categories, records
from labs.lab03.schemas import StudentRead
from shared import student

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Створити відсутні таблиці під час запуску (дані не змінюються)."""
    initialize_database()
    yield


app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, lifespan=lifespan)
app.include_router(categories.router)
app.include_router(records.router)


@app.get("/ping", summary="Перевірка доступності")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/student", response_model=StudentRead, summary="Дані студента")
def get_student() -> StudentRead:
    return StudentRead(
        student_name=student.STUDENT_NAME,
        group_name=student.GROUP_NAME,
        variant_number=student.VARIANT_NUMBER,
    )