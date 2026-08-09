from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    config_dir: Path = Path(os.getenv("HOMEPAGE_CONFIG_DIR", "/config"))
    data_dir: Path = Path(os.getenv("ADMIN_DATA_DIR", "/data"))
    username: str = os.getenv("ADMIN_USERNAME", "admin")
    password: str = os.getenv("ADMIN_PASSWORD", "")
    password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    session_secret: str = os.getenv("SESSION_SECRET", "change-this-session-secret")
    cookie_secure: bool = _bool("ADMIN_COOKIE_SECURE", False)
    homepage_url: str = os.getenv("HOMEPAGE_URL", "http://localhost:3000")
    backup_limit: int = int(os.getenv("BACKUP_LIMIT", "50"))
    allowed_hosts: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("ADMIN_ALLOWED_HOSTS", "*").split(",") if x.strip()
    )

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def audit_log(self) -> Path:
        return self.data_dir / "audit.jsonl"


settings = AppSettings()
