from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 600_000
SALT_SIZE = 16
SESSION_TIMEOUT_SEC = 900
EMAIL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ALLOWED_ACTIONS = {"login_success", "login_failure", "logout"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User:
    def __init__(
        self, username: str, email: str, role: str, password: str, active: bool = True
    ) -> None:
        self.username = username
        self.email = email  # проходить через setter з валідацією
        self.role = role
        self.active = active
        self.__password_hash = b""
        self.__password_salt = b""
        self.set_password(password)

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        if not isinstance(value, str) or not EMAIL_RE.fullmatch(value):
            raise ValueError(f"Некоректний email: {value!r}")
        self._email = value

    def _derive(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )

    def set_password(self, password: str) -> None:
        if not password:
            raise ValueError("Пароль не може бути порожнім")
        self.__password_salt = os.urandom(SALT_SIZE)
        self.__password_hash = self._derive(password, self.__password_salt)

    def check_password(self, password: str) -> bool:
        candidate = self._derive(password, self.__password_salt)
        return hmac.compare_digest(candidate, self.__password_hash)

    def deactivate(self) -> None:
        self.active = False

    def __str__(self) -> str:
        return (
            f"User(username={self.username}, email={self.email}, "
            f"role={self.role}, active={self.active})"
        )


class Admin(User):
    def __init__(
        self,
        username: str,
        email: str,
        password: str,
        permissions: Iterable[str] | None = None,
    ) -> None:
        super().__init__(username, email, "admin", password)
        self.permissions: set[str] = set(permissions or [])

    def grant_permission(self, permission: str) -> None:
        self.permissions.add(permission)

    def revoke_permission(self, permission: str) -> None:
        self.permissions.discard(permission)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def __str__(self) -> str:
        return f"{super().__str__()}, permissions={sorted(self.permissions)}"


class Session:
    def __init__(self, ip: str) -> None:
        self.ip = ip
        self.login_time = utc_now()
        self.last_activity = self.login_time

    def touch(self) -> None:
        self.last_activity = utc_now()

    def is_active(self, timeout_sec: int) -> bool:
        if timeout_sec <= 0:
            raise ValueError("timeout_sec має бути додатним")
        return utc_now() - self.last_activity <= timedelta(seconds=timeout_sec)


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    username: str
    action: str


@dataclass
class AuditLog:
    entries: list[LogEntry] = field(default_factory=list)

    def add_log(self, username: str, action: str) -> None:
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Невідома дія: {action}")
        self.entries.append(LogEntry(utc_now(), username, action))

    def show_all(self) -> None:
        for e in self.entries:
            print(
                f"{e.timestamp:%Y-%m-%d %H:%M:%S} UTC | {e.username:<10} | {e.action}"
            )


class UserAccount:
    _ALLOWED_KEYS: dict[str, tuple[type, ...]] = {
        "user": (User,),
        "session": (Session, type(None)),
        "audit": (AuditLog,),
    }

    def __init__(
        self,
        user: User,
        session: Session | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self._data: dict[str, object] = {
            "user": user,
            "session": session,
            "audit": audit if audit is not None else AuditLog(),
        }

    def login(self, username: str, password: str, ip: str) -> bool:
        user: User = self._data["user"]  # type: ignore[assignment]
        audit: AuditLog = self._data["audit"]  # type: ignore[assignment]
        ok = user.active and username == user.username and user.check_password(password)
        if not ok:
            audit.add_log(username, "login_failure")
            return False
        session = Session(ip)
        session.touch()
        self._data["session"] = session
        audit.add_log(username, "login_success")
        return True

    def is_authenticated(self) -> bool:
        session = self._data["session"]
        return isinstance(session, Session) and session.is_active(SESSION_TIMEOUT_SEC)

    def logout(self) -> None:
        user: User = self._data["user"]  # type: ignore[assignment]
        audit: AuditLog = self._data["audit"]  # type: ignore[assignment]
        if self._data["session"] is not None:
            audit.add_log(user.username, "logout")
        self._data["session"] = None

    def __getitem__(self, key: str) -> object:
        if key not in self._ALLOWED_KEYS:
            raise KeyError(key)
        return self._data[key]

    def __setitem__(self, key: str, value: object) -> None:
        if key not in self._ALLOWED_KEYS:
            raise KeyError(key)
        if not isinstance(value, self._ALLOWED_KEYS[key]):
            raise TypeError(f"Неправильний тип для {key!r}: {type(value).__name__}")
        self._data[key] = value


def run_demo() -> None:
    audit = AuditLog()
    user = User("alice_01", "alice_01@example.com", "user", "S3cret!pass")
    account = UserAccount(user, audit=audit)
    print(account["user"])

    print("Невдалий вхід:", account.login("alice_01", "wrong", "10.0.0.5"))
    print("Успішний вхід:", account.login("alice_01", "S3cret!pass", "10.0.0.5"))
    print("Автентифікований:", account.is_authenticated())

    try:
        user.email = "a@x"
    except ValueError as exc:
        print("Валідація email:", exc)
    user.email = "alice_new@example.org"
    print("Новий email:", user.email)

    admin = Admin("root_admin", "root_admin@corp.ua", "Adm1n!pass", {"read"})
    admin.grant_permission("write")
    admin.revoke_permission("read")
    print(admin, "| write:", admin.has_permission("write"))

    session = account["session"]
    session.last_activity -= timedelta(seconds=SESSION_TIMEOUT_SEC + 1)
    print("Після таймаута:", account.is_authenticated())

    account.login("alice_01", "S3cret!pass", "10.0.0.5")
    account.logout()
    print("Після logout:", account.is_authenticated())

    try:
        account["password_hash"]
    except KeyError as exc:
        print("KeyError:", exc)

    print("\n=== AuditLog ===")
    audit.show_all()
