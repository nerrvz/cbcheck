import os
import sys
import csv
import json
import hashlib
from datetime import datetime
from functools import wraps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from shared.student import STUDENT_NAME, GROUP_NAME, VARIANT_NUMBER

MIN_PASSWORD_LENGTH = 12
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CSV_FILE = os.path.join(DATA_DIR, 'users.csv')
LOG_FILE = os.path.join(DATA_DIR, 'log.json')
USERS_DB = []


class ValidationError(Exception):
    pass


PERSONAL_SALT = str(VARIANT_NUMBER).zfill(5)



def generate_hash(password: str, salt: str = "00000") -> str:
    if not password or not salt:
        raise ValueError("Пароль або сіль не можуть бути порожніми.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Пароль коротший за {MIN_PASSWORD_LENGTH} символів.")

    data = (password + salt).encode('utf-8')
    return hashlib.blake2b(data).hexdigest()


def create_user(username, password):
    hash_value = generate_hash(password, PERSONAL_SALT)
    return username, hash_value


def create_users(users_list):
    os.makedirs(DATA_DIR, exist_ok=True)

    users_data = []
    for u, p in users_list:
        try:
            users_data.append(create_user(u, p))
        except (ValueError, ValidationError) as e:
            print(f"  [Пропуск] {u}: {e}")

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['login', 'hash_password'])
        writer.writerows(users_data)



def log_event(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        username = args[0] if args else kwargs.get('username', 'unknown')
        try:
            result = func(*args, **kwargs)
            status = "success" if result else "failure"
        except Exception:
            status = "error"
            raise
        finally:
            log_entry = {
                "event": "login",
                "user": username,
                "result": status,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "args": list(args),
                "kwargs": kwargs
            }
            try:
                logs = []
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        try:
                            logs = json.load(f)
                        except json.JSONDecodeError:
                            pass
                logs.append(log_entry)
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=4, ensure_ascii=False)
            except IOError as io_err:
                print(f"Помилка запису логу: {io_err}")
        return result

    return wrapper


@log_event
def login(username: str, password: str) -> bool:
    if not username or not password:
        raise ValueError("Логін або пароль не можуть бути порожніми.")

    expected_hash = generate_hash(password, PERSONAL_SALT)

    for user in USERS_DB:
        if user['login'] == username and user['hash_password'] == expected_hash:
            return True
    return False



def main():
    print(f"--- Завдання 3: Хешування, CSV-база та JSON-логування ---")
    print(f"Студент: {STUDENT_NAME} | Група: {GROUP_NAME} | Варіант: {VARIANT_NUMBER}\n")

    users_to_register = (
        ("admin", "SuperAdmin12345"), ("manager", "MngPass2023!_long"),
        ("user1", "Usr1_Pass"), ("guest", "guest1234"),
        ("dev", "D3v_S3cr3t_123"), ("tester", "test"),
        ("empty_p", ""), ("analyst", "An4lyst_2024_pro"),
        ("ceo", "B0ss_P@ssw0rd99"), ("support", "H3lp_D3sk!_now")
    )

    try:
        print("1. Формування бази даних користувачів:")
        create_users(users_to_register)
        print(f"   CSV-базу успішно створено: {CSV_FILE}\n")

        global USERS_DB
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            USERS_DB = list(reader)

        print("2. Зміст CSV-бази (users_db):")
        print(f"{'Логін':<15} | {'Хеш пароля (BLAKE2B)'}")
        print("-" * 80)
        for u in USERS_DB:
            print(f"{u['login']:<15} | {u['hash_password'][:60]}...")

        print("\n3. Тестування системи автентифікації:")
        test_logins = [
            ("admin", "SuperAdmin12345"),
            ("manager", "WrongPass"),
            ("", "pass")
        ]

        for uname, pwd in test_logins:
            try:
                print(f"   Спроба входу для '{uname}': ", end="")
                is_success = login(uname, pwd)
                print("УСПІШНО (ALLOW)" if is_success else "ВІДМОВЛЕНО (DENY)")
            except (ValueError, ValidationError) as ve:
                print(f"ПОМИЛКА ({ve})")

        print(f"\n   Журнал подій успішно записано у: {LOG_FILE}")

    except Exception as e:
        print(f"Неочікувана помилка системи: {e}")


if __name__ == "__main__":
    main()