# Лабораторна робота №2, варіант 11

Аудитор ARP-таблиць: шукає некоректні IP/MAC і ознаки ARP-spoofing
(одна MAC-адреса в кількох IP).

## Встановлення

```bash
pip install -r requirements.txt
```

## Вхідний файл

`labs/lab02/data/data_v11/arp_table.csv` з колонками
`IP Address, MAC Address, Interface, Type`.

## Запуск

Демонстрація Завдання 1:

```bash
python -m labs.lab02.main demo
```

Аналіз ARP-таблиці:

```bash
python -m labs.lab02.main analyze --arp-file labs/lab02/data/data_v11/arp_table.csv --detect-spoofing --output-json labs/lab02/data/arp_security_alerts.json
```

## Параметри

| Параметр | Опис |
|---|---|
| `--arp-file` | шлях до файлу (обов'язковий) |
| `--output-json` | куди зберегти JSON-звіт |
| `--detect-spoofing` | шукати дублікати MAC |
| `--log-file` | файл журналу |

## Помилки

- Файл не знайдено: повідомлення `ERROR`, код завершення 2.
- Некоректний рядок: пропускається з попередженням.
- Код 0: усе чисто. Код 1: знайдено підозру на spoofing.