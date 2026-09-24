import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from functools import wraps

try:
    from shared.student import GROUP_NAME, STUDENT_NAME, VARIANT_NUMBER
except ImportError:
    VARIANT_NUMBER = 11

DATA_DIR = "labs/lab01/data"
USERS_FILE = os.path.join(DATA_DIR, "users.csv")
LOG_FILE = os.path.join(DATA_DIR, "log.json")

MIN_PASSWORD_LENGTH = 12
PERSONAL_SALT = str(VARIANT_NUMBER).zfill(5)


class ValidationError(Exception):
    """якщо пароль не підходить вимогам"""
    pass


def generate_hash(password: str, salt: str = "00000") -> str:
    if not password or not salt:
        raise ValueError("Пароль або сіль не можуть бути порожніми.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Пароль коротший за {MIN_PASSWORD_LENGTH} символів.")

    salted_password = password + salt
    return hashlib.blake2b(salted_password.encode('utf-8')).hexdigest()


def create_user(username, password):
    hash_value = generate_hash(password, PERSONAL_SALT)
    return (username, hash_value)


def create_users(users_list):
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        with open(USERS_FILE, mode='w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            for username, password in users_list:
                try:
                    user_record = create_user(username, password)
                    writer.writerow(user_record)
                except (ValueError, ValidationError) as e:
                    print(f"Помилка створення запису для {username}: {e}")
    except (OSError, PermissionError) as e:
        print(f"Системна помилка доступу до файлу бази даних: {e}")


def print_users(users_db: dict):
    """Виводить список користувачів у вигляді структурованої таблиці на екран[cite: 2]."""
    if not users_db:
        print("База даних порожня або сталася помилка зчитування.")
        return

    print(f"{'Логін':<15} | {'Хеш пароля'}")
    print("-" * 50)
    for login_name, pass_hash in users_db.items():
        print(f"{login_name:<15} | {pass_hash[:30]}...")
    print("-" * 50)


def log_event(func):
    """Декоратор, який записує кожну спробу входу у файл log.json"""

    @wraps(func)
    def wrapper(username: str, password: str, *args, **kwargs):
        result = func(username, password, *args, **kwargs)

        log_entry = {
            "event": "login",
            "user": username,
            "result": "success" if result else "failure",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "args": list(args),
            "kwargs": kwargs
        }

        try:
            logs = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, mode='r', encoding='utf-8') as file:
                    try:
                        logs = json.load(file)
                    except json.JSONDecodeError:
                        logs = []
            logs.append(log_entry)
            with open(LOG_FILE, mode='w', encoding='utf-8') as file:
                json.dump(logs, file, indent=4)
        except (OSError, PermissionError) as e:
            print(f"Помилка запису у файл логів: {e}")

        return result

    return wrapper


@log_event
def login(username: str, password: str) -> bool:
    """Перевіряє, чи існує користувач у базі, та чи збігається хеш введеного пароля з урахуванням солі[cite: 2]."""
    if not username or not password:
        raise ValueError("Логін або пароль не можуть бути порожніми.")

    users_db = {}
    try:
        with open(USERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) == 2:
                    users_db[row[0]] = row[1]
    except FileNotFoundError:
        print(f"Помилка: Файл {USERS_FILE} не знайдено.")
        return False
    except (OSError, PermissionError) as e:
        print(f"Помилка читання файлу користувачів: {e}")
        return False

    if username not in users_db:
        return False

    try:
        attempt_hash = generate_hash(password, PERSONAL_SALT)
        return attempt_hash == users_db[username]
    except (ValueError, ValidationError) as e:
        print(f"Помилка під час обробки пароля: {e}")
        return False


def main():
    users_to_register = (
        ("admin1", "SuperSecurePass12"),
        ("user02", "MyPassword12345"),
        ("guest3", "WelcomeGuest2026"),
        ("elena4", "ElenaSecure123"),
        ("test05", "TestPassword005"),
        ("manager", "ManagerPass123"),
        ("student", "StudentPass2026"),
        ("hacker8", "HackerPassword!"),
        ("dev009", "DeveloperPass09"),
        ("boss10", "BossSecurePass1")
    )
    print("--- Завдання 3: Безпечне хешування, CSV-база та JSON-логування з винятками ---")
    print(f"Студент: {STUDENT_NAME} | Група: {GROUP_NAME} | Варіант: {VARIANT_NUMBER}\n")
    print("=== Створення бази даних ===")
    create_users(users_to_register)

    print("\n=== Крок 2. Зчитування та вивід структурованої таблиці ===")
    users_db = {}
    try:
        with open(USERS_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) == 2:
                    users_db[row[0]] = row[1]
        print_users(users_db)
    except (OSError, FileNotFoundError, PermissionError) as e:
        print(f"Помилка читання бази даних: {e}")

    print("\n=== Тестування системи автентифікації ===")
    try:
        print("Спроба входу admin1:", login("admin1", "SuperSecurePass12"))
        print("Спроба входу user02 (невірний пароль):", login("user02", "WrongPassword123"))
        print("Спроба порожнього логіна:", login("", "Password12345"))
    except (OSError, FileNotFoundError, PermissionError, ValidationError, ValueError) as e:
        print(f"\nКРИТИЧНА ПОМИЛКА під час авторизації: {type(e).__name__} - {e}")


if __name__ == "__main__":
    main()