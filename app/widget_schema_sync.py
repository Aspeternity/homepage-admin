from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ruamel.yaml import YAML

GITHUB_REPO = "gethomepage/homepage"
DOCS_API = "https://api.github.com/repos/gethomepage/homepage/contents/docs/widgets/services"
REGISTRY_RAW = "https://raw.githubusercontent.com/gethomepage/homepage/{ref}/src/widgets/widgets.js"
USER_AGENT = "Homepage-Admin-Widget-Schema-Sync/0.3.3"

_SECRET_HINTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "api-key",
    "accesskey",
    "access_key",
    "privatekey",
    "private_key",
    "clientsecret",
    "client_secret",
    "cookie",
)

_LABELS = {
    "url": "服务地址",
    "username": "用户名",
    "user": "用户",
    "password": "密码",
    "key": "API Key / Key",
    "token": "Token",
    "secret": "Secret",
    "version": "版本",
    "slug": "Slug",
    "site": "站点 / Site",
    "siteid": "Site ID",
    "siteId": "Site ID",
    "env": "Environment ID",
    "node": "节点",
    "host": "主机",
    "port": "端口",
    "namespace": "Namespace",
    "repository": "Repository",
    "project": "Project",
    "organization": "Organization",
    "endpoint": "Endpoint",
    "refreshInterval": "刷新间隔",
}

_NETWORK_TYPES = {
    "adguard", "caddy", "cloudflared", "develancacheui", "fritzbox", "gluetun", "headscale", "mikrotik",
    "netalertx", "nextdns", "npm", "omada", "openwrt", "opnsense", "pangolin", "pfsense", "pihole",
    "swagdashboard", "tailscale", "technitium", "traefik", "unifi", "wgeasy",
}
_STORAGE_TYPES = {
    "backrest", "diskstation", "downloadstation", "filebrowser", "kopia", "openmediavault", "proxmoxbackupserver",
    "qnap", "scrutiny", "truenas", "unifi_drive", "unraid", "urbackup",
}
_MONITOR_TYPES = {
    "apcups", "beszel", "changedetectionio", "checkmk", "gatus", "glances", "grafana", "healthchecks",
    "myspeed", "netdata", "peanut", "prometheus", "prometheusmetric", "speedtest", "uptimekuma", "uptimerobot", "zabbix",
}
_DOWNLOAD_TYPES = {
    "autobrr", "deluge", "flood", "jackett", "jdownloader", "nzbget", "prowlarr", "pyload", "qbittorrent",
    "rutorrent", "sabnzbd", "slskd", "transmission",
}
_MEDIA_TYPES = {
    "atsumeru", "audiobookshelf", "bazarr", "booklore", "calibreweb", "channelsdvrserver", "dispatcharr", "emby",
    "fileflows", "frigate", "hdhomerun", "immich", "jellyfin", "jellystat", "kavita", "komga", "lidarr", "medusa",
    "mylar", "navidrome", "ombi", "photoprism", "plex", "radarr", "readarr", "seerr", "sonarr", "stash", "suwayomi",
    "tautulli", "tdarr", "tracearr", "tubearchivist", "unmanic", "xteve", "yourspotify",
}
_SMARTHOME_TYPES = {
    "esphome", "evcc", "homeassistant", "homebridge", "moonraker", "octoprint", "opendtu", "spoolman",
}
_GAME_TYPES = {"gamedig", "minecraft", "pterodactyl", "romm"}
_DEV_TYPES = {"argocd", "azuredevops", "gitea", "gitlab"}
_INFRA_TYPES = {"arcane", "dockhand", "komodo", "portainer", "proxmox", "watchtower", "whatsupdocker"}
_SECURITY_TYPES = {"authentik", "crowdsec"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _request_text(url: str, timeout: float) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed trusted GitHub endpoints
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"GitHub 返回 HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接 GitHub: {exc.reason}") from exc


def _request_json(url: str, timeout: float) -> Any:
    return json.loads(_request_text(url, timeout))


