import argparse
import sys

from labs.lab02 import task1, task2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m labs.lab02.main")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Демонстрація Завдання 1")
    analyze = sub.add_parser("analyze", help="Аудитор ARP-таблиць (варіант 11)")
    task2.add_arguments(analyze)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "demo":
        task1.run_demo()
        return 0
    return task2.run(args)


if __name__ == "__main__":
    sys.exit(main())
