from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("arp_audit")

IP_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
MAC_RE = re.compile(r"[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}")
IGNORED_MACS = {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"}
REQUIRED_COLUMNS = {"ipaddress", "macaddress"}

EXIT_OK = 0
EXIT_CONFLICTS = 1
EXIT_ERROR = 2
EXIT_UNEXPECTED = 3
EXIT_INTERRUPTED = 130


class ArpAuditError(Exception):
    """Очікувана помилка роботи утиліти"""


@dataclass
class ArpEntry:
    line_no: int
    ip: str
    mac: str
    interface: str = ""
    entry_type: str = ""


@dataclass
class ArpConflict:
    mac: str
    entries: list[ArpEntry] = field(default_factory=list)

    @property
    def ips(self) -> list[str]:
        return sorted({e.ip for e in self.entries})


def is_valid_ip(value: str) -> bool:
    if not IP_RE.fullmatch(value):
        return False
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def is_valid_mac(value: str) -> bool:
    return MAC_RE.fullmatch(value) is not None


def normalize_mac(value: str) -> str:
    return value.lower().replace("-", ":")


def check_input_file(path: Path) -> None:
    """Перевіряє вхідний файл до читання,кидає ArpAuditError."""
    if not path.exists():
        raise ArpAuditError(f"Файл не знайдено: {path}")
    if path.is_dir():
        raise ArpAuditError(f"Це каталог, а не файл: {path}")
    if path.stat().st_size == 0:
        raise ArpAuditError(f"Файл порожній: {path}")


def read_arp_entries(path: Path) -> Iterator[ArpEntry]:
    """Генератор: читає CSV або текстову ARP-таблицю по одному запису."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if path.suffix.lower() == ".csv":
            try:
                header_line = handle.readline()
                handle.seek(0)
            except OSError as exc:
                raise ArpAuditError(f"Не вдалося прочитати заголовок CSV: {exc}") from exc
            delimiter = max((",", ";", "\t"), key=header_line.count)
            if header_line.count(delimiter) == 0:
                delimiter = ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            try:
                fieldnames = reader.fieldnames
            except (csv.Error, OSError) as exc:
                raise ArpAuditError(f"Не вдалося розібрати заголовок CSV: {exc}") from exc
            if not fieldnames:
                raise ArpAuditError("У CSV немає заголовка")
            columns = [c.strip().lower().replace(" ", "") for c in fieldnames if c]
            if not columns:
                raise ArpAuditError("Заголовок CSV порожній (усі назви колонок пусті)")
            duplicated = sorted({c for c in columns if columns.count(c) > 1})
            if duplicated:
                raise ArpAuditError(
                    f"У заголовку CSV колонки повторюються: {', '.join(duplicated)}"
                )
            missing = REQUIRED_COLUMNS - set(columns)
            if missing:
                titles = {"ipaddress": "IP Address", "macaddress": "MAC Address"}
                names = ", ".join(titles[m] for m in sorted(missing))
                raise ArpAuditError(
                    f"У CSV відсутні обов'язкові колонки: {names} "
                    f"(знайдено: {', '.join(f.strip() for f in fieldnames if f)})"
                )
            for row in reader:
                norm = {
                    k.strip().lower().replace(" ", ""): (v or "").strip()
                    for k, v in row.items()
                    if k and isinstance(v, str | None)
                }
                yield ArpEntry(
                    reader.line_num,
                    norm.get("ipaddress", ""),
                    norm.get("macaddress", ""),
                    norm.get("interface", ""),
                    norm.get("type", ""),
                )
        else:
            for line_no, line in enumerate(handle, start=1):
                parts = line.split()
                if len(parts) < 2 or parts[0].lower() in {"ip", "address", "#"}:
                    continue
                yield ArpEntry(line_no, parts[0], parts[1], *parts[2:4])

def split_entries(
    entries: Iterator[ArpEntry],
) -> tuple[list[ArpEntry], list[ArpEntry]]:
    valid: list[ArpEntry] = []
    invalid: list[ArpEntry] = []
    for entry in entries:
        if is_valid_ip(entry.ip) and is_valid_mac(entry.mac):
            entry.mac = normalize_mac(entry.mac)
            valid.append(entry)
        else:
            invalid.append(entry)
            logger.warning(
                "Рядок %d: некоректний IP/MAC (%r, %r)",
                entry.line_no,
                entry.ip,
                entry.mac,
            )
    return valid, invalid


def find_conflicts(valid: list[ArpEntry]) -> list[ArpConflict]:
    by_mac: defaultdict[str, list[ArpEntry]] = defaultdict(list)
    for entry in valid:
        by_mac[entry.mac].append(entry)
    return [
        ArpConflict(mac, items)
        for mac, items in by_mac.items()
        if mac not in IGNORED_MACS and len({i.ip for i in items}) > 1
    ]


def setup_logging(log_file: Path | None) -> None:
    """Налаштовує логування; якщо файл журналу недоступний, лишає лише консоль."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_error: OSError | None = None
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as exc:
            file_error = exc
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    if file_error:
        logger.warning("Журнал у файл вимкнено, не вдалося відкрити %s: %s", log_file, file_error)


def save_report(
    path: Path,
    source: Path,
    total: int,
    valid: int,
    invalid: list[ArpEntry],
    conflicts: list[ArpConflict],
) -> None:
    if path.is_dir():
        raise ArpAuditError(f"--output-json вказує на каталог: {path}")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "total_entries": total,
        "valid_entries": valid,
        "invalid_entries": [asdict(e) for e in invalid],
        "conflicts": [
            {"mac": c.mac, "ips": c.ips, "entries": [asdict(e) for e in c.entries]}
            for c in conflicts
        ],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ArpAuditError(f"Не вдалося зберегти звіт {path}: {exc}") from exc


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--arp-file", type=Path, required=True, help="CSV/текстова ARP-таблиця")
    parser.add_argument("--output-json", type=Path, help="Шлях до JSON-звіту")
    parser.add_argument(
        "--detect-spoofing",
        action="store_true",
        help="Шукати дублікати MAC для різних IP",
    )
    parser.add_argument("--log-file", type=Path, help="Файл журналу подій")


def _analyze(args: argparse.Namespace) -> int:
    check_input_file(args.arp_file)
    logger.info("Parsing ARP table snapshot from %s...", args.arp_file)
    try:
        valid, invalid = split_entries(read_arp_entries(args.arp_file))
    except PermissionError as exc:
        raise ArpAuditError(f"Немає доступу до файлу {args.arp_file}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ArpAuditError(f"Файл не у кодуванні UTF-8: {exc}") from exc
    except (OSError, csv.Error) as exc:
        raise ArpAuditError(f"Не вдалося прочитати файл: {exc}") from exc

    total = len(valid) + len(invalid)
    if total == 0:
        raise ArpAuditError("У файлі немає жодного запису ARP")

    logger.info("Validated %d IP/MAC entries.", total)
    print("\n=== Validated Entries Summary ===")
    print(f"Valid IP/MAC Pairs : {len(valid)}")
    print(f"Invalid Syntax     : {len(invalid)}")
    if not valid:
        logger.warning("Жодного коректного запису, перевірка конфліктів неможлива")

    conflicts = find_conflicts(valid) if args.detect_spoofing else []
    if conflicts:
        print("\n=== CRITICAL SECURITY ALERTS: ARP-SPOOFING DETECTED ===")
    for c in conflicts:
        print("[ALERT] MAC Address Duplicate Conflict!")
        print(f"MAC Address: {c.mac} associated with MULTIPLE IP addresses:")
        for e in c.entries:
            print(f"  - {e.ip} (iface: {e.interface or '-'}, type: {e.entry_type or '-'})")
        print("-> POSSIBLE MAN-IN-THE-MIDDLE / ARP-SPOOFING ATTACK!")
        logger.critical("ARP-spoofing suspect: MAC %s -> IPs %s", c.mac, ", ".join(c.ips))

    if args.output_json:
        save_report(args.output_json, args.arp_file, total, len(valid), invalid, conflicts)
        logger.info("Report saved to %s", args.output_json)

    return EXIT_CONFLICTS if conflicts else EXIT_OK


def run(args: argparse.Namespace) -> int:
    setup_logging(args.log_file)
    try:
        return _analyze(args)
    except ArpAuditError as exc:
        logger.error("%s", exc)
        return EXIT_ERROR
    except KeyboardInterrupt:
        logger.error("Перервано користувачем")
        return EXIT_INTERRUPTED
    except Exception:
        logger.exception("Непередбачена помилка")
        return EXIT_UNEXPECTED