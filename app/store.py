from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from filelock import FileLock
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .settings import settings

ALLOWED_FILES = {
    "services.yaml": list,
    "bookmarks.yaml": list,
    "settings.yaml": dict,
    "widgets.yaml": list,
    "docker.yaml": dict,
    "proxmox.yaml": dict,
    "kubernetes.yaml": dict,
    "custom.css": str,
    "custom.js": str,
}


def _yaml() -> YAML:
    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    y.width = 4096
    return y


class ConfigError(RuntimeError):
    pass


class HomepageStore:
    def __init__(self, config_dir: Path | None = None, data_dir: Path | None = None) -> None:
        self.config_dir = Path(config_dir or settings.config_dir)
        self.data_dir = Path(data_dir or settings.data_dir)
        self.backup_dir = self.data_dir / "backups"
        self.lock_path = self.data_dir / ".write.lock"
        self.audit_path = self.data_dir / "audit.jsonl"
        self.preferences_path = self.data_dir / "admin-settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def path(self, filename: str) -> Path:
        if filename not in ALLOWED_FILES:
            raise ConfigError(f"不允许访问文件：{filename}")
        return self.config_dir / filename

    def read_text(self, filename: str) -> str:
        path = self.path(filename)
        if not path.exists():
            return "" if filename.endswith((".css", ".js")) else "---\n"
        return path.read_text(encoding="utf-8")

    def load(self, filename: str) -> Any:
        text = self.read_text(filename)
        if filename.endswith((".css", ".js")):
            return text
        try:
            data = _yaml().load(text)
        except Exception as exc:
            raise ConfigError(f"{filename} YAML 解析失败：{exc}") from exc
        if data is None:
            expected = ALLOWED_FILES[filename]
            return CommentedSeq() if expected is list else CommentedMap()
        expected = ALLOWED_FILES[filename]
        if expected is list and not isinstance(data, list):
            raise ConfigError(f"{filename} 顶层必须是数组列表。")
        if expected is dict and not isinstance(data, dict):
            raise ConfigError(f"{filename} 顶层必须是对象映射。")
        return data

    def dump(self, data: Any) -> str:
        stream = StringIO()
        stream.write("---\n")
        _yaml().dump(data, stream)
        return stream.getvalue()

    def dump_fragment(self, data: Any) -> str:
        stream = StringIO()
        _yaml().dump(data, stream)
        return stream.getvalue().rstrip()

    def parse_fragment(self, text: str, expected: type = dict) -> Any:
        if not text.strip():
            return CommentedMap() if expected is dict else CommentedSeq()
        try:
            data = _yaml().load(text)
        except Exception as exc:
            raise ConfigError(f"YAML 片段解析失败：{exc}") from exc
        if data is None:
            return CommentedMap() if expected is dict else CommentedSeq()
        if not isinstance(data, expected):
            name = "对象" if expected is dict else "列表"
            raise ConfigError(f"这里需要 YAML {name}。")
        return data

    def parse_any(self, text: str) -> Any:
        if not text.strip():
            return CommentedMap()
        try:
            data = _yaml().load(text)
        except Exception as exc:
            raise ConfigError(f"YAML 片段解析失败：{exc}") from exc
        return CommentedMap() if data is None else data

    def validate_text(self, filename: str, text: str) -> Any:
        if filename.endswith((".css", ".js")):
            return text
        try:
            data = _yaml().load(text)
        except Exception as exc:
            raise ConfigError(f"YAML 语法错误：{exc}") from exc
        if data is None:
            data = CommentedSeq() if ALLOWED_FILES[filename] is list else CommentedMap()
        expected = ALLOWED_FILES[filename]
        if expected is list and not isinstance(data, list):
            raise ConfigError(f"{filename} 顶层必须是列表。")
        if expected is dict and not isinstance(data, dict):
            raise ConfigError(f"{filename} 顶层必须是映射。")
        return data

    @contextmanager
    def locked(self) -> Iterator[None]:
        with FileLock(str(self.lock_path), timeout=15):
            yield

    def _create_backup(self, filename: str) -> str | None:
        source = self.path(filename)
        if not source.exists():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
        target_dir = self.backup_dir / backup_id
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target_dir / filename)
        return backup_id

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def write_data(self, filename: str, data: Any, actor: str, action: str) -> str | None:
        text = data if filename.endswith((".css", ".js")) else self.dump(data)
        return self.write_text(filename, text, actor=actor, action=action)

    def write_text(self, filename: str, text: str, actor: str, action: str) -> str | None:
        self.validate_text(filename, text)
        with self.locked():
            backup_id = self._create_backup(filename)
            self._atomic_write(self.path(filename), text)
            self._audit(actor, action, filename, backup_id)
            self._prune_backups()
        return backup_id

    def _audit(self, actor: str, action: str, filename: str, backup_id: str | None) -> None:
        row = {
            "time": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "filename": filename,
            "backup_id": backup_id,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _backup_path(self, backup_id: str) -> Path:
        if not backup_id or backup_id != Path(backup_id).name or "/" in backup_id or ".." in backup_id:
            raise ConfigError("无效备份 ID。")
        path = self.backup_dir / backup_id
        try:
            path.resolve().relative_to(self.backup_dir.resolve())
        except ValueError as exc:
            raise ConfigError("无效备份 ID。") from exc
        return path

    def list_backups(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.backup_dir.exists():
            return rows
        for directory in sorted(self.backup_dir.iterdir(), reverse=True):
            if not directory.is_dir():
                continue
            file_paths = sorted(x for x in directory.iterdir() if x.is_file())
            files = [x.name for x in file_paths]
            total_bytes = sum(x.stat().st_size for x in file_paths)
            if total_bytes < 1024:
                size_label = f"{total_bytes} B"
            elif total_bytes < 1024 * 1024:
                size_label = f"{total_bytes / 1024:.1f} KB"
            else:
                size_label = f"{total_bytes / (1024 * 1024):.1f} MB"
            rows.append({"id": directory.name, "files": files, "total_bytes": total_bytes, "size_label": size_label})
        return rows

    def restore(self, backup_id: str, filename: str, actor: str) -> None:
        source = self._backup_path(backup_id) / filename
        if not source.exists() or filename not in ALLOWED_FILES:
            raise ConfigError("备份文件不存在。")
        text = source.read_text(encoding="utf-8")
        self.write_text(filename, text, actor=actor, action=f"restore:{backup_id}")

    def delete_backup(self, backup_id: str, actor: str) -> None:
        target = self._backup_path(backup_id)
        if not target.exists() or not target.is_dir():
            raise ConfigError("备份不存在或已经删除。")
        with self.locked():
            shutil.rmtree(target)
            self._audit(actor, f"delete backup:{backup_id}", "backups", None)

    def delete_all_backups(self, actor: str) -> int:
        with self.locked():
            directories = [p for p in self.backup_dir.iterdir() if p.is_dir()]
            for directory in directories:
                shutil.rmtree(directory, ignore_errors=True)
            if directories:
                self._audit(actor, f"delete all backups:{len(directories)}", "backups", None)
            return len(directories)

    def _read_preferences(self) -> dict[str, Any]:
        if not self.preferences_path.exists():
            return {}
        try:
            payload = json.loads(self.preferences_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _widget_schema_sync_defaults(self) -> dict[str, Any]:
        mode = str(getattr(settings, "widget_schema_sync_mode", "interval") or "interval").strip().lower()
        if mode not in {"interval", "daily"}:
            mode = "interval"
        try:
            interval = int(getattr(settings, "widget_schema_sync_interval_hours", 24))
        except (TypeError, ValueError):
            interval = 24
        interval = max(1, min(interval, 720))
        sync_time = str(getattr(settings, "widget_schema_sync_time", "03:00") or "03:00").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", sync_time):
            sync_time = "03:00"
        timezone_name = str(getattr(settings, "widget_schema_timezone", "UTC") or "UTC").strip()
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            timezone_name = "UTC"
        return {
            "auto_sync": bool(getattr(settings, "widget_schema_auto_sync", True)),
            "mode": mode,
            "interval_hours": interval,
            "daily_time": sync_time,
            "timezone": timezone_name,
        }

    def widget_schema_sync_preferences(self) -> dict[str, Any]:
        defaults = self._widget_schema_sync_defaults()
        prefs = self._read_preferences()
        raw = prefs.get("widget_schema_sync")
        if not isinstance(raw, dict):
            return {**defaults, "custom": False}
        result = dict(defaults)
        if "auto_sync" in raw:
            result["auto_sync"] = bool(raw.get("auto_sync"))
        mode = str(raw.get("mode", result["mode"]) or result["mode"]).strip().lower()
        if mode in {"interval", "daily"}:
            result["mode"] = mode
        try:
            result["interval_hours"] = max(1, min(int(raw.get("interval_hours", result["interval_hours"])), 720))
        except (TypeError, ValueError):
            pass
        daily_time = str(raw.get("daily_time", result["daily_time"]) or result["daily_time"]).strip()
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_time):
            result["daily_time"] = daily_time
        timezone_name = str(raw.get("timezone", result["timezone"]) or result["timezone"]).strip()
        try:
            ZoneInfo(timezone_name)
            result["timezone"] = timezone_name
        except (ZoneInfoNotFoundError, ValueError):
            pass
        result["custom"] = True
        return result

    def set_widget_schema_sync_preferences(
        self,
        *,
        auto_sync: bool,
        mode: str,
        interval_hours: int,
        daily_time: str,
        timezone_name: str,
        actor: str,
    ) -> dict[str, Any]:
        mode = str(mode).strip().lower()
        if mode not in {"interval", "daily"}:
            raise ConfigError("自动同步方式必须是固定间隔或每天固定时间。")
        if interval_hours < 1 or interval_hours > 720:
            raise ConfigError("自动同步间隔必须在 1 到 720 小时之间。")
        daily_time = str(daily_time).strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_time):
            raise ConfigError("每天同步时间必须是 HH:MM 格式。")
        timezone_name = str(timezone_name).strip() or "UTC"
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ConfigError("时区无效，请填写 IANA 时区，例如 Asia/Shanghai、Asia/Tokyo 或 UTC。") from exc
        payload = {
            "auto_sync": bool(auto_sync),
            "mode": mode,
            "interval_hours": int(interval_hours),
            "daily_time": daily_time,
            "timezone": timezone_name,
        }
        with self.locked():
            prefs = self._read_preferences()
            prefs["widget_schema_sync"] = payload
            self._atomic_write(self.preferences_path, json.dumps(prefs, ensure_ascii=False, indent=2) + "\n")
            self._audit(actor, f"set widget schema sync:{json.dumps(payload, ensure_ascii=False, sort_keys=True)}", "admin-settings.json", None)
        return {**payload, "custom": True}

    def reset_widget_schema_sync_preferences(self, actor: str) -> dict[str, Any]:
        with self.locked():
            prefs = self._read_preferences()
            prefs.pop("widget_schema_sync", None)
            if prefs:
                self._atomic_write(self.preferences_path, json.dumps(prefs, ensure_ascii=False, indent=2) + "\n")
            elif self.preferences_path.exists():
                self.preferences_path.unlink()
            self._audit(actor, "reset widget schema sync settings", "admin-settings.json", None)
        return self.widget_schema_sync_preferences()

    def backup_limit(self) -> int:
        default = max(1, min(int(settings.backup_limit), 500))
        value = self._read_preferences().get("backup_limit")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, min(parsed, 500))

    def backup_limit_is_custom(self) -> bool:
        return "backup_limit" in self._read_preferences()

    def set_backup_limit(self, limit: int, actor: str) -> int:
        if limit < 1 or limit > 500:
            raise ConfigError("备份保留数量必须在 1 到 500 之间。")
        with self.locked():
            prefs = self._read_preferences()
            prefs["backup_limit"] = int(limit)
            self._atomic_write(
                self.preferences_path,
                json.dumps(prefs, ensure_ascii=False, indent=2) + "\n",
            )
            self._audit(actor, f"set backup limit:{limit}", "admin-settings.json", None)
            self._prune_backups()
        return limit

    def reset_backup_limit(self, actor: str) -> int:
        with self.locked():
            prefs = self._read_preferences()
            prefs.pop("backup_limit", None)
            if prefs:
                self._atomic_write(
                    self.preferences_path,
                    json.dumps(prefs, ensure_ascii=False, indent=2) + "\n",
                )
            elif self.preferences_path.exists():
                self.preferences_path.unlink()
            self._audit(actor, "reset backup limit", "admin-settings.json", None)
            self._prune_backups()
        return self.backup_limit()

    def _prune_backups(self) -> None:
        limit = self.backup_limit()
        dirs = [p for p in self.backup_dir.iterdir() if p.is_dir()]
        dirs.sort(reverse=True)
        for old in dirs[limit:]:
            shutil.rmtree(old, ignore_errors=True)


store = HomepageStore()


def deep_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): deep_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deep_plain(v) for v in value]
    return value
