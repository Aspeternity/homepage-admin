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
    username: str = os.getenv("ADMIN_USERNAME", "").strip()
    password: str = os.getenv("ADMIN_PASSWORD", "")
    password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    session_secret: str = os.getenv("SESSION_SECRET", "").strip()
    cookie_secure: bool = _bool("ADMIN_COOKIE_SECURE", False)
    homepage_url: str = os.getenv("HOMEPAGE_URL", "").strip()
    backup_limit: int = int(os.getenv("BACKUP_LIMIT", "50"))
    docker_discovery_url: str = os.getenv("DOCKER_DISCOVERY_URL", "").strip()
    docker_public_host: str = os.getenv("DOCKER_PUBLIC_HOST", "").strip()
    docker_server_name: str = os.getenv("DOCKER_SERVER_NAME", "").strip()
    homepage_docker_proxy_host: str = os.getenv("HOMEPAGE_DOCKER_PROXY_HOST", "homepage-docker-proxy").strip()
    homepage_docker_proxy_port: int = int(os.getenv("HOMEPAGE_DOCKER_PROXY_PORT", "2375"))
    hide_internal_containers: bool = _bool("DOCKER_HIDE_INTERNAL", True)
    widget_schema_auto_sync: bool = _bool("WIDGET_SCHEMA_AUTO_SYNC", True)
    widget_schema_sync_interval_hours: int = int(os.getenv("WIDGET_SCHEMA_SYNC_INTERVAL_HOURS", "24"))
    widget_schema_sync_mode: str = os.getenv("WIDGET_SCHEMA_SYNC_MODE", "interval").strip().lower() or "interval"
    widget_schema_sync_time: str = os.getenv("WIDGET_SCHEMA_SYNC_TIME", "03:00").strip() or "03:00"
    widget_schema_timezone: str = os.getenv("WIDGET_SCHEMA_TIMEZONE", os.getenv("TZ", "UTC")).strip() or "UTC"
    widget_schema_ref: str = os.getenv("WIDGET_SCHEMA_REF", "dev").strip() or "dev"
    widget_schema_timeout: float = float(os.getenv("WIDGET_SCHEMA_TIMEOUT", "8"))
    widget_schema_workers: int = int(os.getenv("WIDGET_SCHEMA_WORKERS", "10"))
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
