# Лабораторна робота №3, варіант 11

Облік завантаження каналів зв'язку (FastAPI + SQLite, без ORM).

- Категорії: `internet`, `vpn`, `backup_link`
- `value`: частка використання пропускної здатності, `percent`, від 0 до 100
- Поріг варіанта: 70.0 (зберігається в `config.py`)
- `status`: `new`, `in_progress`, `done`

## Встановлення

```bash
pip install -r requirements.txt
```

## Початкове заповнення

```bash
python -m labs.lab03.seed
```

Повторний запуск нічого не змінює й виводить повідомлення.

## Запуск API

```bash
uvicorn labs.lab03.main:app --reload --host 127.0.0.1 --port 8000
```

Документація: http://127.0.0.1:8000/docs

## Приклади запитів

```bash
curl -i "http://127.0.0.1:8000/ping"
curl -i "http://127.0.0.1:8000/records?category_id=1&status=new&limit=5&offset=0"
curl -i -X POST "http://127.0.0.1:8000/records" \
  -H "Content-Type: application/json" \
  -d '{"code":"V11-TEST","title":"Тестове вимірювання","category_id":1,"value":55.5,"status":"new"}'
curl -i -X POST "http://127.0.0.1:8000/records/bulk" \
  -H "Content-Type: application/json" \
  -d '[{"code":"V11-ROLLBACK","title":"Перший елемент","category_id":1,"value":40.0,"status":"new"},{"code":"V11-01","title":"Дублікат коду","category_id":2,"value":50.0,"status":"new"}]'
```

Останній запит повертає `409`, запис `V11-ROLLBACK` не зберігається.

## Структура

| Файл | Призначення |
|---|---|
| `main.py` | застосунок, lifespan, `/ping`, `/student` |
| `routers/` | маршрути категорій і записів |
| `repository.py` | усі SQL-запити |
| `schemas.py` | Pydantic-моделі |
| `errors.py` | перетворення помилок БД на HTTP-коди |
| `database.py`, `schema.sql` | з'єднання та готова схема |
| `seed.py`, `data/seed.json` | початкові дані |
| `config.py` | параметри варіанта |