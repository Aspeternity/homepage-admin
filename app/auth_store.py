from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Any

import bcrypt
from filelock import FileLock

from .settings import settings


class AuthError(RuntimeError):
    pass


class AuthStore:
    """Persistent administrator credentials and session secret.

    New installations store only a bcrypt password hash in /data/auth.json.
    Legacy ADMIN_USERNAME / ADMIN_PASSWORD(_HASH) environment variables remain
    supported and are migrated into the persistent file so they can later be
    removed from Compose without changing the account.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        legacy_username: str | None = None,
        legacy_password: str | None = None,
        legacy_password_hash: str | None = None,
        session_secret_override: str | None = None,
    ) -> None:
        self.data_dir = Path(data_dir or settings.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "auth.json"
        self.lock_path = self.data_dir / ".auth.lock"
        self.legacy_username = (
            settings.username if legacy_username is None else legacy_username
        ).strip()
        self.legacy_password = settings.password if legacy_password is None else legacy_password
        self.legacy_password_hash = (
            settings.password_hash if legacy_password_hash is None else legacy_password_hash
        ).strip()
        self.session_secret_override = (
            settings.session_secret if session_secret_override is None else session_secret_override
        ).strip()
        self._bootstrap()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthError("/data/auth.json 无法读取或格式损坏；为安全起见不会自动进入首次设置。") from exc
        if not isinstance(payload, dict):
            raise AuthError("/data/auth.json 格式无效；为安全起见不会自动进入首次设置。")
        return payload

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".auth.json.", dir=str(self.data_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _valid_hash(value: str) -> bool:
        return value.startswith(("$2a$", "$2b$", "$2y$")) and len(value) >= 50

    def _bootstrap(self) -> None:
        """Persist a session secret and migrate legacy Compose credentials."""
        with FileLock(str(self.lock_path), timeout=15):
            payload = self._read()
            changed = False

            stored_secret = str(payload.get("session_secret") or "").strip()
            if self.session_secret_override:
                if stored_secret != self.session_secret_override:
                    payload["session_secret"] = self.session_secret_override
                    changed = True
            elif not stored_secret:
                payload["session_secret"] = secrets.token_urlsafe(48)
                changed = True

            # Existing environment based installs keep working, while the same
            # credentials are mirrored into /data so Compose can be simplified later.
            if self.legacy_password_hash or self.legacy_password:
                username = self.legacy_username or "admin"
                stored_username = str(payload.get("username") or "").strip()
                stored_hash = str(payload.get("password_hash") or "").strip()
                if self.legacy_password_hash:
                    password_hash = self.legacy_password_hash
                    credentials_changed = stored_username != username or stored_hash != password_hash
                else:
                    credentials_changed = stored_username != username or not self._valid_hash(stored_hash)
                    if not credentials_changed:
                        try:
                            credentials_changed = not bcrypt.checkpw(
                                self.legacy_password.encode("utf-8"), stored_hash.encode("utf-8")
                            )
                        except ValueError:
                            credentials_changed = True
                    password_hash = stored_hash if not credentials_changed else bcrypt.hashpw(
                        self.legacy_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
                    ).decode("utf-8")
                if credentials_changed:
                    payload.update({"version": 1, "username": username, "password_hash": password_hash})
                    changed = True

            if changed:
                self._atomic_write(payload)

    @staticmethod
    def _file_configured(payload: dict[str, Any]) -> bool:
        return bool(str(payload.get("username") or "").strip()) and AuthStore._valid_hash(
            str(payload.get("password_hash") or "").strip()
        )

    def is_configured(self) -> bool:
        # Explicit legacy credentials have precedence for backwards compatibility.
        if self.legacy_password_hash or self.legacy_password:
            return bool(self.legacy_username or "admin")
        return self._file_configured(self._read())

    def username(self) -> str:
        if self.legacy_password_hash or self.legacy_password:
            return self.legacy_username or "admin"
        return str(self._read().get("username") or "").strip()

    def session_secret(self) -> str:
        if self.session_secret_override:
            return self.session_secret_override
        payload = self._read()
        value = str(payload.get("session_secret") or "").strip()
        if value:
            return value
        # Normally created by _bootstrap; this is a last-resort recovery path.
        with FileLock(str(self.lock_path), timeout=15):
            payload = self._read()
            value = str(payload.get("session_secret") or "").strip()
            if not value:
                value = secrets.token_urlsafe(48)
                payload["session_secret"] = value
                self._atomic_write(payload)
            return value

    def verify_password(self, candidate: str) -> bool:
        if self.legacy_password_hash:
            password_hash = self.legacy_password_hash
        elif self.legacy_password:
            return secrets.compare_digest(candidate, self.legacy_password)
        else:
            password_hash = str(self._read().get("password_hash") or "").strip()
        if not self._valid_hash(password_hash):
            return False
        try:
            return bcrypt.checkpw(candidate.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    @staticmethod
    def validate_username(username: str) -> str:
        value = username.strip()
        if len(value) < 3 or len(value) > 64:
            raise AuthError("用户名长度必须在 3 到 64 个字符之间。")
        if re.search(r"[\x00-\x1f\x7f]", value):
            raise AuthError("用户名不能包含控制字符。")
        return value

    @staticmethod
    def validate_password(password: str) -> None:
        if len(password) < 10:
            raise AuthError("密码至少需要 10 个字符。")
        if len(password.encode("utf-8")) > 72:
            raise AuthError("密码 UTF-8 长度不能超过 72 字节。")

    def create_initial_account(self, username: str, password: str) -> str:
        username = self.validate_username(username)
        self.validate_password(password)
        with FileLock(str(self.lock_path), timeout=15):
            payload = self._read()
            if self._file_configured(payload) or self.legacy_password_hash or self.legacy_password:
                raise AuthError("管理员账号已经创建。")
            payload.update(
                {
                    "version": 1,
                    "username": username,
                    "password_hash": bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
                    ).decode("utf-8"),
                }
            )
            if not str(payload.get("session_secret") or "").strip():
                payload["session_secret"] = secrets.token_urlsafe(48)
            self._atomic_write(payload)
        return username


# A single process-wide store. Instantiation also creates the persistent session
# secret before SessionMiddleware is configured.
auth_store = AuthStore()
