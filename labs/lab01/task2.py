import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from shared.student import STUDENT_NAME, GROUP_NAME, VARIANT_NUMBER


def main():
    print(f"--- Завдання 2: Система контролю доступу ---")
    print(f"Студент: {STUDENT_NAME} | Група: {GROUP_NAME} | Варіант: {VARIANT_NUMBER}\n")

    users = {
        "risk_manager": {"role": "risk_analyst", "clearance": 4, "department": "Risk Management", "active": True},
        "business_analyst": {"role": "business_analyst", "clearance": 2, "department": "Business", "active": True},
        "legal_counsel": {"role": "legal", "clearance": 3, "department": "Legal", "active": True},
        "contractor_dev": {"role": "contractor", "clearance": 2, "department": "Contract", "active": True},
        "obsolete_system": {"role": "legacy_system", "clearance": 1, "department": "Legacy", "active": False}
    }

    resources = [
        ("risk_registers", 4), ("business_requirements", 2),
        ("legal_documents", 3), ("contract_code", 2), ("governance_framework", 4),
        ("meeting_minutes", 1), ("regulatory_reports", 3), ("executive_dashboards", 4),
        ("project_specs", 2), ("public_statements", 1)
    ]

    security_levels = ("Public", "Internal Use", "Restricted", "Highly Restricted")
    blocked_users = {"obsolete_system", "contract_expired", "legal_hold"}

    print("Список ресурсів системи:")
    for res_name, res_level in resources:
        text_level = security_levels[res_level - 1]
        print(f"- {res_name}: {text_level} (Рівень {res_level})")

    print("\n" + "=" * 50 + "\n")
    print("Результати перевірки доступу:\n")

    test_users = list(users.keys()) + ["unknown_hacker", "contract_expired"]

    for username in test_users:
        for res_name, res_level in resources:

            if username not in users:
                result = "DENY (User not found)"
            elif username in blocked_users:
                result = "DENY (User is blocked)"
            elif users[username]["active"] == False:
                result = "DENY (Account inactive)"
            elif users[username]["clearance"] >= res_level:
                result = "ALLOW"
            else:
                result = "DENY (Insufficient clearance)"

            print(f"user=[{username}] resource=[{res_name}] -> {result}")
        print("-" * 30)


if __name__ == "__main__":
    main()