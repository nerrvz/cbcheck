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


def read_arp_entries(path: Path) -> Iterator[ArpEntry]:
    """Генератор: читає CSV або текстову ARP-таблицю по одному запису."""
    with path.open(encoding="utf-8", newline="") as handle:
        if path.suffix.lower() == ".csv":
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                norm = {
                    k.strip().lower().replace(" ", ""): (v or "").strip()
                    for k, v in row.items()
                    if k
                }
                yield ArpEntry(
                    line_no,
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
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )


def save_report(
    path: Path,
    source: Path,
    total: int,
    valid: int,
    invalid: list[ArpEntry],
    conflicts: list[ArpConflict],
) -> None:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--arp-file", type=Path, required=True, help="CSV/текстова ARP-таблиця"
    )
    parser.add_argument("--output-json", type=Path, help="Шлях до JSON-звіту")
    parser.add_argument(
        "--detect-spoofing",
        action="store_true",
        help="Шукати дублікати MAC для різних IP",
    )
    parser.add_argument("--log-file", type=Path, help="Файл журналу подій")


def run(args: argparse.Namespace) -> int:
    setup_logging(args.log_file)
    if not args.arp_file.is_file():
        logger.error("Файл не знайдено: %s", args.arp_file)
        return 2

    logger.info("Parsing ARP table snapshot from %s...", args.arp_file)
    try:
        valid, invalid = split_entries(read_arp_entries(args.arp_file))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        logger.error("Не вдалося прочитати файл: %s", exc)
        return 2

    total = len(valid) + len(invalid)
    logger.info("Validated %d IP/MAC entries.", total)
    print("\n=== Validated Entries Summary ===")
    print(f"Valid IP/MAC Pairs : {len(valid)}")
    print(f"Invalid Syntax     : {len(invalid)}")

    conflicts = find_conflicts(valid) if args.detect_spoofing else []
    if conflicts:
        print("\n=== CRITICAL SECURITY ALERTS: ARP-SPOOFING DETECTED ===")
    for c in conflicts:
        print("[ALERT] MAC Address Duplicate Conflict!")
        print(f"MAC Address: {c.mac} associated with MULTIPLE IP addresses:")
        for e in c.entries:
            print(
                f"  - {e.ip} (iface: {e.interface or '-'}, type: {e.entry_type or '-'})"
            )
        print("-> POSSIBLE MAN-IN-THE-MIDDLE / ARP-SPOOFING ATTACK!")
        logger.critical(
            "ARP-spoofing suspect: MAC %s -> IPs %s", c.mac, ", ".join(c.ips)
        )

    if args.output_json:
        try:
            save_report(
                args.output_json, args.arp_file, total, len(valid), invalid, conflicts
            )
        except OSError as exc:
            logger.error("Не вдалося зберегти звіт: %s", exc)
            return 2
        logger.info("Critical conflict logged to %s", args.output_json)

    return 1 if conflicts else 0
