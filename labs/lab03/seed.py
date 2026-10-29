from __future__ import annotations

import json
import logging
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from labs.lab03.config import VALUE_MAX, VALUE_MIN
from labs.lab03.database import get_connection, initialize_database

logger = logging.getLogger("lab03.seed")

SEED_PATH = Path(__file__).resolve().parent / "data" / "seed.json"
STATUSES = {"new", "in_progress", "done"}
RECORD_KEYS = {"code", "title", "category_id", "value", "status"}


class SeedError(Exception):
    """Помилка початкових даних або заповнення бази"""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_text(value: object, low: int, high: int) -> bool:
    return isinstance(value, str) and low <= len(value.strip()) <= high


def _check_category(index: int, item: object) -> None:
    where = f"categories[{index}]"
    if not isinstance(item, dict) or set(item) != {"id", "name"}:
        raise SeedError(f"{where}: очікується об'єкт з полями id та name")
    if not _is_int(item["id"]) or item["id"] <= 0:
        raise SeedError(f"{where}: id має бути додатним цілим числом")
    if not _is_text(item["name"], 2, 40):
        raise SeedError(f"{where}: name має містити 2-40 символів")


def _check_record(index: int, item: object, category_ids: set[int]) -> None:
    where = f"records[{index}]"
    if not isinstance(item, dict) or set(item) != RECORD_KEYS:
        raise SeedError(f"{where}: очікуються поля {sorted(RECORD_KEYS)}")
    if not _is_text(item["code"], 3, 40):
        raise SeedError(f"{where}: code має містити 3-40 символів")
    if not _is_text(item["title"], 3, 120):
        raise SeedError(f"{where}: title має містити 3-120 символів")
    if item["category_id"] not in category_ids or not _is_int(item["category_id"]):
        raise SeedError(f"{where}: category_id посилається на невідому категорію")
    value = item["value"]
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    if not is_number or not math.isfinite(value):
        raise SeedError(f"{where}: value має бути скінченним числом")
    if not VALUE_MIN <= value <= VALUE_MAX:
        raise SeedError(f"{where}: value поза межами {VALUE_MIN}-{VALUE_MAX}")
    if item["status"] not in STATUSES:
        raise SeedError(f"{where}: недозволений status {item['status']!r}")


def load_seed(path: Path = SEED_PATH) -> dict[str, list[dict[str, Any]]]:
    """Прочитати JSON і перевірити його вміст"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"Файл {path.name} не знайдено") from exc
    except (OSError, ValueError) as exc:
        raise SeedError(f"Не вдалося прочитати {path.name}: {exc}") from exc

    if not isinstance(data, dict) or set(data) != {"categories", "records"}:
        raise SeedError("JSON має містити лише масиви categories та records")
    categories, records = data["categories"], data["records"]
    if not isinstance(categories, list) or not isinstance(records, list):
        raise SeedError("categories та records мають бути масивами")
    if not categories or not records:
        raise SeedError("categories та records не можуть бути порожніми")

    for index, item in enumerate(categories):
        _check_category(index, item)
    category_ids = {item["id"] for item in categories}
    if len(category_ids) != len(categories):
        raise SeedError("id категорій повторюються")
    if len({item["name"].strip() for item in categories}) != len(categories):
        raise SeedError("назви категорій повторюються")

    for index, item in enumerate(records):
        _check_record(index, item, category_ids)
    if len({item["code"].strip() for item in records}) != len(records):
        raise SeedError("code записів повторюється")
    return data


def seed_database(data: dict[str, list[dict[str, Any]]]) -> bool:
    """Заповнити порожню базу однією транзакцією.

    Повертає False, якщо база вже містить дані
    """
    with closing(get_connection()) as connection:
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT (SELECT COUNT(*) FROM categories)"
                    " + (SELECT COUNT(*) FROM records)"
                ).fetchone()[0]
                if existing:
                    return False
                connection.executemany(
                    "INSERT INTO categories (id, name) VALUES (?, ?)",
                    [(c["id"], c["name"].strip()) for c in data["categories"]],
                )
                connection.executemany(
                    "INSERT INTO records (code, title, category_id, value, status)"
                    " VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            r["code"].strip(),
                            r["title"].strip(),
                            r["category_id"],
                            r["value"],
                            r["status"],
                        )
                        for r in data["records"]
                    ],
                )
        except sqlite3.Error as exc:
            raise SeedError(
                f"Не вдалося заповнити базу: {exc}. Усі зміни скасовано."
            ) from exc
    return True


def main() -> int:
    """Точка входу: python -m labs.lab03.seed"""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    try:
        data = load_seed()
        initialize_database()
        inserted = seed_database(data)
    except SeedError as exc:
        logger.error("%s", exc)
        return 1
    except sqlite3.Error as exc:
        logger.error("Помилка бази даних: %s", exc)
        return 1
    if inserted:
        logger.info(
            "Додано %d категорії та %d записів.",
            len(data["categories"]),
            len(data["records"]),
        )
    else:
        logger.info("База вже містить дані: заповнення пропущено, змін немає.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