def _frontmatter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---"):
        return {}
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}
    values: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def _yaml_blocks(markdown: str) -> list[str]:
    return re.findall(r"```ya?ml\s*\n(.*?)```", markdown, flags=re.IGNORECASE | re.DOTALL)


def _find_widget_maps(value: Any) -> list[dict[str, Any]]:
    """Find widget mappings in both short and full services.yaml examples."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        widget = value.get("widget")
        if isinstance(widget, dict):
            found.append(dict(widget))
        for child in value.values():
            found.extend(_find_widget_maps(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_widget_maps(child))
    return found


def _extract_widget_maps(markdown: str) -> list[tuple[dict[str, Any], str]]:
    yaml = YAML(typ="safe")
    results: list[tuple[dict[str, Any], str]] = []
    for block in _yaml_blocks(markdown):
        try:
            parsed = yaml.load(block)
        except Exception:
            parsed = None
        for widget_map in _find_widget_maps(parsed):
            results.append((widget_map, block))
    return results


def _allowed_fields(markdown: str) -> list[str]:
    match = re.search(r"Allowed fields:\s*`?\s*(\[[^\n`]+\])", markdown, flags=re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1)
    try:
        parsed = json.loads(raw.replace("'", '"'))
        if isinstance(parsed, list):
            return [str(value) for value in parsed]
    except json.JSONDecodeError:
        pass
    return re.findall(r"[\"']([^\"']+)[\"']", raw)


def _commented_widget_values(block: str) -> list[tuple[str, Any, str]]:
    """Recover simple optional properties that official examples leave commented out.

    Homepage documentation often demonstrates optional switches as ``# key: value``
    inside the widget block. YAML parsers intentionally discard those lines, so the
    schema generator recovers only direct, simple widget properties here.
    """
    yaml = YAML(typ="safe")
    results: list[tuple[str, Any, str]] = []
    in_widget = False
    widget_indent = 0
    for line in block.splitlines():
        if re.match(r"^\s*widget:\s*$", line):
            in_widget = True
            widget_indent = len(line) - len(line.lstrip())
            continue
        if not in_widget:
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and not stripped.startswith("#") and indent <= widget_indent:
            break

        match = re.match(
            r"^\s*#\s*([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*?)(?:\s+#\s*(.*))?$",
            line,
        )
        if not match or indent != widget_indent + 2:
            continue
        name, raw_value, comment = match.group(1), match.group(2).strip(), (match.group(3) or "").strip()
        if name in {"type", "fields"} or not raw_value:
            continue
        try:
            value = yaml.load(raw_value)
        except Exception:
            value = raw_value
        results.append((name, value, comment or "optional"))
    return results


def _inline_comments(block: str) -> dict[str, str]:
    comments: dict[str, str] = {}
    in_widget = False
    widget_indent = 0
    for line in block.splitlines():
        if re.match(r"^\s*widget:\s*$", line):
            in_widget = True
            widget_indent = len(line) - len(line.lstrip())
            continue
        if not in_widget:
            continue
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= widget_indent:
            break
        match = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_.-]*):.*?(?:\s+#\s*(.*))?$", line)
        if match and indent == widget_indent + 2:
            comments[match.group(1)] = (match.group(2) or "").strip()
    return comments


def _is_secret(name: str) -> bool:
    normalized = name.lower().replace("-", "_")
    if normalized == "key":
        return True
    return any(hint in normalized for hint in _SECRET_HINTS)


def _humanize(name: str) -> str:
    if name in _LABELS:
        return _LABELS[name]
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ").replace("-", " ")
    return " ".join(part.upper() if part.lower() in {"id", "api", "url", "ip", "ssl", "tls"} else part.capitalize() for part in spaced.split())


def _field_kind(name: str, value: Any) -> str:
    if _is_secret(name):
        return "secret"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, (list, dict)):
        return "yaml"
    return "text"


def _placeholder(name: str, value: Any, kind: str) -> str:
    if kind == "secret":
        return "请输入官方文档要求的凭据"
    if value is None:
        return ""
    if kind == "yaml":
        yaml = YAML()
        from io import StringIO
        stream = StringIO()
        yaml.dump(value, stream)
        return stream.getvalue().strip()
    if isinstance(value, bool):
        return "true / false"
    text = str(value)
    if name == "url" and not text.startswith(("http://", "https://")):
        return "http://service.host.or.ip"
    return text


def _category(widget_type: str, label: str) -> str:
    if widget_type in _NETWORK_TYPES:
        return "网络"
    if widget_type in _STORAGE_TYPES:
        return "存储"
    if widget_type in _MONITOR_TYPES:
        return "监控"
    if widget_type in _DOWNLOAD_TYPES:
        return "下载"
    if widget_type in _MEDIA_TYPES:
        return "媒体"
    if widget_type in _SMARTHOME_TYPES:
        return "智能家居"
    if widget_type in _GAME_TYPES:
        return "游戏"
    if widget_type in _DEV_TYPES:
        return "开发"
    if widget_type in _INFRA_TYPES:
        return "基础设施"
    if widget_type in _SECURITY_TYPES:
        return "安全"
    lowered = f"{widget_type} {label}".lower()
    if any(word in lowered for word in ("nas", "backup", "storage", "disk")):
        return "存储"
    if any(word in lowered for word in ("torrent", "download", "nzb", "arr")):
        return "下载"
    if any(word in lowered for word in ("monitor", "status", "metrics", "grafana", "uptime")):
        return "监控"
    return "应用"


def parse_widget_document(markdown: str, slug: str) -> tuple[str, dict[str, Any]] | None:
    front = _frontmatter(markdown)
    examples = _extract_widget_maps(markdown)
    first_map = examples[0][0] if examples else {}
    widget_type = str(first_map.get("type") or slug).strip().lower()
    if not widget_type:
        return None
    label = front.get("title") or _humanize(widget_type)

    field_by_name: dict[str, dict[str, Any]] = {}
    field_order: list[str] = []
    for widget_map, block in examples:
        example_type = str(widget_map.get("type") or widget_type).strip().lower()
        if example_type != widget_type:
            continue
        comments = _inline_comments(block)
        for name, value in widget_map.items():
            name = str(name)
            if name in {"type", "fields"}:
                continue
            kind = _field_kind(name, value)
            comment = comments.get(name, "")
            lower_comment = comment.lower()
            required = not any(token in lower_comment for token in ("optional", "default", "defaults to", "if "))
            candidate: dict[str, Any] = {
                "name": name,
                "label": _humanize(name),
                "kind": kind,
                "required": required,
            }
            placeholder = _placeholder(name, value, kind)
            if placeholder:
                candidate["placeholder"] = placeholder
            if kind == "yaml":
                candidate["rows"] = 6
            if comment:
                candidate["help"] = comment

            if name not in field_by_name:
                field_by_name[name] = candidate
                field_order.append(name)
            else:
                existing = field_by_name[name]
                # If any official example marks the field optional, keep the form optional.
                existing["required"] = bool(existing.get("required")) and required
                if not existing.get("help") and candidate.get("help"):
                    existing["help"] = candidate["help"]
                if not existing.get("placeholder") and candidate.get("placeholder"):
                    existing["placeholder"] = candidate["placeholder"]
                # Prefer structured / secret kinds over a generic text inference.
                priority = {"text": 0, "number": 1, "bool": 2, "yaml": 3, "secret": 4}
                if priority.get(kind, 0) > priority.get(str(existing.get("kind")), 0):
                    existing["kind"] = kind
                    if kind == "yaml":
                        existing["rows"] = 6

    # Include optional fields that are shown commented-out in official examples.
    for _, block in examples:
        for name, value, comment in _commented_widget_values(block):
            if name in field_by_name:
                continue
            kind = _field_kind(name, value)
            candidate = {
                "name": name,
                "label": _humanize(name),
                "kind": kind,
                "required": False,
            }
            placeholder = _placeholder(name, value, kind)
            if placeholder:
                candidate["placeholder"] = placeholder
            if kind == "yaml":
                candidate["rows"] = 6
            if comment and comment != "optional":
                candidate["help"] = comment
            field_by_name[name] = candidate
            field_order.append(name)

    fields = [field_by_name[name] for name in field_order]
    docs_url = f"https://gethomepage.dev/widgets/services/{slug}/"
    return widget_type, {
        "label": label,
        "category": _category(widget_type, label),
        "description": f"Homepage 官方 {label} Service Widget。字段由官方配置示例自动生成。",
        "docs": docs_url,
        "icon": "mdi-puzzle-outline",
        "test": "basic" if any(field["name"] == "url" for field in fields) else "config",
        "allowed_fields": _allowed_fields(markdown),
        "fields": fields,
        "enhanced": True,
        "auto_generated": True,
        "source_mode": "official-auto",
        "source_slug": slug,
    }


def _parse_registry(source: str) -> dict[str, str]:
    match = re.search(r"const\s+widgets\s*=\s*\{(.*?)\};\s*export\s+default", source, flags=re.DOTALL)
    if not match:
        return {}
    aliases: dict[str, str] = {}
    for token in match.group(1).split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            key, target = [part.strip() for part in token.split(":", 1)]
        else:
            key = target = token
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", target):
            aliases[key] = target
    return aliases


def fetch_official_widget_schemas(ref: str = "dev", timeout: float = 8.0, workers: int = 10) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    listing = _request_json(f"{DOCS_API}?ref={ref}", timeout)
    if not isinstance(listing, list):
        raise RuntimeError("GitHub Widget 文档目录返回格式异常。")
    docs = [
        item for item in listing
        if isinstance(item, dict) and str(item.get("name", "")).endswith(".md") and item.get("download_url")
    ]
    if not docs:
        raise RuntimeError("没有从 Homepage 官方仓库发现 Service Widget 文档。")

    schemas: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    def load_doc(item: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        slug = str(item["name"])[:-3]
        markdown = _request_text(str(item["download_url"]), timeout)
        return parse_widget_document(markdown, slug)

    with ThreadPoolExecutor(max_workers=max(2, min(workers, 16))) as executor:
        futures = {executor.submit(load_doc, item): item for item in docs}
        for future in as_completed(futures):
            item = futures[future]
            try:
                parsed = future.result()
                if parsed:
                    type_id, schema = parsed
                    schemas[type_id] = schema
            except Exception as exc:  # keep a partial sync usable
                errors.append(f"{item.get('name')}: {exc}")

    try:
        registry = _parse_registry(_request_text(REGISTRY_RAW.format(ref=ref), timeout))
    except Exception as exc:
        registry = {}
        errors.append(f"widgets.js: {exc}")

    # Include aliases / registry-only widget IDs so the Admin follows Homepage's actual registry,
    # not only the documentation filenames.
    for alias, target in registry.items():
        if alias in schemas:
            continue
        if target in schemas:
            copied = dict(schemas[target])
            copied["label"] = f"{copied.get('label', target)} ({alias})" if alias != target else copied.get("label", target)
            copied["source_mode"] = "official-auto"
            copied["alias_of"] = target if alias != target else ""
            schemas[alias] = copied
        else:
            schemas[alias] = {
                "label": _humanize(alias),
                "category": _category(alias, alias),
                "description": "Homepage 官方 Service Widget；官方注册表已发现该类型。",
                "docs": "https://gethomepage.dev/widgets/services/",
                "icon": "mdi-puzzle-outline",
                "test": "config",
                "allowed_fields": [],
                "fields": [],
                "enhanced": True,
                "auto_generated": True,
                "source_mode": "official-auto",
            }

    meta = {
        "source": GITHUB_REPO,
        "ref": ref,
        "synced_at": utc_now_iso(),
        "document_count": len(docs),
        "widget_count": len(schemas),
        "registry_count": len(registry),
        "error_count": len(errors),
        "errors": errors[:20],
    }
    return dict(sorted(schemas.items())), meta
