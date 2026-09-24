import os
import random
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from shared.student import GROUP_NAME, STUDENT_NAME, VARIANT_NUMBER

def main():
    print("--- Аналізатор паролів ---")
    print(f"Студент: {STUDENT_NAME} | Група: {GROUP_NAME} | Варіант: {VARIANT_NUMBER}\n")

    passwords = [
        "APT@Detect10n", "simple", "Red@Team2023", "participant",
        "Blue@T3am", "common123", "Purple@T34m", "regular123",
        "Gr33n@Team", "normal123"
    ]

    criteria = {
        "min_length": 7,
        "require_digits": True,
        "require_upper": True,
        "require_special": True
    }

    forbidden_passwords = {
        "simple", "participant", "common123", "regular123",
        "normal123", "test"
    }

    random_indices = random.sample(range(len(passwords)), 3)
    for idx in random_indices:
        passwords.append(passwords[idx])

    results = []
    for pwd in passwords:
        status = evaluate_password(pwd, criteria, forbidden_passwords, passwords)
        results.append((pwd, status))

    print(f"{'Пароль':<20} | {'Рівень надійності'}")
    print("-" * 45)
    for pwd, status in results:
        print(f"{pwd:<20} | {status}")


def evaluate_password(pwd, criteria, forbidden, all_passwords):
    """Функція для оцінки стійкості пароля за заданим алгоритмом."""

    if pwd in forbidden or len(pwd) < criteria["min_length"]:
        return "Заборонений"

    has_digit = any(char.isdigit() for char in pwd)
    has_upper = any(char.isupper() for char in pwd)
    has_lower = any(char.islower() for char in pwd)
    has_special = any(not char.isalnum() for char in pwd)

    security_criteria = [has_digit, has_upper, has_lower, has_special]
    met_count = sum(security_criteria)
    meets_all_criteria = (met_count == 4)

    length_plus_4 = len(pwd) >= (criteria["min_length"] + 4)
    is_unique = all_passwords.count(pwd) == 1

    if meets_all_criteria and length_plus_4 and is_unique:
        return "Дуже сильний"

    if meets_all_criteria and not length_plus_4:
        return "Сильний"

    if len(pwd) >= criteria["min_length"] and (0 < met_count < 4):
        return "Середній"

    if met_count > 0:
        return "Слабкий"

    return "Невизначений"


if __name__ == "__main__":
    main()