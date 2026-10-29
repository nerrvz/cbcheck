"""Параметризовані SQL-запити (модуль не залежить від FastAPI)."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from labs.lab03.database import get_connection

RECORD_COLUMNS = ("code", "title", "category_id", "value", "status")
RECORD_SELECT = (
    "SELECT r.id, r.code, r.title, r.category_id, "
    "c.name AS category_name, r.value, r.status "
    "FROM records AS r JOIN categories AS c ON c.id = r.category_id"
)
INSERT_RECORD = (
    "INSERT INTO records (code, title, category_id, value, status) "
    "VALUES (?, ?, ?, ?, ?)"
)


class RepositoryError(Exception):
    """Базова помилка шару доступу до даних."""


class NotFoundError(RepositoryError):
    """Запис або категорію не знайдено."""


class ConflictError(RepositoryError):
    """Дублікат унікального значення або порушення зв'язку."""


def _connect() -> sqlite3.Connection:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    return connection


def _conflict(exc: sqlite3.IntegrityError) -> ConflictError:
    """Перетворити IntegrityError на зрозумілу помилку без SQL-деталей."""
    text = str(exc)
    if "records.code" in text:
        return ConflictError("Запис із таким code вже існує")
    if "categories.name" in text:
        return ConflictError("Категорія з такою назвою вже існує")
    return ConflictError("Порушено обмеження цілісності даних")


def _values(data: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(data[column] for column in RECORD_COLUMNS)


def _fetch_record(connection: sqlite3.Connection, record_id: int) -> dict | None:
    row = connection.execute(
        RECORD_SELECT + " WHERE r.id = ?", (record_id,)
    ).fetchone()
    return dict(row) if row else None


def _require_category(connection: sqlite3.Connection, category_id: int) -> None:
    row = connection.execute(
        "SELECT 1 FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Категорію не знайдено")




def create_category(name: str) -> dict[str, Any]:
    """Створити категорію"""
    with closing(_connect()) as connection:
        try:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO categories (name) VALUES (?)", (name,)
                )
        except sqlite3.IntegrityError as exc:
            raise _conflict(exc) from exc
        return {"id": cursor.lastrowid, "name": name}


def list_categories() -> list[dict[str, Any]]:
    """Список категорій за зростанням id"""
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT id, name FROM categories ORDER BY id ASC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_category(category_id: int) -> None:
    """Видалити порожню категорію"""
    with closing(_connect()) as connection:
        try:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM categories WHERE id = ?", (category_id,)
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                "Категорія містить записи й не може бути видалена"
            ) from exc
        if cursor.rowcount == 0:
            raise NotFoundError("Категорію не знайдено")




def create_record(data: dict[str, Any]) -> dict[str, Any]:
    """Додати запис і повернути його з category_name"""
    with closing(_connect()) as connection:
        try:
            with connection:
                _require_category(connection, data["category_id"])
                cursor = connection.execute(INSERT_RECORD, _values(data))
                record = _fetch_record(connection, cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise _conflict(exc) from exc
        return record


def get_record(record_id: int) -> dict[str, Any]:
    """Отримати запис за id"""
    with closing(_connect()) as connection:
        record = _fetch_record(connection, record_id)
        if record is None:
            raise NotFoundError("Запис не знайдено")
        return record


def list_records(
        *,
        category_id: int | None = None,
        status: str | None = None,
        min_value: float | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
) -> list[dict[str, Any]]:
    """Список записів з фільтрами (AND) і поділом на сторінки"""
    conditions: list[str] = []
    params: list[Any] = []
    if category_id is not None:
        conditions.append("r.category_id = ?")
        params.append(category_id)
    if status is not None:
        conditions.append("r.status = ?")
        params.append(status)
    if min_value is not None:
        conditions.append("r.value >= ?")
        params.append(min_value)
    if q is not None:
        conditions.append("instr(r.title, ?) > 0")
        params.append(q)

    sql = RECORD_SELECT
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY r.id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with closing(_connect()) as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def replace_record(record_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Повна заміна змінюваних полів; id не змінюється"""
    with closing(_connect()) as connection:
        try:
            with connection:
                if _fetch_record(connection, record_id) is None:
                    raise NotFoundError("Запис не знайдено")
                _require_category(connection, data["category_id"])
                cursor = connection.execute(
                    "UPDATE records SET code = ?, title = ?, category_id = ?, "
                    "value = ?, status = ? WHERE id = ?",
                    (*_values(data), record_id),
                )
                if cursor.rowcount == 0:
                    raise NotFoundError("Запис не знайдено")
                record = _fetch_record(connection, record_id)
        except sqlite3.IntegrityError as exc:
            raise _conflict(exc) from exc
        return record


def delete_record(record_id: int) -> None:
    """Видалити запис"""
    with closing(_connect()) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM records WHERE id = ?", (record_id,)
            )
        if cursor.rowcount == 0:
            raise NotFoundError("Запис не знайдено")


def create_records_bulk(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Атомарно додати пакет записів"""
    with closing(_connect()) as connection:
        try:
            with connection:
                for category_id in sorted({item["category_id"] for item in items}):
                    _require_category(connection, category_id)
                new_ids = [
                    connection.execute(INSERT_RECORD, _values(item)).lastrowid
                    for item in items
                ]
                return [_fetch_record(connection, new_id) for new_id in new_ids]
        except sqlite3.IntegrityError as exc:
            raise _conflict(exc) from exc

