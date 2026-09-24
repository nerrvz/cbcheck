import os
import subprocess
import sys


def run_task(script_name: str):
    print(f"\n{'=' * 50}")
    print(f"ЗАПУСК ЗАВДАННЯ: {script_name}")
    print(f"{'=' * 50}\n")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, script_name)

    if not os.path.exists(script_path):
        print(f"Помилка: Файл {script_name} не знайдено у папці {current_dir}!")
        return

    try:
        subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nЗавдання {script_name} завершилося з помилкою (код {e.returncode}).")
    except OSError as e:
        print(f"\nСистемна помилка під час запуску {script_name}: {e}")


def main():
    """Головна функція, що керує запуском усіх завдань лабораторної роботи."""
    print("\n" + "*" * 50)
    print("🎓 ПОЧАТОК ВИКОНАННЯ ЛАБОРАТОРНОЇ РОБОТИ №1")
    print("*" * 50)

    tasks = ["task1.py", "task2.py", "task3.py"]

    for task in tasks:
        run_task(task)

    print("\n" + "*" * 50)
    print("УСІ ЗАВДАННЯ ЛАБОРАТОРНОЇ РОБОТИ УСПІШНО ВИКОНАНО!")
    print("*" * 50 + "\n")


if __name__ == "__main__":
    main()