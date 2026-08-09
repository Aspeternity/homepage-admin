from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterator

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

    def list_backups(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.backup_dir.exists():
            return rows
        for directory in sorted(self.backup_dir.iterdir(), reverse=True):
            if not directory.is_dir():
                continue
            files = [x.name for x in directory.iterdir() if x.is_file()]
            rows.append({"id": directory.name, "files": sorted(files)})
        return rows

    def restore(self, backup_id: str, filename: str, actor: str) -> None:
        if "/" in backup_id or ".." in backup_id:
            raise ConfigError("无效备份 ID。")
        source = self.backup_dir / backup_id / filename
        if not source.exists() or filename not in ALLOWED_FILES:
            raise ConfigError("备份文件不存在。")
        text = source.read_text(encoding="utf-8")
        self.write_text(filename, text, actor=actor, action=f"restore:{backup_id}")

    def _prune_backups(self) -> None:
        limit = max(settings.backup_limit, 1)
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
