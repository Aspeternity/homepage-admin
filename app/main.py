from __future__ import annotations

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager, suppress
import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .docker_client import (
    DockerDiscoveryClient,
    dedupe_ports,
    first_published_port,
    homepage_labels_to_values,
    infer_icon_and_widget,
    infer_service_description,
    infer_service_profile,
    public_host_from_url,
    recommend_group_index,
)
from .secrets import SECRET_PLACEHOLDER, mask_secrets, restore_masked_secrets
from .security import ensure_csrf, login_limiter, require_auth, verify_csrf, verify_password
from .settings import settings
from .store import ALLOWED_FILES, ConfigError, deep_plain, store
from .proxmox_client import (
    ProxmoxConnection,
    ProxmoxDiscoveryClient,
    ProxmoxDiscoveryError,
    normalize_proxmox_url,
)
from .widget_catalog import (
    WIDGET_CATALOG,
    catalog_categories,
    catalog_field_names,
    catalog_secret_names,
    public_catalog,
    import_widget_schema_json,
    reset_widget_schema_cache,
    start_widget_schema_sync_job,
    sync_widget_schema,
    sync_widget_schema_if_due,
    widget_schema_status,
    widget_schema_sync_job_status,
)
from .widget_tester import WidgetTestError, test_widget

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    # v0.4.3 migrates the old duplicated Docker discovery rows into metadata-only
    # settings. docker.yaml remains the sole connection source of truth.
    try:
        await asyncio.to_thread(store.migrate_legacy_docker_host_preferences, "system")
    except Exception:
        pass

    async def runner() -> None:
        while True:
            try:
                # Runtime preferences are read on every check, so enabling/disabling
                # or changing the schedule in the UI takes effect without a restart.
                await asyncio.to_thread(sync_widget_schema_if_due)
            except Exception:
                # The bundled/cached catalog remains usable. The error is exposed on /widget-schema.
                pass
            await asyncio.sleep(60)

    task = asyncio.create_task(runner(), name="widget-schema-auto-sync")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Homepage Admin", version=__version__, docs_url=None, redoc_url=None, lifespan=app_lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.cookie_secure,
    max_age=60 * 60 * 12,
)
if settings.allowed_hosts and settings.allowed_hosts != ("*",):
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
docker_discovery = DockerDiscoveryClient(settings.docker_discovery_url)
proxmox_discovery = ProxmoxDiscoveryClient()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def auth_guard(request: Request) -> None:
    require_auth(request)


def actor(request: Request) -> str:
    return str(request.session.get("username", "admin"))


def context(request: Request, active: str, **extra: Any) -> dict[str, Any]:
    return {
        "request": request,
        "active": active,
        "csrf": ensure_csrf(request),
        "username": request.session.get("username", ""),
        "homepage_url": settings.homepage_url,
        "version": __version__,
        **extra,
    }


def redirect(path: str, ok: str | None = None, error: str | None = None) -> RedirectResponse:
    parts = []
    if ok:
        parts.append("ok=" + quote(ok))
    if error:
        parts.append("error=" + quote(error))
    if parts:
        path += ("&" if "?" in path else "?") + "&".join(parts)
    return RedirectResponse(path, status_code=303)


def first_pair(mapping: dict[str, Any]) -> tuple[str, Any]:
    if not isinstance(mapping, dict) or not mapping:
        raise ConfigError("配置条目格式无效。")
    key = next(iter(mapping.keys()))
    return str(key), mapping[key]


def groups_view(filename: str) -> list[dict[str, Any]]:
    data = store.load(filename)
    groups: list[dict[str, Any]] = []
    for gi, group_entry in enumerate(data):
        try:
            name, items = first_pair(group_entry)
        except ConfigError:
            name, items = f"无效分组 #{gi + 1}", []
        normalized_items = []
        if isinstance(items, list):
            for ii, entry in enumerate(items):
                try:
                    item_name, details = first_pair(entry)
                    plain_details = deep_plain(details)
                    if filename == "bookmarks.yaml" and isinstance(plain_details, list) and plain_details and isinstance(plain_details[0], dict):
                        meta = plain_details[0]
                    elif isinstance(plain_details, dict):
                        meta = plain_details
                    else:
                        meta = {}
                    normalized_items.append(
                        {
                            "index": ii,
                            "name": item_name,
                            "details": plain_details,
                            "meta": meta,
                            "nested": isinstance(details, list) and filename == "services.yaml",
                        }
                    )
                except ConfigError:
                    normalized_items.append(
                        {"index": ii, "name": f"无效条目 #{ii + 1}", "details": {}, "invalid": True}
                    )
        groups.append({"index": gi, "name": name, "items": normalized_items})
    return groups


def group_names(filename: str) -> list[str]:
    names = []
    for group in store.load(filename):
        try:
            name, _ = first_pair(group)
            names.append(name)
        except ConfigError:
            continue
    return names


def assert_unique_group(name: str, current: str | None = None) -> None:
    names = group_names("services.yaml") + group_names("bookmarks.yaml")
    for existing in names:
        if existing == current:
            continue
        if existing.casefold() == name.casefold():
            raise ConfigError("服务分组和书签分组不能使用相同名称，Homepage 可能隐藏其中一个分组。")


def sync_layout_rename(old: str, new: str, user: str) -> None:
    settings_data = store.load("settings.yaml")
    layout = settings_data.get("layout")
    if not isinstance(layout, dict) or old not in layout or old == new:
        return
    replacement = CommentedMap()
    for key, value in layout.items():
        replacement[new if str(key) == old else key] = value
    settings_data["layout"] = replacement
    store.write_data("settings.yaml", settings_data, user, f"layout rename {old} -> {new}")


def sync_layout_add(name: str, user: str, columns: int) -> None:
    settings_data = store.load("settings.yaml")
    layout = settings_data.get("layout")
    if not isinstance(layout, dict):
        layout = CommentedMap()
        settings_data["layout"] = layout
    if name not in layout:
        layout[name] = CommentedMap({"style": "row", "columns": columns, "useEqualHeights": True})
        store.write_data("settings.yaml", settings_data, user, f"layout add {name}")


def sync_layout_delete(name: str, user: str) -> None:
    settings_data = store.load("settings.yaml")
    layout = settings_data.get("layout")
    if isinstance(layout, dict) and name in layout:
        del layout[name]
        store.write_data("settings.yaml", settings_data, user, f"layout delete {name}")


def sync_layout_swap(first: str, second: str, user: str) -> None:
    settings_data = store.load("settings.yaml")
    layout = settings_data.get("layout")
    if not isinstance(layout, dict) or first not in layout or second not in layout:
        return
    keys = list(layout.keys())
    a, b = keys.index(first), keys.index(second)
    keys[a], keys[b] = keys[b], keys[a]
    settings_data["layout"] = CommentedMap((key, layout[key]) for key in keys)
    store.write_data("settings.yaml", settings_data, user, f"layout swap {first} <-> {second}")


def sync_layout_order(group_order: list[str], user: str) -> None:
    settings_data = store.load("settings.yaml")
    layout = settings_data.get("layout")
    if not isinstance(layout, dict):
        return
    relevant = {name for name in group_order if name in layout}
    if not relevant:
        return
    iterator = iter([name for name in group_order if name in relevant])
    replacement = CommentedMap()
    for key, value in layout.items():
        if str(key) in relevant:
            new_key = next(iterator)
            replacement[new_key] = layout[new_key]
        else:
            replacement[key] = value
    settings_data["layout"] = replacement
    store.write_data("settings.yaml", settings_data, user, "layout reorder")


def configured_docker_containers() -> dict[tuple[str, str], list[dict[str, Any]]]:
    configured: dict[tuple[str, str], list[dict[str, Any]]] = {}
    try:
        data = store.load("services.yaml")
    except ConfigError:
        return configured
    for group_index, group_entry in enumerate(data):
        try:
            group_name, items = first_pair(group_entry)
        except ConfigError:
            continue
        if not isinstance(items, list):
            continue
        for item_index, entry in enumerate(items):
            try:
                service_name, details = first_pair(entry)
            except ConfigError:
                continue
            if isinstance(details, dict) and details.get("container"):
                server_raw = str(details.get("server") or "")
                container_raw = str(details.get("container") or "")
                configured.setdefault((server_raw.casefold(), container_raw.casefold()), []).append({
                    "group": str(group_name),
                    "service": str(service_name),
                    "group_index": group_index,
                    "item_index": item_index,
                    "server": server_raw,
                    "container": container_raw,
                })
    return configured


def docker_server_references(server_name: str) -> list[dict[str, Any]]:
    """Return services that currently depend on a Homepage Docker server."""
    target = str(server_name or "").strip().casefold()
    if not target:
        return []
    try:
        data = store.load("services.yaml")
    except ConfigError:
        return []
    rows: list[dict[str, Any]] = []
    for group_index, group_entry in enumerate(data):
        try:
            group_name, items = first_pair(group_entry)
        except ConfigError:
            continue
        if not isinstance(items, list):
            continue
        for item_index, entry in enumerate(items):
            try:
                service_name, details = first_pair(entry)
            except ConfigError:
                continue
            if not isinstance(details, dict):
                continue
            if str(details.get("server") or "").strip().casefold() != target:
                continue
            rows.append({
                "group_index": group_index,
                "item_index": item_index,
                "group": str(group_name),
                "service": str(service_name),
                "container": str(details.get("container") or ""),
            })
    return rows


def _clear_docker_server_references(data: list[Any], server_name: str) -> int:
    target = str(server_name or "").strip().casefold()
    changed = 0
    for group_entry in data:
        try:
            _, items = first_pair(group_entry)
        except ConfigError:
            continue
        if not isinstance(items, list):
            continue
        for entry in items:
            try:
                _, details = first_pair(entry)
            except ConfigError:
                continue
            if not isinstance(details, dict):
                continue
            if str(details.get("server") or "").strip().casefold() != target:
                continue
            details.pop("server", None)
            details.pop("container", None)
            changed += 1
    return changed


def homepage_docker_servers() -> dict[str, dict[str, Any]]:
    try:
        data = store.load("docker.yaml")
    except ConfigError:
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw_name, raw_cfg in data.items():
        name = str(raw_name)
        if not isinstance(raw_cfg, dict):
            continue
        cfg = raw_cfg
        info: dict[str, Any] = {
            "name": name,
            "mode": "none",
            "host": "",
            "port": "",
            "protocol": "http",
            "url": "",
            "socket": "",
            "has_headers": isinstance(cfg.get("headers"), dict) and bool(cfg.get("headers")),
            "has_tls": isinstance(cfg.get("tls"), dict) and bool(cfg.get("tls")),
            "raw": cfg,
        }
        if cfg.get("socket"):
            info.update({"mode": "socket", "socket": str(cfg.get("socket"))})
        elif cfg.get("host"):
            host = str(cfg.get("host"))
            protocol = str(cfg.get("protocol") or ("https" if info["has_tls"] else "http")).lower()
            if protocol not in {"http", "https"}:
                protocol = "http"
            try:
                port = int(cfg.get("port", 443 if protocol == "https" else 2375))
            except (TypeError, ValueError):
                port = 443 if protocol == "https" else 2375
            display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
            info.update({
                "mode": "remote",
                "host": host,
                "port": port,
                "protocol": protocol,
                "url": f"{protocol}://{display_host}:{port}",
            })
        result[name] = info
    return result


def first_docker_server_name() -> str:
    if settings.docker_server_name:
        return settings.docker_server_name
    servers = homepage_docker_servers()
    return next(iter(servers.keys()), "")


def docker_server_info(name: str | None = None) -> dict[str, Any]:
    server_name = name or first_docker_server_name()
    info: dict[str, Any] = {
        "name": server_name,
        "mode": "none",
        "host": "",
        "port": "",
        "socket": "",
        "recommended": False,
    }
    server = homepage_docker_servers().get(server_name)
    if not server:
        return info
    info.update({k: v for k, v in server.items() if k != "raw"})
    if server.get("mode") == "remote":
        info["recommended"] = (
            str(server.get("host")) == settings.homepage_docker_proxy_host
            and int(server.get("port") or 0) == settings.homepage_docker_proxy_port
        )
        info["mode"] = "proxy" if info["recommended"] else "remote"
    return info


def _docker_host_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:28] or "docker"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:7]
    return f"{prefix}-{slug}-{digest}"


def _docker_client_from_url_and_yaml(url: str, server: dict[str, Any] | None = None) -> DockerDiscoveryClient | None:
    if not url:
        return None
    raw = server.get("raw") if isinstance(server, dict) and isinstance(server.get("raw"), dict) else {}
    headers = raw.get("headers") if isinstance(raw.get("headers"), dict) else {}
    safe_headers = {str(k): str(v) for k, v in headers.items()}
    verify: bool | str = True
    cert: str | tuple[str, str] | None = None
    tls = raw.get("tls") if isinstance(raw.get("tls"), dict) else {}
    if tls:
        ca = str(tls.get("caFile") or "").strip()
        cert_file = str(tls.get("certFile") or "").strip()
        key_file = str(tls.get("keyFile") or "").strip()
        if ca:
            verify = str((settings.config_dir / ca).resolve())
        if cert_file and key_file:
            cert = (str((settings.config_dir / cert_file).resolve()), str((settings.config_dir / key_file).resolve()))
    return DockerDiscoveryClient(str(url), headers=safe_headers, verify=verify, cert=cert)


def _docker_client_from_yaml(server: dict[str, Any]) -> DockerDiscoveryClient | None:
    if server.get("mode") != "remote" or not server.get("url"):
        return None
    return _docker_client_from_url_and_yaml(str(server.get("url")), server)


def docker_discovery_hosts() -> list[dict[str, Any]]:
    """Build Docker discovery hosts from docker.yaml plus Admin-only metadata.

    docker.yaml is the single source of truth for server/host/port/socket/TLS/headers.
    admin-settings.json stores only display_name, public_host and an optional
    discovery_override used when Admin cannot reach docker.yaml's endpoint directly.
    """
    store.migrate_legacy_docker_host_preferences("system")
    servers = homepage_docker_servers()
    metadata = store.docker_host_metadata()
    metadata_by_server = {name.casefold(): value for name, value in metadata.items()}
    hosts: list[dict[str, Any]] = []
    first_server = first_docker_server_name()
    env_url = (settings.docker_discovery_url or docker_discovery.base_url).rstrip("/")

    for server_name, server in servers.items():
        meta = metadata_by_server.get(server_name.casefold(), {})
        override = str(meta.get("discovery_override") or "").strip().rstrip("/")
        yaml_url = str(server.get("url") or "").strip().rstrip("/")
        discovery_url = override or yaml_url
        discovery_via_env = False

        # Compatibility for a socket-only first server: the deployment-level
        # DOCKER_DISCOVERY_URL can still provide a read-only proxy without being
        # copied into Admin settings. New deployments should prefer a remote
        # docker.yaml server or an explicit discovery_override metadata field.
        if not discovery_url and server_name == first_server and env_url:
            discovery_url = env_url
            discovery_via_env = True

        client: DockerDiscoveryClient | None = None
        if discovery_url:
            if discovery_via_env and discovery_url == docker_discovery.base_url.rstrip("/"):
                client = docker_discovery
            elif override and server.get("mode") == "socket":
                client = DockerDiscoveryClient(discovery_url)
            else:
                client = _docker_client_from_url_and_yaml(discovery_url, server)

        public_host = str(meta.get("public_host") or "").strip()
        if not public_host:
            if server_name == first_server and settings.docker_public_host:
                public_host = settings.docker_public_host
            elif server.get("host"):
                public_host = str(server.get("host") or "")

        hosts.append({
            "id": _docker_host_id("yaml", server_name),
            "name": str(meta.get("display_name") or server_name),
            "url": discovery_url,
            "core_url": yaml_url,
            "discovery_override": override,
            "homepage_server": server_name,
            "public_host": public_host,
            "source": "docker.yaml",
            "source_label": "docker.yaml",
            "editable": True,
            "manageable": True,
            "has_metadata": bool(meta),
            "has_custom": bool(meta),  # compatibility with older delete tests/routes
            "custom_id": server_name if meta else "",
            "has_yaml": True,
            "yaml_configured": True,
            "yaml_mode": server.get("mode"),
            "socket": str(server.get("socket") or ""),
            "client": client,
            "has_headers": bool(server.get("has_headers")),
            "has_tls": bool(server.get("has_tls")),
            "discovery_via_env": discovery_via_env,
        })

    # Deployment compatibility only: if docker.yaml is empty but an environment
    # endpoint exists, show it as a bootstrap connection. Saving it through the
    # host manager will create docker.yaml and end this fallback state.
    if not hosts and env_url:
        server_name = settings.docker_server_name or "local-docker"
        hosts.append({
            "id": "env-default",
            "name": server_name,
            "url": env_url,
            "core_url": "",
            "discovery_override": "",
            "homepage_server": server_name,
            "public_host": settings.docker_public_host,
            "source": "environment",
            "source_label": "部署环境回退",
            "editable": False,
            "manageable": False,
            "has_metadata": False,
            "has_custom": False,
            "custom_id": "",
            "has_yaml": False,
            "yaml_configured": False,
            "yaml_mode": "none",
            "client": docker_discovery if env_url == docker_discovery.base_url.rstrip("/") else DockerDiscoveryClient(env_url),
            "discovery_via_env": True,
        })
    return hosts


def docker_discovery_host(host_id: str | None = None) -> dict[str, Any] | None:
    hosts = docker_discovery_hosts()
    if host_id:
        for host in hosts:
            if str(host.get("id")) == host_id:
                return host
    return hosts[0] if hosts else None


def docker_host_public_host(host: dict[str, Any]) -> str:
    explicit = str(host.get("public_host") or "").strip()
    if explicit:
        return explicit
    url_host = public_host_from_url(str(host.get("url") or ""))
    if url_host and url_host not in {settings.homepage_docker_proxy_host, "localhost"}:
        return url_host
    return settings.docker_public_host or public_host_from_url(settings.homepage_url)


def sync_custom_docker_host_to_homepage(host: dict[str, str], user: str) -> bool:
    data = store.load("docker.yaml")
    if not isinstance(data, dict):
        raise ConfigError("docker.yaml 必须是对象映射。")
    server_name = str(host.get("homepage_server") or "").strip()
    parsed = urlparse(str(host.get("url") or ""))
    if not server_name or not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise ConfigError("Docker 主机配置不完整。")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    expected_protocol = "https" if parsed.scheme == "https" else "http"
    existing = data.get(server_name)
    if existing is not None:
        if not isinstance(existing, dict):
            raise ConfigError(f"docker.yaml 中的 {server_name} 不是有效映射。")
        current_host = str(existing.get("host") or "")
        try:
            current_port = int(existing.get("port", 443 if str(existing.get("protocol") or "http") == "https" else 2375))
        except (TypeError, ValueError):
            current_port = -1
        current_protocol = str(existing.get("protocol") or ("https" if existing.get("tls") else "http")).lower()
        if current_host != parsed.hostname or current_port != port or current_protocol != expected_protocol:
            raise ConfigError(
                f"docker.yaml 已存在同名 Server“{server_name}”，但连接地址不同。为避免覆盖现有 TLS/Header 配置，请先在高级编辑中确认。"
            )
        return False
    cfg = CommentedMap({"host": parsed.hostname, "port": port})
    if expected_protocol == "https":
        cfg["protocol"] = "https"
    data[server_name] = cfg
    store.write_data("docker.yaml", data, user, f"add docker server {server_name} from discovery host")
    return True


def upsert_homepage_docker_server_from_discovery(
    host: dict[str, str],
    user: str,
    *,
    original_server: str = "",
) -> tuple[bool, bool]:
    """Create/update/rename a remote docker.yaml server from the unified host form.

    docker.yaml remains the single source of truth. Existing headers, TLS blocks
    and unknown future Homepage keys are preserved. A rename is allowed only
    after the caller has verified the old Server has no service references.
    Returns (created, renamed).
    """
    data = store.load("docker.yaml")
    if not isinstance(data, dict):
        raise ConfigError("docker.yaml 必须是对象映射。")
    server_name = str(host.get("homepage_server") or "").strip()
    parsed = urlparse(str(host.get("url") or "").strip())
    if not server_name or not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise ConfigError("Docker 主机配置不完整。")
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise ConfigError("Docker API URL 端口无效。") from exc
    port = parsed_port or (443 if parsed.scheme == "https" else 80)
    protocol = parsed.scheme

    old_name = str(original_server or "").strip()
    renamed = bool(old_name and old_name != server_name)
    if renamed:
        if old_name not in data:
            raise ConfigError(f"原 Docker Server“{old_name}”已不存在，请刷新页面后重试。")
        collision = next((str(key) for key in data.keys() if str(key).casefold() == server_name.casefold() and str(key) != old_name), "")
        if collision:
            raise ConfigError(f"Docker Server“{server_name}”已存在，不能重命名为相同名称。")
        keys = list(data.keys())
        index = keys.index(old_name)
        cfg = data.pop(old_name)
        if isinstance(data, CommentedMap):
            data.insert(index, server_name, cfg)
        else:
            rows = list(data.items())
            rows.insert(index, (server_name, cfg))
            data = CommentedMap(rows)

    created = server_name not in data
    if created:
        cfg = CommentedMap()
        data[server_name] = cfg
    else:
        cfg = data[server_name]
        if not isinstance(cfg, dict):
            raise ConfigError(f"docker.yaml 中的 {server_name} 不是有效映射。")

    # A unified host form represents a remote HTTP(S) endpoint. Remove an old
    # socket key when the user explicitly converts the host to remote mode.
    cfg.pop("socket", None)
    cfg["host"] = parsed.hostname
    cfg["port"] = port
    cfg["protocol"] = protocol

    action = f"rename docker server {old_name} -> {server_name}" if renamed else (f"add docker server {server_name}" if created else f"update docker server {server_name}")
    store.write_data("docker.yaml", data, user, action)
    return created, renamed


def update_homepage_docker_server(server_name: str, payload: dict[str, str], user: str) -> None:
    data = store.load("docker.yaml")
    if not isinstance(data, dict):
        raise ConfigError("docker.yaml 必须是对象映射。")
    if server_name not in data or not isinstance(data.get(server_name), dict):
        raise ConfigError(f"docker.yaml 中不存在 Server“{server_name}”。")
    mode = str(payload.get("mode") or "remote").strip().lower()
    cfg = data[server_name]
    if mode == "socket":
        socket_path = str(payload.get("socket") or "").strip()
        if not socket_path.startswith("/") or any(ch in socket_path for ch in "\r\n"):
            raise ConfigError("Socket 路径必须是绝对路径，例如 /var/run/docker.sock。")
        cfg["socket"] = socket_path
        cfg.pop("host", None)
        cfg.pop("port", None)
        cfg.pop("protocol", None)
    elif mode == "remote":
        host = str(payload.get("host") or "").strip()
        if not host or "://" in host or any(ch.isspace() for ch in host) or any(ch in host for ch in "/?#"):
            raise ConfigError("Docker Host 只能填写主机名或 IP，不要包含协议、路径或空格。")
        try:
            port = int(str(payload.get("port") or "2375"))
        except ValueError as exc:
            raise ConfigError("Docker Port 必须是数字。") from exc
        if port < 1 or port > 65535:
            raise ConfigError("Docker Port 必须在 1-65535 之间。")
        protocol = str(payload.get("protocol") or "http").strip().lower()
        if protocol not in {"http", "https"}:
            raise ConfigError("Docker Protocol 只能是 http 或 https。")
        cfg["host"] = host
        cfg["port"] = port
        cfg["protocol"] = protocol
        cfg.pop("socket", None)
    else:
        raise ConfigError("Docker Server 模式必须是 remote 或 socket。")
    # Preserve headers, tls and any future Homepage keys that the visual editor does not understand.
    store.write_data("docker.yaml", data, user, f"edit docker server {server_name}")


def recommended_import_group(names: list[str]) -> int:
    if not names:
        return 0
    less_useful = {"widgets", "widget", "状态面板", "status"}
    for index, name in enumerate(names):
        if name.strip().casefold() not in less_useful:
            return index
    return 0


def container_role(container: dict[str, Any]) -> str:
    name = str(container.get("name", "")).casefold()
    image = str(container.get("image", "")).casefold()
    if name == "homepage-admin":
        return "当前管理后台"
    if "gethomepage/homepage" in image or name == "homepage":
        return "Homepage 本体"
    if name in {"homepage-docker-proxy", "homepage-admin-docker-proxy", "docker-proxy"}:
        return "Docker 只读代理"
    return ""


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    if request.session.get("authenticated"):
        return RedirectResponse("/services", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": request.query_params.get("error"), "version": __version__},
    )


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request) -> HTMLResponse:
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    ip = request.client.host if request.client else "unknown"
    if not login_limiter.allowed(ip):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "尝试次数过多，请稍后再试。", "version": __version__},
            status_code=429,
        )
    if username != settings.username or not verify_password(password):
        login_limiter.record_failure(ip)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "用户名或密码错误。", "version": __version__},
            status_code=401,
        )
    login_limiter.clear(ip)
    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = username
    ensure_csrf(request)
    return RedirectResponse("/services", status_code=303)


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def index(_: None = Depends(auth_guard)) -> RedirectResponse:
    return RedirectResponse("/services", status_code=303)


@app.get("/services", response_class=HTMLResponse)
def services_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        groups = groups_view("services.yaml")
    except ConfigError as exc:
        groups = []
        error = str(exc)
    else:
        error = request.query_params.get("error")
    return templates.TemplateResponse(
        request,
        "items.html",
        context(
            request,
            "services",
            kind="services",
            title="服务管理",
            subtitle="管理 services.yaml 中的服务、分组、状态监控和 Widget。",
            groups=groups,
            ok=request.query_params.get("ok"),
            error=error,
        ),
    )


@app.get("/bookmarks", response_class=HTMLResponse)
def bookmarks_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        groups = groups_view("bookmarks.yaml")
    except ConfigError as exc:
        groups = []
        error = str(exc)
    else:
        error = request.query_params.get("error")
    return templates.TemplateResponse(
        request,
        "items.html",
        context(
            request,
            "bookmarks",
            kind="bookmarks",
            title="书签管理",
            subtitle="管理 bookmarks.yaml 中的网站书签、快捷链接和分类。",
            groups=groups,
            ok=request.query_params.get("ok"),
            error=error,
        ),
    )


@app.post("/{kind}/group/create")
async def create_group(kind: str, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    name = str(form.get("name", "")).strip()
    target = f"/{kind}"
    try:
        if not name:
            raise ConfigError("分组名称不能为空。")
        assert_unique_group(name)
        filename = f"{kind}.yaml"
        data = store.load(filename)
        data.append(CommentedMap({name: CommentedSeq()}))
        store.write_data(filename, data, actor(request), f"create group {name}")
        sync_layout_add(name, actor(request), 4 if kind == "services" else 5)
        return redirect(target, ok=f"已创建分组“{name}”。")
    except ConfigError as exc:
        return redirect(target, error=str(exc))


@app.post("/{kind}/group/{group_index}/rename")
async def rename_group(kind: str, group_index: int, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    new_name = str(form.get("name", "")).strip()
    target = f"/{kind}"
    try:
        filename = f"{kind}.yaml"
        data = store.load(filename)
        old_name, items = first_pair(data[group_index])
        if not new_name:
            raise ConfigError("分组名称不能为空。")
        assert_unique_group(new_name, current=old_name)
        data[group_index] = CommentedMap({new_name: items})
        store.write_data(filename, data, actor(request), f"rename group {old_name} -> {new_name}")
        sync_layout_rename(old_name, new_name, actor(request))
        return redirect(target, ok=f"已将分组重命名为“{new_name}”。")
    except (ConfigError, IndexError) as exc:
        return redirect(target, error=str(exc))


@app.post("/{kind}/group/{group_index}/delete")
async def delete_group(kind: str, group_index: int, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    target = f"/{kind}"
    try:
        filename = f"{kind}.yaml"
        data = store.load(filename)
        name, items = first_pair(data[group_index])
        if items and str(form.get("confirm", "")) != "DELETE":
            raise ConfigError("该分组不是空的。请输入 DELETE 确认删除整个分组。")
        del data[group_index]
        store.write_data(filename, data, actor(request), f"delete group {name}")
        sync_layout_delete(name, actor(request))
        return redirect(target, ok=f"已删除分组“{name}”。")
    except (ConfigError, IndexError) as exc:
        return redirect(target, error=str(exc))


@app.post("/{kind}/group/{group_index}/move")
async def move_group(kind: str, group_index: int, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    direction = str(form.get("direction", ""))
    target = f"/{kind}"
    try:
        filename = f"{kind}.yaml"
        data = store.load(filename)
        destination = group_index - 1 if direction == "up" else group_index + 1
        if destination < 0 or destination >= len(data):
            return redirect(target)
        first_name, _ = first_pair(data[group_index])
        second_name, _ = first_pair(data[destination])
        data[group_index], data[destination] = data[destination], data[group_index]
        store.write_data(filename, data, actor(request), f"move group {group_index} {direction}")
        sync_layout_swap(first_name, second_name, actor(request))
        return redirect(target, ok="分组顺序已更新。")
    except ConfigError as exc:
        return redirect(target, error=str(exc))


def empty_service_values() -> dict[str, Any]:
    return {
        "name": "",
        "icon": "",
        "href": "",
        "description": "",
        "target": "",
        "siteMonitor": "",
        "ping": "",
        "server": "",
        "container": "",
        "proxmoxNode": "",
        "proxmoxVMID": "",
        "proxmoxType": "",
        "widgets": [],
        # Legacy mirror used by the Docker import wizard and old links.
        "widget_type": "",
        "widget_fields": {},
        "widget_secret_saved": {},
        "widget_extra": "",
        "extra": "",
        "multiple_widgets": False,
    }


def _widget_form_value(widget: dict[str, Any], original_index: int) -> dict[str, Any]:
    widget_type = str(widget.get("type", ""))
    values: dict[str, Any] = {
        "type": widget_type,
        "fields": {},
        "secret_saved": {},
        "selected_fields": list(widget.get("fields") or []) if isinstance(widget.get("fields"), list) else [],
        "extra": "",
        "original_index": original_index,
    }
    known_widget = catalog_field_names(widget_type)
    for key in known_widget:
        if key == "fields" or key not in widget:
            continue
        if key in catalog_secret_names(widget_type):
            values["secret_saved"][key] = bool(widget.get(key))
            continue
        field_schema = next(
            (f for f in WIDGET_CATALOG.get(widget_type, {}).get("fields", []) if f.get("name") == key),
            {},
        )
        value = widget.get(key)
        if field_schema.get("kind") == "yaml":
            values["fields"][key] = store.dump_fragment(value) if value not in (None, "") else ""
        else:
            values["fields"][key] = value
    extra = CommentedMap(
        (k, copy.deepcopy(v)) for k, v in widget.items() if k not in known_widget | {"type"}
    )
    values["extra"] = store.dump_fragment(mask_secrets(extra)) if extra else ""
    return values


def service_form_values(data: list[Any], group_index: int, item_index: int | None) -> dict[str, Any]:
    values = empty_service_values()
    if item_index is None:
        return values
    _, items = first_pair(data[group_index])
    name, details = first_pair(items[item_index])
    if not isinstance(details, dict):
        raise ConfigError("嵌套分组暂不支持表单编辑，请使用高级 YAML 编辑器。")
    values["name"] = name
    known = {
        "icon", "href", "description", "target", "siteMonitor", "ping", "server", "container",
        "proxmoxNode", "proxmoxVMID", "proxmoxType",
    }
    for key in known:
        values[key] = details.get(key, "")

    widgets_raw: list[dict[str, Any]] = []
    if isinstance(details.get("widgets"), list):
        widgets_raw = [widget for widget in details.get("widgets", []) if isinstance(widget, dict)]
    elif isinstance(details.get("widget"), dict):
        widgets_raw = [details["widget"]]
    values["widgets"] = [_widget_form_value(widget, index) for index, widget in enumerate(widgets_raw)]
    values["multiple_widgets"] = len(values["widgets"]) > 1
    if values["widgets"]:
        first = values["widgets"][0]
        values["widget_type"] = first["type"]
        values["widget_fields"] = first["fields"]
        values["widget_secret_saved"] = first["secret_saved"]
        values["widget_extra"] = first["extra"]

    extra = CommentedMap(
        (k, copy.deepcopy(v))
        for k, v in details.items()
        if k not in known | {"widget", "widgets"}
    )
    values["extra"] = store.dump_fragment(mask_secrets(extra)) if extra else ""
    return values


def _ensure_widget_values(values: dict[str, Any]) -> None:
    """Convert Docker/import legacy first-widget values into v0.3.0 widgets list."""
    if values.get("widgets"):
        return
    widget_type = str(values.get("widget_type") or "").strip()
    if not widget_type:
        return
    values["widgets"] = [
        {
            "type": widget_type,
            "fields": copy.deepcopy(values.get("widget_fields") or {}),
            "secret_saved": copy.deepcopy(values.get("widget_secret_saved") or {}),
            "selected_fields": [],
            "extra": values.get("widget_extra", ""),
            "original_index": -1,
        }
    ]


def service_form_docker_hosts() -> list[dict[str, Any]]:
    """Return non-sensitive Docker discovery choices for the service editor."""
    rows: list[dict[str, Any]] = []
    for host in docker_discovery_hosts():
        rows.append({
            "id": str(host.get("id") or ""),
            "name": str(host.get("name") or host.get("homepage_server") or "Docker"),
            "homepage_server": str(host.get("homepage_server") or ""),
            "discoverable": bool(host.get("client") and host.get("url") and host.get("yaml_configured")),
        })
    return rows


def service_form_proxmox_connections() -> list[dict[str, str]]:
    """Return Proxmox connection names without exposing tokens/secrets."""
    try:
        connections = _proxmox_connections()
    except ConfigError:
        return []
    return [{"name": name, "url": normalize_proxmox_url(connection.url)} for name, connection in connections.items()]


def render_service_form(
    request: Request,
    *,
    mode: str,
    group_index: int,
    item_index: int | None,
    groups: list[str],
    values: dict[str, Any],
    error: str | None = None,
    docker_source: str | None = None,
) -> HTMLResponse:
    _ensure_widget_values(values)
    docker_hosts = service_form_docker_hosts()
    proxmox_connections = service_form_proxmox_connections()
    return templates.TemplateResponse(
        request,
        "service_form.html",
        context(
            request,
            "services",
            mode=mode,
            group_index=group_index,
            item_index=item_index,
            groups=groups,
            values=values,
            error=error,
            widget_catalog=WIDGET_CATALOG,
            widget_catalog_json=json.dumps(public_catalog(), ensure_ascii=False),
            docker_source=docker_source,
            docker_hosts=docker_hosts,
            docker_integration_available=any(item.get("discoverable") for item in docker_hosts),
            proxmox_connections=proxmox_connections,
            proxmox_integration_available=bool(proxmox_connections),
        ),
    )


@app.get("/services/item/new", response_class=HTMLResponse)
def new_service(
    request: Request,
    group: int = 0,
    widget: str = "",
    proxmox_node: str = "",
    proxmox_vmid: str = "",
    proxmox_type: str = "",
    name: str = "",
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    try:
        data = store.load("services.yaml")
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        group = min(max(group, 0), len(names) - 1)
        values = service_form_values(data, group, None)
        if widget and widget in WIDGET_CATALOG:
            values["widgets"] = [{"type": widget, "fields": {}, "secret_saved": {}, "selected_fields": [], "extra": "", "original_index": -1}]
        if name:
            values["name"] = name
        if proxmox_node and proxmox_vmid:
            values["proxmoxNode"] = proxmox_node
            values["proxmoxVMID"] = proxmox_vmid
            values["proxmoxType"] = proxmox_type or "qemu"
        error = None
    except ConfigError as exc:
        names, values, error = [], {}, str(exc)
    return render_service_form(
        request,
        mode="new",
        group_index=group,
        item_index=None,
        groups=names,
        values=values,
        error=error,
    )


@app.get("/services/item/{group_index}/{item_index}/edit", response_class=HTMLResponse)
def edit_service(
    request: Request, group_index: int, item_index: int, _: None = Depends(auth_guard)
) -> HTMLResponse:
    try:
        data = store.load("services.yaml")
        values = service_form_values(data, group_index, item_index)
        names = group_names("services.yaml")
        error = None
    except (ConfigError, IndexError) as exc:
        return redirect("/services", error=str(exc))
    return render_service_form(
        request,
        mode="edit",
        group_index=group_index,
        item_index=item_index,
        groups=names,
        values=values,
        error=error,
    )


@app.get("/api/docker/host/{host_id}/service-options")
def docker_service_options(host_id: str, _: None = Depends(auth_guard)) -> JSONResponse:
    host = docker_discovery_host(host_id)
    if not host:
        return JSONResponse({"ok": False, "error": "Docker 主机不存在，请刷新页面。"}, status_code=404)
    client = host.get("client")
    if not isinstance(client, DockerDiscoveryClient):
        return JSONResponse({"ok": False, "error": "该 Docker 主机当前没有可用于发现容器的连接地址。"}, status_code=400)
    try:
        containers = client.list_containers()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"读取 Docker 容器失败：{exc}"}, status_code=502)
    payload = [
        {
            "id": str(item.get("id") or ""),
            "name": str(item.get("name") or ""),
            "image": str(item.get("image") or ""),
            "state": str(item.get("state") or "unknown"),
        }
        for item in containers
        if str(item.get("name") or "").strip()
    ]
    return JSONResponse({
        "ok": True,
        "host": {
            "id": str(host.get("id") or ""),
            "name": str(host.get("name") or host.get("homepage_server") or "Docker"),
            "homepage_server": str(host.get("homepage_server") or ""),
        },
        "containers": payload,
    })


@app.get("/api/proxmox/service-options")
async def proxmox_service_options(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    server = str(request.query_params.get("server") or "").strip()
    try:
        connections = _proxmox_connections()
    except ConfigError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    connection = connections.get(server)
    if not connection:
        return JSONResponse({"ok": False, "error": "Proxmox 连接不存在，请刷新页面。"}, status_code=404)
    try:
        resources = await proxmox_discovery.discover(connection)
    except ProxmoxDiscoveryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
    return JSONResponse({
        "ok": True,
        "server": server,
        "resources": [
            {
                "name": str(item.get("name") or f"VM {item.get('vmid', '')}"),
                "node": str(item.get("node") or server),
                "vmid": int(item.get("vmid") or 0),
                "type": str(item.get("type") or "qemu"),
                "status": str(item.get("status") or "unknown"),
                "connection_available": str(item.get("node") or server) in connections,
            }
            for item in resources
        ],
    })


def _coerce_widget_field(kind: str, raw: str) -> Any:
    if kind == "bool":
        if raw == "":
            return None
        return raw.lower() == "true"
    if kind == "number":
        if raw == "":
            return None
        value = raw.strip()
        try:
            if re.fullmatch(r"[+-]?\d+", value):
                return int(value)
            return float(value)
        except ValueError as exc:
            raise ConfigError(f"Widget 数字字段必须是有效数字：{raw}") from exc
    if kind == "yaml":
        if not raw.strip():
            return None
        return store.parse_any(raw)
    return raw.strip() or None


def _old_widgets(details: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(details.get("widgets"), list):
        return [item for item in details["widgets"] if isinstance(item, dict)]
    if isinstance(details.get("widget"), dict):
        return [details["widget"]]
    return []


def _parse_widget_slot(form: Any, slot: str, old_widgets: list[dict[str, Any]], *, legacy: bool = False) -> CommentedMap | None:
    prefix = "" if legacy else f"widgets_{slot}_"
    type_key = "widget_type" if legacy else prefix + "type"
    widget_type = str(form.get(type_key, "")).strip().lower()
    if not widget_type:
        return None
    schema = WIDGET_CATALOG.get(widget_type, {})
    schema_fields = list(schema.get("fields", []))
    if not any(field.get("name") == "url" for field in schema_fields):
        schema_fields.insert(0, {"name": "url", "kind": "text"})

    original_index = -1
    if not legacy:
        try:
            original_index = int(str(form.get(prefix + "original_index", "-1")))
        except ValueError:
            original_index = -1
    elif old_widgets:
        original_index = 0
    old_widget = old_widgets[original_index] if 0 <= original_index < len(old_widgets) else {}
    old_type = str(old_widget.get("type", "")) if isinstance(old_widget, dict) else ""

    widget = CommentedMap({"type": widget_type})
    for field in schema_fields:
        field_name = str(field.get("name", ""))
        if not field_name:
            continue
        kind = str(field.get("kind", "text"))
        form_key = f"widget_field_{field_name}" if legacy else prefix + f"field_{field_name}"
        raw = str(form.get(form_key, ""))
        if kind == "secret":
            if raw.strip():
                widget[field_name] = raw.strip()
            elif old_type == widget_type and field_name in old_widget:
                widget[field_name] = copy.deepcopy(old_widget[field_name])
            continue
        value = _coerce_widget_field(kind, raw)
        if value is not None:
            widget[field_name] = value

    if not legacy:
        selected = [str(value) for value in form.getlist(prefix + "fields") if str(value).strip()]
    else:
        selected = [str(value) for value in form.getlist("widget_fields_selection") if str(value).strip()]
    allowed = set(schema.get("allowed_fields") or [])
    selected = [value for value in selected if not allowed or value in allowed]
    if selected:
        widget["fields"] = CommentedSeq(selected[:4])

    extra_key = "widget_extra" if legacy else prefix + "extra"
    widget_extra = store.parse_fragment(str(form.get(extra_key, "")), dict)
    if old_type == widget_type and old_widget:
        try:
            widget_extra = restore_masked_secrets(widget_extra, old_widget)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    for key, value in widget_extra.items():
        if key not in widget and key != "type":
            widget[key] = value
    return widget


def _build_service_change(form: Any, group_index: int, item_index: int | None) -> tuple[list[Any], str]:
    data = store.load("services.yaml")
    target_group = int(str(form.get("group_index", group_index)))
    if target_group < 0 or target_group >= len(data):
        raise ConfigError("目标分组不存在。")
    name = str(form.get("name", "")).strip()
    if not name:
        raise ConfigError("服务名称不能为空。")

    old_details: dict[str, Any] = {}
    if item_index is not None:
        _, old_items = first_pair(data[group_index])
        _, loaded_old_details = first_pair(old_items[item_index])
        if isinstance(loaded_old_details, dict):
            old_details = loaded_old_details
    old_widgets = _old_widgets(old_details)

    details = CommentedMap()
    field_order = [
        "icon", "href", "description", "target", "siteMonitor", "ping", "server", "container",
        "proxmoxNode", "proxmoxVMID", "proxmoxType",
    ]
    for key in field_order:
        value = str(form.get(key, "")).strip()
        if value:
            if key == "proxmoxVMID":
                try:
                    details[key] = int(value)
                except ValueError as exc:
                    raise ConfigError("Proxmox VMID 必须是整数。") from exc
            else:
                details[key] = value

    extra = store.parse_fragment(str(form.get("extra", "")), dict)
    if old_details:
        try:
            extra = restore_masked_secrets(extra, old_details)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    for key, value in extra.items():
        if key in details or key in {"widget", "widgets"}:
            continue
        details[key] = value

    slots = [part for part in str(form.get("widget_slots", "")).split(",") if part.strip()]
    widgets: list[CommentedMap] = []
    if slots:
        for slot in slots:
            parsed = _parse_widget_slot(form, slot.strip(), old_widgets)
            if parsed is not None:
                widgets.append(parsed)
    elif str(form.get("widget_type", "")).strip():
        # Backwards compatible with v0.2.x form submissions and external tests.
        parsed = _parse_widget_slot(form, "legacy", old_widgets, legacy=True)
        if parsed is not None:
            widgets.append(parsed)

    if len(widgets) == 1:
        details["widget"] = widgets[0]
    elif len(widgets) > 1:
        details["widgets"] = CommentedSeq(widgets)

    new_entry = CommentedMap({name: details})
    if item_index is None:
        _, target_items = first_pair(data[target_group])
        target_items.append(new_entry)
    else:
        _, source_items = first_pair(data[group_index])
        if target_group == group_index:
            source_items[item_index] = new_entry
        else:
            del source_items[item_index]
            _, target_items = first_pair(data[target_group])
            target_items.append(new_entry)
    return data, name


async def save_service(request: Request, group_index: int, item_index: int | None) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        before = deep_plain(store.load("services.yaml"))
        data, name = _build_service_change(form, group_index, item_index)
        if deep_plain(data) == before:
            return redirect("/services", ok=f"服务“{name}”没有实际变化，未写入配置，也没有生成备份。")
        action = f"create service {name}" if item_index is None else f"update service {name}"
        store.write_data("services.yaml", data, actor(request), action)
        return redirect("/services", ok=f"服务“{name}”已保存。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect("/services", error=str(exc))


@app.post("/api/services/preview")
async def preview_service_change(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        group_index = int(str(form.get("source_group_index", form.get("group_index", 0))))
        item_raw = str(form.get("source_item_index", "")).strip()
        item_index = int(item_raw) if item_raw else None
        current = store.load("services.yaml")
        proposed, _ = _build_service_change(form, group_index, item_index)
        before = store.dump(mask_secrets(current)).splitlines()
        after = store.dump(mask_secrets(proposed)).splitlines()
        diff = "\n".join(
            difflib.unified_diff(before, after, fromfile="services.yaml · 当前", tofile="services.yaml · 保存后", lineterm="")
        )
        return JSONResponse({"ok": True, "changed": before != after, "diff": diff or "无实际变化。"})
    except (ConfigError, IndexError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/api/widgets/test")
async def test_widget_connection(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    payload = await request.json()
    verify_csrf(request, request.headers.get("x-csrf-token", ""))
    widget_type = str(payload.get("type", "")).strip().lower()
    raw_config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    try:
        config: dict[str, Any] = {}
        schema = WIDGET_CATALOG.get(widget_type, {})
        for field in schema.get("fields", []):
            name = str(field.get("name", ""))
            if not name:
                continue
            raw = raw_config.get(name, "")
            kind = str(field.get("kind", "text"))
            if kind == "secret":
                if str(raw).strip():
                    config[name] = str(raw).strip()
                continue
            if kind == "yaml" and isinstance(raw, str):
                value = _coerce_widget_field("yaml", raw)
            else:
                value = _coerce_widget_field(kind, str(raw))
            if value is not None:
                config[name] = value

        # Reuse an already-saved secret without sending it to the browser.
        item_raw = str(payload.get("item_index", "")).strip()
        original_index = int(payload.get("original_index", -1))
        if item_raw and original_index >= 0:
            gi = int(payload.get("group_index", 0))
            ii = int(item_raw)
            data = store.load("services.yaml")
            _, items = first_pair(data[gi])
            _, details = first_pair(items[ii])
            if isinstance(details, dict):
                old_widgets = _old_widgets(details)
                if original_index < len(old_widgets):
                    old_widget = old_widgets[original_index]
                    if str(old_widget.get("type", "")).lower() == widget_type:
                        for secret_name in catalog_secret_names(widget_type):
                            if secret_name not in config and old_widget.get(secret_name):
                                config[secret_name] = old_widget[secret_name]

        result = await test_widget(widget_type, config)
        return JSONResponse({"ok": True, **result})
    except (WidgetTestError, ConfigError, IndexError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/services/item/create")
async def create_service(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    return await save_service(request, 0, None)


@app.post("/services/item/{group_index}/{item_index}/update")
async def update_service(
    request: Request, group_index: int, item_index: int, _: None = Depends(auth_guard)
) -> RedirectResponse:
    return await save_service(request, group_index, item_index)


def bookmark_form_values(data: list[Any], group_index: int, item_index: int | None) -> dict[str, Any]:
    values = {"name": "", "abbr": "", "icon": "", "href": "", "description": "", "extra": ""}
    if item_index is None:
        return values
    _, items = first_pair(data[group_index])
    name, details_list = first_pair(items[item_index])
    if not isinstance(details_list, list) or not details_list or not isinstance(details_list[0], dict):
        raise ConfigError("书签格式无法通过表单编辑，请使用高级 YAML 编辑器。")
    details = details_list[0]
    values["name"] = name
    known = {"abbr", "icon", "href", "description"}
    for key in known:
        values[key] = details.get(key, "")
    extra = CommentedMap((k, copy.deepcopy(v)) for k, v in details.items() if k not in known)
    values["extra"] = store.dump_fragment(mask_secrets(extra)) if extra else ""
    return values


@app.get("/bookmarks/item/new", response_class=HTMLResponse)
def new_bookmark(request: Request, group: int = 0, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        data = store.load("bookmarks.yaml")
        names = group_names("bookmarks.yaml")
        if not names:
            return redirect("/bookmarks", error="请先创建一个书签分组。")
        group = min(max(group, 0), len(names) - 1)
        values = bookmark_form_values(data, group, None)
    except ConfigError as exc:
        return redirect("/bookmarks", error=str(exc))
    return templates.TemplateResponse(
        request,
        "bookmark_form.html",
        context(request, "bookmarks", mode="new", group_index=group, item_index=None, groups=names, values=values),
    )


@app.get("/bookmarks/item/{group_index}/{item_index}/edit", response_class=HTMLResponse)
def edit_bookmark(
    request: Request, group_index: int, item_index: int, _: None = Depends(auth_guard)
) -> HTMLResponse:
    try:
        data = store.load("bookmarks.yaml")
        values = bookmark_form_values(data, group_index, item_index)
        names = group_names("bookmarks.yaml")
    except (ConfigError, IndexError) as exc:
        return redirect("/bookmarks", error=str(exc))
    return templates.TemplateResponse(
        request,
        "bookmark_form.html",
        context(
            request,
            "bookmarks",
            mode="edit",
            group_index=group_index,
            item_index=item_index,
            groups=names,
            values=values,
        ),
    )


async def save_bookmark(request: Request, group_index: int, item_index: int | None) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("bookmarks.yaml")
        target_group = int(str(form.get("group_index", group_index)))
        name = str(form.get("name", "")).strip()
        if not name:
            raise ConfigError("书签名称不能为空。")
        details = CommentedMap()
        for key in ["abbr", "icon", "href", "description"]:
            value = str(form.get(key, "")).strip()
            if value:
                details[key] = value
        if not details.get("href"):
            raise ConfigError("书签访问地址不能为空。")
        extra = store.parse_fragment(str(form.get("extra", "")), dict)
        old_list: list[Any] = []
        old_bookmark_details: dict[str, Any] = {}
        if item_index is not None:
            _, source_items = first_pair(data[group_index])
            _, loaded_old_list = first_pair(source_items[item_index])
            if isinstance(loaded_old_list, list):
                old_list = loaded_old_list
                if old_list and isinstance(old_list[0], dict):
                    old_bookmark_details = old_list[0]
        if old_bookmark_details:
            try:
                extra = restore_masked_secrets(extra, old_bookmark_details)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
        for key, value in extra.items():
            if key not in details:
                details[key] = value
        details_list = CommentedSeq([details])
        if old_list and len(old_list) > 1:
            details_list.extend(copy.deepcopy(old_list[1:]))
        entry = CommentedMap({name: details_list})
        if item_index is None:
            _, target_items = first_pair(data[target_group])
            target_items.append(entry)
            action = f"create bookmark {name}"
        else:
            _, source_items = first_pair(data[group_index])
            if target_group == group_index:
                source_items[item_index] = entry
            else:
                del source_items[item_index]
                _, target_items = first_pair(data[target_group])
                target_items.append(entry)
            action = f"update bookmark {name}"
        store.write_data("bookmarks.yaml", data, actor(request), action)
        return redirect("/bookmarks", ok=f"书签“{name}”已保存。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect("/bookmarks", error=str(exc))


@app.post("/bookmarks/item/create")
async def create_bookmark(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    return await save_bookmark(request, 0, None)


@app.post("/bookmarks/item/{group_index}/{item_index}/update")
async def update_bookmark(
    request: Request, group_index: int, item_index: int, _: None = Depends(auth_guard)
) -> RedirectResponse:
    return await save_bookmark(request, group_index, item_index)


@app.post("/{kind}/item/{group_index}/{item_index}/delete")
async def delete_item(
    kind: str, group_index: int, item_index: int, request: Request, _: None = Depends(auth_guard)
) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    target = f"/{kind}"
    try:
        filename = f"{kind}.yaml"
        data = store.load(filename)
        _, items = first_pair(data[group_index])
        name, _ = first_pair(items[item_index])
        del items[item_index]
        store.write_data(filename, data, actor(request), f"delete item {name}")
        return redirect(target, ok=f"已删除“{name}”。")
    except (ConfigError, IndexError) as exc:
        return redirect(target, error=str(exc))


@app.post("/{kind}/item/{group_index}/{item_index}/duplicate")
async def duplicate_item(
    kind: str, group_index: int, item_index: int, request: Request, _: None = Depends(auth_guard)
) -> RedirectResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    target = f"/{kind}"
    try:
        filename = f"{kind}.yaml"
        data = store.load(filename)
        _, items = first_pair(data[group_index])
        name, value = first_pair(items[item_index])
        items.insert(item_index + 1, CommentedMap({f"{name} - 副本": copy.deepcopy(value)}))
        store.write_data(filename, data, actor(request), f"duplicate item {name}")
        return redirect(target, ok=f"已复制“{name}”。")
    except (ConfigError, IndexError) as exc:
        return redirect(target, error=str(exc))


@app.post("/api/{kind}/move")
async def move_item(kind: str, request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    verify_csrf(request, request.headers.get("x-csrf-token"))
    payload = await request.json()
    try:
        source_group = int(payload["source_group"])
        source_index = int(payload["source_index"])
        target_group = int(payload["target_group"])
        target_index = int(payload["target_index"])
        filename = f"{kind}.yaml"
        data = store.load(filename)
        _, source_items = first_pair(data[source_group])
        item = source_items.pop(source_index)
        _, target_items = first_pair(data[target_group])
        # target_index is calculated by the browser against cards with the dragged
        # item already excluded, so it already matches the post-pop list.
        target_index = max(0, min(target_index, len(target_items)))
        target_items.insert(target_index, item)
        store.write_data(filename, data, actor(request), "drag item")
        return JSONResponse({"ok": True})
    except (KeyError, ValueError, IndexError, ConfigError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/api/{kind}/group/reorder")
async def reorder_group(kind: str, request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    if kind not in {"services", "bookmarks"}:
        raise HTTPException(404)
    verify_csrf(request, request.headers.get("x-csrf-token"))
    payload = await request.json()
    try:
        source_index = int(payload["source_index"])
        target_index = int(payload["target_index"])
        filename = f"{kind}.yaml"
        data = store.load(filename)
        group = data.pop(source_index)
        if target_index > source_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(data)))
        data.insert(target_index, group)
        store.write_data(filename, data, actor(request), "drag group")
        sync_layout_order([first_pair(entry)[0] for entry in data], actor(request))
        return JSONResponse({"ok": True})
    except (KeyError, ValueError, IndexError, ConfigError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)



def _service_choices() -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    data = store.load("services.yaml")
    for gi, group_entry in enumerate(data):
        group_name, items = first_pair(group_entry)
        if not isinstance(items, list):
            continue
        for ii, item in enumerate(items):
            try:
                name, details = first_pair(item)
            except ConfigError:
                continue
            if not isinstance(details, dict):
                continue
            choices.append({"group_index": gi, "item_index": ii, "group": group_name, "name": name, "details": details})
    return choices


@app.get("/widget-center", response_class=HTMLResponse)
def widget_center_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "widget_center.html",
        context(
            request,
            "widget-center",
            widget_catalog=WIDGET_CATALOG,
            categories=catalog_categories(),
            schema_status=widget_schema_status(),
            ok=request.query_params.get("ok"),
            error=request.query_params.get("error"),
        ),
    )


@app.get("/widget-schema", response_class=HTMLResponse)
def widget_schema_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "widget_schema.html",
        context(
            request,
            "widget-center",
            schema_status=widget_schema_status(),
            ok=request.query_params.get("ok"),
            error=request.query_params.get("error"),
        ),
    )


@app.post("/widget-schema/schedule")
async def widget_schema_schedule_update(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        interval_hours = int(str(form.get("interval_hours", "24")).strip())
        saved = store.set_widget_schema_sync_preferences(
            auto_sync=str(form.get("auto_sync", "")).lower() in {"1", "true", "yes", "on"},
            mode=str(form.get("mode", "interval")),
            interval_hours=interval_hours,
            daily_time=str(form.get("daily_time", "03:00")),
            timezone_name=str(form.get("timezone", "UTC")),
            actor=actor(request),
        )
        if not saved["auto_sync"]:
            message = "Widget Schema 自动同步已关闭；手动同步仍可正常使用。"
        elif saved["mode"] == "daily":
            message = f"自动同步已保存：每天 {saved['daily_time']}（{saved['timezone']}）。"
        else:
            message = f"自动同步已保存：每 {saved['interval_hours']} 小时检查一次。"
        return redirect("/widget-schema", ok=message)
    except (TypeError, ValueError):
        return redirect("/widget-schema", error="自动同步间隔必须填写 1 到 720 之间的整数。")
    except ConfigError as exc:
        return redirect("/widget-schema", error=str(exc))


@app.post("/widget-schema/schedule/reset")
async def widget_schema_schedule_reset(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    saved = store.reset_widget_schema_sync_preferences(actor(request))
    if saved["auto_sync"]:
        if saved["mode"] == "daily":
            message = f"已恢复环境默认自动同步计划：每天 {saved['daily_time']}（{saved['timezone']}）。"
        else:
            message = f"已恢复环境默认自动同步计划：每 {saved['interval_hours']} 小时。"
    else:
        message = "已恢复环境默认设置：自动同步关闭。"
    return redirect("/widget-schema", ok=message)


@app.post("/api/widget-schema/sync/start")
async def widget_schema_sync_start_api(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    verify_csrf(request, request.headers.get("x-csrf-token", ""))
    state = start_widget_schema_sync_job()
    return JSONResponse({"ok": True, **state})


@app.get("/api/widget-schema/sync/status")
async def widget_schema_sync_status_api(_: None = Depends(auth_guard)) -> JSONResponse:
    return JSONResponse({"ok": True, **widget_schema_sync_job_status()})


@app.post("/widget-schema/sync")
async def widget_schema_sync_now(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        status = await asyncio.to_thread(sync_widget_schema, force=True)
        return redirect(
            "/widget-schema",
            ok=f"官方 Widget Schema 已同步：{status.get('widget_count', 0)} 个 Widget，自动字段 {status.get('generated_field_count', 0)} 个。",
        )
    except Exception as exc:
        return redirect("/widget-schema", error=f"同步失败：{exc}")


@app.post("/widget-schema/reset")
async def widget_schema_reset(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    reset_widget_schema_cache()
    return redirect("/widget-schema", ok="已清除官方 Schema 缓存并恢复内置目录；后续自动同步将按当前计划处理。")


@app.post("/widget-schema/import")
async def widget_schema_import(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        status = import_widget_schema_json(str(form.get("schema_json", "")))
        return redirect("/widget-schema", ok=f"Schema 已导入：{status.get('widget_count', 0)} 个 Widget。")
    except (ValueError, OSError) as exc:
        return redirect("/widget-schema", error=f"导入失败：{exc}")


def _proxmox_connections() -> dict[str, ProxmoxConnection]:
    data = store.load("proxmox.yaml")
    connections: dict[str, ProxmoxConnection] = {}
    for name, config in data.items():
        if not isinstance(config, dict):
            continue
        url = str(config.get("url") or "").strip()
        token = str(config.get("token") or "").strip()
        secret = str(config.get("secret") or "").strip()
        if url and token and secret:
            connections[str(name)] = ProxmoxConnection(str(name), url, token, secret)
    return connections


def _proxmox_widget_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for service in _service_choices():
        details = service["details"]
        widgets = _old_widgets(details)
        for widget in widgets:
            if str(widget.get("type", "")).lower() != "proxmox":
                continue
            if widget.get("url") and widget.get("username") and widget.get("password"):
                candidates.append(
                    {
                        "group_index": service["group_index"],
                        "item_index": service["item_index"],
                        "group": service["group"],
                        "name": service["name"],
                        "node": str(widget.get("node") or "pve"),
                        "url": str(widget.get("url")),
                    }
                )
            break
    return candidates


def _proxmox_bindings() -> dict[tuple[str, int, str], dict[str, Any]]:
    bindings: dict[tuple[str, int, str], dict[str, Any]] = {}
    for service in _service_choices():
        details = service["details"]
        node = str(details.get("proxmoxNode") or "")
        vmid = details.get("proxmoxVMID")
        ptype = str(details.get("proxmoxType") or "qemu")
        try:
            vmid_int = int(vmid)
        except (TypeError, ValueError):
            continue
        if node:
            record = {k: v for k, v in service.items() if k != "details"}
            record["has_docker"] = bool(details.get("server") and details.get("container"))
            record["docker_server"] = str(details.get("server") or "")
            record["docker_container"] = str(details.get("container") or "")
            bindings[(node, vmid_int, ptype)] = record
    return bindings


@app.get("/proxmox", response_class=HTMLResponse)
async def proxmox_page(
    request: Request,
    server: str = "",
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    error = None
    resources: list[dict[str, Any]] = []
    connections = _proxmox_connections()
    selected = server if server in connections else (next(iter(connections), ""))
    if selected:
        try:
            resources = await proxmox_discovery.discover(connections[selected])
        except ProxmoxDiscoveryError as exc:
            error = str(exc)
    bindings = _proxmox_bindings()
    physical_nodes: set[str] = set()
    for resource in resources:
        # Homepage's current per-VM endpoint uses proxmoxNode both as the
        # proxmox.yaml key and as /nodes/{node}; bind to the physical node name.
        bind_node = str(resource.get("node") or selected)
        physical_nodes.add(bind_node)
        resource["bind_node"] = bind_node
        resource["connection_available"] = bind_node in connections
        resource["binding"] = bindings.get((bind_node, int(resource["vmid"]), str(resource["type"])))

    connection_rows = []
    for name, conn in connections.items():
        normalized = normalize_proxmox_url(conn.url)
        connection_rows.append({
            "name": name,
            "url": conn.url,
            "normalized_url": normalized,
            "needs_url_normalization": bool(conn.url and conn.url != normalized),
        })
    selected_row = next((row for row in connection_rows if row["name"] == selected), None)
    missing_node_connections = sorted(node for node in physical_nodes if node and node not in connections)

    service_choices = []
    for item in _service_choices():
        details = item["details"]
        row = {k: v for k, v in item.items() if k != "details"}
        row["has_docker"] = bool(details.get("server") and details.get("container"))
        row["docker_server"] = str(details.get("server") or "")
        row["docker_container"] = str(details.get("container") or "")
        service_choices.append(row)

    return templates.TemplateResponse(
        request,
        "proxmox.html",
        context(
            request,
            "proxmox",
            connections=connection_rows,
            selected=selected,
            selected_connection=selected_row,
            missing_node_connections=missing_node_connections,
            resources=resources,
            service_choices=service_choices,
            widget_candidates=_proxmox_widget_candidates(),
            error=error,
        ),
    )


@app.post("/proxmox/import-connection")
async def proxmox_import_connection(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        gi = int(str(form.get("group_index", "-1")))
        ii = int(str(form.get("item_index", "-1")))
        data = store.load("services.yaml")
        _, items = first_pair(data[gi])
        _, details = first_pair(items[ii])
        if not isinstance(details, dict):
            raise ConfigError("服务配置格式无效。")
        widget = next((item for item in _old_widgets(details) if str(item.get("type", "")).lower() == "proxmox"), None)
        if not widget:
            raise ConfigError("该服务没有 Proxmox Widget。")
        node = str(widget.get("node") or "pve").strip()
        url = normalize_proxmox_url(str(widget.get("url") or ""))
        token = str(widget.get("username") or "").strip()
        secret = str(widget.get("password") or "").strip()
        if not all([node, url, token, secret]):
            raise ConfigError("Proxmox Widget 缺少 node/url/token/secret，无法导入。")
        proxmox = store.load("proxmox.yaml")
        proxmox[node] = CommentedMap({"url": url, "token": token, "secret": secret})
        store.write_data("proxmox.yaml", proxmox, actor(request), f"import proxmox connection {node}")
        return redirect(f"/proxmox?server={quote(node)}", ok=f"已从现有 Widget 导入 Proxmox 连接“{node}”。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect("/proxmox", error=str(exc))


@app.post("/proxmox/normalize-connection")
async def proxmox_normalize_connection(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    server = str(form.get("server", "")).strip()
    try:
        data = store.load("proxmox.yaml")
        config = data.get(server)
        if not isinstance(config, dict):
            raise ConfigError("Proxmox 连接不存在。")
        current = str(config.get("url") or "").strip()
        normalized = normalize_proxmox_url(current)
        if not normalized:
            raise ConfigError("Proxmox URL 为空。")
        if current == normalized:
            return redirect(f"/proxmox?server={quote(server)}", ok="该连接 URL 已符合 Homepage 要求。")
        config["url"] = normalized
        store.write_data("proxmox.yaml", data, actor(request), f"normalize proxmox url {server}")
        return redirect(
            f"/proxmox?server={quote(server)}",
            ok=f"已修复“{server}”的 URL：去除末尾 /，Homepage 将正确拼接 /api2/json。",
        )
    except ConfigError as exc:
        return redirect(f"/proxmox?server={quote(server)}" if server else "/proxmox", error=str(exc))


@app.post("/proxmox/clear-docker")
async def proxmox_clear_docker_binding(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    server = str(form.get("server", "")).strip()
    try:
        gi = int(str(form.get("group_index", "-1")))
        ii = int(str(form.get("item_index", "-1")))
        data = store.load("services.yaml")
        _, items = first_pair(data[gi])
        service_name, details = first_pair(items[ii])
        if not isinstance(details, dict):
            raise ConfigError("目标服务格式无效。")
        details.pop("server", None)
        details.pop("container", None)
        store.write_data("services.yaml", data, actor(request), f"clear docker integration for {service_name}")
        return redirect(
            f"/proxmox?server={quote(server)}" if server else "/proxmox",
            ok=f"已清除“{service_name}”的 Docker 集成；Proxmox VM/LXC 关联保持不变。",
        )
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect(f"/proxmox?server={quote(server)}" if server else "/proxmox", error=str(exc))


@app.post("/proxmox/unbind")
async def proxmox_unbind_service(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    selected_server = str(form.get("server", "")).strip()
    expected_node = str(form.get("node", "")).strip()
    expected_type = str(form.get("type", "qemu")).strip() or "qemu"
    try:
        gi = int(str(form.get("group_index", "-1")))
        ii = int(str(form.get("item_index", "-1")))
        expected_vmid = int(str(form.get("vmid", "0")))
        data = store.load("services.yaml")
        _, items = first_pair(data[gi])
        service_name, details = first_pair(items[ii])
        if not isinstance(details, dict):
            raise ConfigError("目标服务格式无效。")

        current_node = str(details.get("proxmoxNode") or "").strip()
        current_type = str(details.get("proxmoxType") or "qemu").strip() or "qemu"
        try:
            current_vmid = int(details.get("proxmoxVMID"))
        except (TypeError, ValueError) as exc:
            raise ConfigError("该服务当前没有有效的 Proxmox VM/LXC 关联。") from exc

        if (current_node, current_vmid, current_type) != (expected_node, expected_vmid, expected_type):
            raise ConfigError("该服务的 Proxmox 关联已发生变化，请刷新页面后再操作。")

        details.pop("proxmoxNode", None)
        details.pop("proxmoxVMID", None)
        details.pop("proxmoxType", None)
        store.write_data("services.yaml", data, actor(request), f"unbind service {service_name} from proxmox {expected_node}/{expected_vmid}")
        return redirect(
            f"/proxmox?server={quote(selected_server)}" if selected_server else "/proxmox",
            ok=f"已取消“{service_name}”与 {expected_type.upper()} {expected_vmid} 的关联；服务本身未删除。",
        )
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect(f"/proxmox?server={quote(selected_server)}" if selected_server else "/proxmox", error=str(exc))


@app.post("/proxmox/bind")
async def proxmox_bind_service(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    server = str(form.get("server", "")).strip()
    try:
        if server not in _proxmox_connections():
            raise ConfigError("Proxmox Server 不存在。")
        gi = int(str(form.get("group_index", "-1")))
        ii = int(str(form.get("item_index", "-1")))
        vmid = int(str(form.get("vmid", "0")))
        ptype = str(form.get("type", "qemu"))
        if ptype not in {"qemu", "lxc"}:
            raise ConfigError("Proxmox 类型必须是 qemu 或 lxc。")
        data = store.load("services.yaml")
        _, items = first_pair(data[gi])
        service_name, details = first_pair(items[ii])
        if not isinstance(details, dict):
            raise ConfigError("目标服务格式无效。")
        details["proxmoxNode"] = server
        details["proxmoxVMID"] = vmid
        if ptype == "lxc":
            details["proxmoxType"] = "lxc"
        else:
            details.pop("proxmoxType", None)
        if str(form.get("clear_docker", "")) == "1":
            details.pop("server", None)
            details.pop("container", None)
        store.write_data("services.yaml", data, actor(request), f"bind service {service_name} to proxmox {server}/{vmid}")
        return redirect(f"/proxmox?server={quote(server)}", ok=f"已将“{service_name}”关联到 {ptype.upper()} {vmid}。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect(f"/proxmox?server={quote(server)}" if server else "/proxmox", error=str(exc))


def _docker_host_safe(host: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in host.items() if k != "client"}


def _docker_host_snapshot(host: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row = _docker_host_safe(host)
    client = host.get("client")
    if not isinstance(client, DockerDiscoveryClient):
        row.update({"healthy": False, "error": "该连接无法由 Admin 直接发现容器。若 docker.yaml 使用 socket，请添加一个只读 Docker Proxy 自定义连接。", "container_count": 0})
        return row, []
    try:
        if not client.ping():
            raise RuntimeError("Docker API /_ping 不可达")
        containers = client.list_containers()
        row.update({"healthy": True, "error": "", "container_count": len(containers)})
        return row, containers
    except Exception as exc:
        row.update({"healthy": False, "error": str(exc), "container_count": 0})
        return row, []


def _docker_custom_host_id(homepage_server: str, display_name: str) -> str:
    source = homepage_server or display_name or "docker-host"
    slug = re.sub(r"[^a-z0-9]+", "-", source.casefold()).strip("-")[:48] or "docker-host"
    return slug


@app.get("/docker", response_class=HTMLResponse)
def docker_page(
    request: Request,
    host: str = "all",
    show_internal: bool = False,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    error = request.query_params.get("error")
    configured = configured_docker_containers()
    all_hosts = docker_discovery_hosts()
    host_ids = {str(item.get("id")) for item in all_hosts}
    if host != "all" and host not in host_ids:
        error = error or "未找到指定的 Docker 主机，已切换到全部主机。"
        host = "all"
    selected_hosts = all_hosts if host == "all" else [item for item in all_hosts if str(item.get("id")) == host]

    snapshots: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    if selected_hosts:
        with ThreadPoolExecutor(max_workers=min(8, len(selected_hosts))) as pool:
            futures = {pool.submit(_docker_host_snapshot, item): str(item.get("id")) for item in selected_hosts}
            for future in as_completed(futures):
                host_id = futures[future]
                try:
                    snapshots[host_id] = future.result()
                except Exception as exc:
                    base = next((x for x in selected_hosts if str(x.get("id")) == host_id), {"id": host_id, "name": host_id})
                    snapshots[host_id] = ({**_docker_host_safe(base), "healthy": False, "error": str(exc), "container_count": 0}, [])

    visible: list[dict[str, Any]] = []
    host_errors: list[dict[str, Any]] = []
    hidden_internal_count = 0
    internal_names = {"homepage-docker-proxy", "homepage-admin-docker-proxy", "docker-proxy"}
    for selected in selected_hosts:
        host_id = str(selected.get("id"))
        status, containers = snapshots.get(host_id, (_docker_host_safe(selected), []))
        if not status.get("healthy"):
            host_errors.append(status)
        server_name = str(selected.get("homepage_server") or "")
        for raw in containers:
            item = dict(raw)
            name = str(item.get("name", ""))
            item["published_ports"] = [p for p in dedupe_ports(item.get("ports") or []) if p.get("public")]
            labels = item.get("labels") or {}
            item["homepage_labeled"] = any(str(k).startswith("homepage.") for k in labels)
            matches = configured.get((server_name.casefold(), name.casefold()), [])
            item["configured"] = bool(matches)
            item["configured_matches"] = matches
            item["role"] = container_role(item)
            item["discovery_host_id"] = host_id
            item["discovery_host_name"] = str(selected.get("name") or host_id)
            item["homepage_server"] = server_name
            item["yaml_configured"] = bool(selected.get("yaml_configured"))
            if settings.hide_internal_containers and not show_internal and name.casefold() in internal_names:
                hidden_internal_count += 1
                continue
            visible.append(item)

    visible.sort(key=lambda item: (str(item.get("discovery_host_name", "")).casefold(), item.get("state") != "running", str(item.get("name", "")).casefold()))
    groups = group_names("services.yaml")
    return templates.TemplateResponse(
        request,
        "docker.html",
        context(
            request,
            "docker",
            containers=visible,
            error=error,
            ok=request.query_params.get("ok"),
            docker_hosts=[_docker_host_safe(item) for item in all_hosts],
            selected_host=host,
            host_errors=host_errors,
            show_internal=show_internal,
            hidden_internal_count=hidden_internal_count,
            service_groups=groups,
            recommended_group_index=recommended_import_group(groups),
        ),
    )


@app.post("/docker/unbind")
async def docker_unbind_service(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    host_id = str(form.get("host_id", "")).strip()
    expected_server = str(form.get("server", "")).strip()
    expected_container = str(form.get("container", "")).strip()
    try:
        gi = int(str(form.get("group_index", "-1")))
        ii = int(str(form.get("item_index", "-1")))
        data = store.load("services.yaml")
        _, items = first_pair(data[gi])
        service_name, details = first_pair(items[ii])
        if not isinstance(details, dict):
            raise ConfigError("目标服务格式无效。")
        current_server = str(details.get("server") or "").strip()
        current_container = str(details.get("container") or "").strip()
        if current_server.casefold() != expected_server.casefold() or current_container.casefold() != expected_container.casefold():
            raise ConfigError("该服务的 Docker 配置已经发生变化，请刷新页面后再操作。")
        details.pop("server", None)
        details.pop("container", None)
        store.write_data("services.yaml", data, actor(request), f"unbind service {service_name} from docker {expected_server}/{expected_container}")
        target = f"/docker?host={quote(host_id)}" if host_id else "/docker"
        return redirect(target, ok=f"已移除“{service_name}”的 Docker 配置；服务本身及 Widget/链接配置保持不变。")
    except (ConfigError, IndexError, ValueError) as exc:
        target = f"/docker?host={quote(host_id)}" if host_id else "/docker"
        return redirect(target, error=str(exc))


@app.get("/docker/hosts", response_class=HTMLResponse)
def docker_hosts_page(
    request: Request,
    edit: str | None = None,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    hosts = docker_discovery_hosts()
    for item in hosts:
        refs = docker_server_references(str(item.get("homepage_server") or ""))
        item["reference_count"] = len(refs)
        item["reference_preview"] = refs[:4]
    editable = next((item for item in hosts if str(item.get("id")) == str(edit or "") and item.get("editable")), None)
    form_values = {
        "original_id": "",
        "original_server": "",
        "name": "",
        "url": "",
        "homepage_server": "",
        "public_host": "",
        "discovery_override": "",
    }
    if editable:
        form_values.update({
            "original_id": "",
            "original_server": str(editable.get("homepage_server") or ""),
            "name": str(editable.get("name") or editable.get("homepage_server") or ""),
            "url": str(editable.get("core_url") or editable.get("url") or ""),
            "homepage_server": str(editable.get("homepage_server") or ""),
            "public_host": str(editable.get("public_host") or ""),
            "discovery_override": str(editable.get("discovery_override") or ""),
        })
    return templates.TemplateResponse(
        request,
        "docker_hosts.html",
        context(
            request,
            "docker",
            hosts=[_docker_host_safe(item) for item in hosts],
            default_server_info=docker_server_info(),
            edit_host=_docker_host_safe(editable) if editable else None,
            form_values=form_values,
            error=request.query_params.get("error"),
            ok=request.query_params.get("ok"),
        ),
    )


@app.post("/api/docker/hosts/test")
async def docker_host_test(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        host_id = str(form.get("host_id", "")).strip()
        if host_id:
            target = docker_discovery_host(host_id)
            if not target or not isinstance(target.get("client"), DockerDiscoveryClient):
                raise ConfigError("该 Docker 主机没有可用的 Admin Discovery 连接。")
            client = target["client"]
            label = str(target.get("name") or host_id)
        else:
            core_url = str(form.get("url", "")).strip().rstrip("/")
            override = str(form.get("discovery_override", "")).strip().rstrip("/")
            test_url = override or core_url
            validated = store._validate_docker_discovery_host_payload({
                "id": "test-host",
                "name": "Test",
                "url": test_url,
                "homepage_server": str(form.get("homepage_server", "test-server") or "test-server"),
                "public_host": str(form.get("public_host", "")),
            })
            existing_server = homepage_docker_servers().get(str(form.get("homepage_server", "") or ""))
            client = _docker_client_from_url_and_yaml(validated["url"], existing_server) if existing_server else DockerDiscoveryClient(validated["url"])
            label = validated["url"]
        if not client.ping():
            raise ConfigError("Docker API /_ping 不可达。")
        containers = client.list_containers()
        running = sum(1 for item in containers if str(item.get("state")) == "running")
        return JSONResponse({"ok": True, "message": f"{label} 连接成功：{len(containers)} 个容器，{running} 个运行中。", "containers": len(containers), "running": running})
    except Exception as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)


@app.post("/docker/hosts/save")
async def docker_host_save(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    original_server = str(form.get("original_server", "")).strip()
    homepage_server = str(form.get("homepage_server", "")).strip()
    core_url = str(form.get("url", "")).strip().rstrip("/")
    override = str(form.get("discovery_override", "")).strip().rstrip("/")
    payload = {
        "id": _docker_custom_host_id(homepage_server, str(form.get("name", ""))),
        "name": str(form.get("name", "")),
        "url": core_url,
        "homepage_server": homepage_server,
        "public_host": str(form.get("public_host", "")),
    }
    try:
        validated = store._validate_docker_discovery_host_payload(payload)
        renamed = bool(original_server and original_server != validated["homepage_server"])
        if renamed:
            refs = docker_server_references(original_server)
            if refs:
                raise ConfigError(f"Docker Server“{original_server}”当前被 {len(refs)} 个服务引用，暂不能改名。请先移除或迁移这些服务的 Docker 配置。")
            duplicate = next((item for item in docker_discovery_hosts() if str(item.get("homepage_server") or "").casefold() == validated["homepage_server"].casefold() and str(item.get("homepage_server") or "") != original_server), None)
            if duplicate:
                raise ConfigError(f"Docker 主机“{validated['homepage_server']}”已存在，不能使用该名称。")
        elif not original_server:
            duplicate = next((item for item in docker_discovery_hosts() if str(item.get("homepage_server") or "").casefold() == validated["homepage_server"].casefold()), None)
            if duplicate:
                raise ConfigError(f"Docker 主机“{validated['homepage_server']}”已存在，请直接编辑现有主机。")

        if override:
            # Validate Admin-only override independently. It is never copied into docker.yaml.
            store._validate_docker_host_metadata(validated["homepage_server"], {"discovery_override": override})
            if override == validated["url"].rstrip("/"):
                override = ""

        old_metadata = store.docker_host_metadata().get(original_server, {}) if renamed else {}
        created, did_rename = upsert_homepage_docker_server_from_discovery(validated, actor(request), original_server=original_server)
        metadata_payload = {
            "display_name": validated["name"] if validated["name"] != validated["homepage_server"] else "",
            "public_host": validated["public_host"],
            "discovery_override": override,
        }
        # Preserve any Admin-only metadata values that the current form does not
        # expose, while always letting the submitted fields win.
        if old_metadata:
            merged_meta = dict(old_metadata)
            merged_meta.update(metadata_payload)
            metadata_payload = merged_meta
        metadata = store.save_docker_host_metadata(validated["homepage_server"], metadata_payload, actor(request))
        if did_rename and original_server != validated["homepage_server"]:
            store.delete_docker_host_metadata(original_server, actor(request))
        note = "已重命名并更新 docker.yaml Server" if did_rename else ("已创建 docker.yaml Server" if created else "已更新 docker.yaml Server")
        meta_note = "；Admin 仅保存显示元数据" if metadata else "；无需额外 Admin 元数据"
        return redirect("/docker/hosts", ok=f"已保存 Docker 主机“{validated['name']}”；{note}{meta_note}。")
    except ConfigError as exc:
        return redirect("/docker/hosts", error=str(exc))


@app.post("/docker/hosts/yaml-save")
async def docker_yaml_host_save(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    server_name = str(form.get("server_name", "")).strip()
    try:
        update_homepage_docker_server(
            server_name,
            {
                "mode": str(form.get("mode", "remote")),
                "host": str(form.get("host", "")),
                "port": str(form.get("port", "")),
                "protocol": str(form.get("protocol", "http")),
                "socket": str(form.get("socket", "")),
            },
            actor(request),
        )
        return redirect("/docker/hosts", ok=f"已更新 docker.yaml Server“{server_name}”；未识别的 TLS/Header/扩展字段均已保留。")
    except ConfigError as exc:
        return redirect(f"/docker/hosts?edit={quote(_docker_host_id('yaml', server_name))}", error=str(exc))


@app.get("/docker/hosts/delete/{host_id}", response_class=HTMLResponse)
def docker_host_delete_page(host_id: str, request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    host = docker_discovery_host(host_id)
    if not host or not host.get("manageable"):
        raise HTTPException(404)
    server_name = str(host.get("homepage_server") or "")
    references = docker_server_references(server_name)
    has_metadata = bool(store.docker_host_metadata().get(server_name))
    has_yaml = server_name in homepage_docker_servers()
    return templates.TemplateResponse(
        request,
        "docker_host_delete.html",
        context(
            request,
            "docker",
            host=_docker_host_safe(host),
            references=references,
            has_metadata=has_metadata,
            has_custom=has_metadata,  # compatibility with older templates/tests
            has_yaml=has_yaml,
            default_remove_custom=False,
            default_remove_yaml=has_yaml,
            error=request.query_params.get("error"),
        ),
    )


@app.post("/docker/hosts/delete-confirm")
async def docker_host_delete_confirm(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    host_id = str(form.get("host_id", "")).strip()
    server_name = str(form.get("homepage_server", "")).strip()
    remove_custom = str(form.get("remove_custom", "")) == "1"
    remove_yaml = str(form.get("remove_yaml", "")) == "1"
    clear_refs = str(form.get("clear_refs", "")) == "1"
    confirm_text = str(form.get("confirm_text", "")).strip()
    try:
        host = docker_discovery_host(host_id)
        if not host or not host.get("manageable"):
            raise ConfigError("Docker 主机不存在或已发生变化，请刷新后重试。")
        current_server = str(host.get("homepage_server") or "").strip()
        if current_server != server_name:
            raise ConfigError("Docker Server 映射已经发生变化，请刷新后重试。")
        has_metadata = bool(store.docker_host_metadata().get(server_name))
        has_custom = has_metadata  # compatibility with v0.4.1/v0.4.2 POST payloads
        has_yaml = server_name in homepage_docker_servers()
        if not remove_custom and not remove_yaml:
            raise ConfigError("至少选择一项删除操作。")
        if remove_custom and not has_metadata:
            raise ConfigError("该主机当前没有 Admin 元数据。")
        if remove_yaml and not has_yaml:
            raise ConfigError("该主机当前没有 docker.yaml Server。")
        refs = docker_server_references(server_name)
        if remove_yaml and refs and confirm_text != "DELETE":
            raise ConfigError(f"docker.yaml Server 当前被 {len(refs)} 个服务引用。请输入 DELETE 确认删除。")
        if clear_refs and not remove_yaml:
            raise ConfigError("只有删除 docker.yaml Server 时才能同时清除服务引用。")

        cleared = 0
        if remove_yaml and clear_refs:
            services = store.load("services.yaml")
            cleared = _clear_docker_server_references(services, server_name)
            if cleared:
                store.write_data("services.yaml", services, actor(request), f"clear docker server references {server_name}")

        if remove_yaml:
            docker_data = store.load("docker.yaml")
            if server_name not in docker_data:
                raise ConfigError("docker.yaml Server 已不存在，请刷新页面。")
            del docker_data[server_name]
            store.write_data("docker.yaml", docker_data, actor(request), f"delete docker server {server_name}")
            # Metadata without its docker.yaml server is orphaned, so remove it automatically.
            if has_metadata:
                store.delete_docker_host_metadata(server_name, actor(request))
        elif remove_custom:
            # Backward-compatible endpoint behavior for v0.4.1/v0.4.2 clients.
            store.delete_docker_host_metadata(server_name, actor(request))

        parts: list[str] = []
        if remove_custom and not remove_yaml:
            parts.append("Admin 元数据")
        if remove_yaml:
            parts.append(f"Docker 主机“{server_name}”")
        if cleared:
            parts.append(f"{cleared} 个服务的 Docker 关联")
        return redirect("/docker/hosts", ok="已删除 " + "、".join(parts) + "。")
    except ConfigError as exc:
        return redirect(f"/docker/hosts/delete/{quote(host_id)}", error=str(exc))


@app.post("/docker/hosts/delete")
async def docker_host_delete(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    return redirect("/docker/hosts", error="v0.4.3 已取消独立 Admin 发现层删除；请使用 Docker 主机删除向导。")


@app.post("/docker/hosts/sync-homepage")
async def docker_host_sync_homepage(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    return redirect("/docker/hosts", ok="v0.4.3 已以 docker.yaml 为唯一 Docker 连接源，无需再执行单独同步。")


@app.post("/docker/setup-homepage")
async def docker_setup_homepage(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("docker.yaml")
        if not isinstance(data, dict):
            raise ConfigError("docker.yaml 必须是对象映射。")
        if data:
            return redirect("/docker", error="docker.yaml 已有配置。请在 Docker 主机管理中添加更多连接，或使用高级编辑调整现有 Server。")
        data["local-docker"] = CommentedMap(
            {"host": settings.homepage_docker_proxy_host, "port": settings.homepage_docker_proxy_port}
        )
        store.write_data("docker.yaml", data, actor(request), "setup local docker proxy server")
        return redirect(
            "/docker",
            ok=f"已创建 local-docker，只读代理地址为 {settings.homepage_docker_proxy_host}:{settings.homepage_docker_proxy_port}。",
        )
    except ConfigError as exc:
        return redirect("/docker", error=str(exc))


@app.post("/docker/migrate-homepage-proxy")
async def docker_migrate_homepage_proxy(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("docker.yaml")
        if not isinstance(data, dict) or not data:
            raise ConfigError("docker.yaml 中没有可迁移的 Docker server。")
        name = first_docker_server_name()
        if not name or name not in data or not isinstance(data[name], dict):
            raise ConfigError("无法确定需要迁移的 Docker server。")
        cfg = data[name]
        cfg.pop("socket", None)
        cfg["host"] = settings.homepage_docker_proxy_host
        cfg["port"] = settings.homepage_docker_proxy_port
        cfg.pop("tls", None)
        cfg.pop("protocol", None)
        cfg.pop("headers", None)
        store.write_data("docker.yaml", data, actor(request), f"migrate docker server {name} to read-only proxy")
        return redirect(
            "/docker",
            ok=f"已将 {name} 切换为只读代理。请确认 Homepage 也能访问该代理，并移除直接 socket 挂载。",
        )
    except ConfigError as exc:
        return redirect("/docker", error=str(exc))


def docker_import_values(
    container: dict[str, Any],
    names: list[str],
    host: dict[str, Any],
    requested_group: int | None = None,
) -> tuple[dict[str, Any], int, dict[str, str]]:
    values = empty_service_values()
    sources: dict[str, str] = {}
    profile = infer_service_profile(container)
    label_values = homepage_labels_to_values(container)
    for key in ["name", "icon", "href", "description", "siteMonitor", "ping", "container"]:
        if label_values.get(key):
            values[key] = label_values[key]
            sources[key] = "Homepage Label"

    if not values["name"]:
        values["name"] = str(container.get("name", "Docker Service"))
        sources["name"] = "容器名称"
    if not values["container"]:
        values["container"] = str(container.get("name", ""))
        sources["container"] = "容器名称"

    homepage_server = str(host.get("homepage_server") or "")
    if not homepage_server:
        raise ConfigError("该 Docker 发现连接没有映射 Homepage Docker Server，无法安全导入。")
    values["server"] = homepage_server
    sources["server"] = f"Docker 主机 · {host.get('name') or homepage_server}"

    inferred_icon, inferred_widget = infer_icon_and_widget(container)
    if not values["icon"] and inferred_icon:
        values["icon"] = inferred_icon
        sources["icon"] = "服务识别"
    if not values["description"]:
        inferred_description = infer_service_description(container)
        if inferred_description:
            values["description"] = inferred_description
            sources["description"] = "服务识别"

    label_widget = label_values.get("widget") if isinstance(label_values.get("widget"), dict) else {}
    values["widget_type"] = str(label_widget.get("type", "") or inferred_widget)
    if label_widget.get("type"):
        sources["widget_type"] = "Homepage Label"
    elif inferred_widget:
        sources["widget_type"] = "服务识别"
    for key, value in label_widget.items():
        if key == "type":
            continue
        if key in catalog_secret_names(values["widget_type"]):
            continue
        values["widget_fields"][key] = value
        sources[f"widget_{key}"] = "Homepage Label"

    if not values["href"]:
        port = first_published_port(container)
        if port:
            public_host = docker_host_public_host(host)
            values["href"] = f"http://{public_host}:{port}"
            sources["href"] = f"{host.get('name') or homepage_server} 发布端口"
    if values["widget_type"] and not values["widget_fields"].get("url") and values["href"]:
        values["widget_fields"]["url"] = values["href"]
        sources["widget_url"] = "访问地址"

    desired_group = str(label_values.get("group", ""))
    if desired_group in names:
        group_index = names.index(desired_group)
        sources["group"] = "Homepage Label"
    elif requested_group is not None and 0 <= requested_group < len(names):
        group_index = requested_group
        sources["group"] = "Docker 发现页手动选择"
    else:
        profile_group = recommend_group_index(names, profile)
        if profile_group is not None:
            group_index = profile_group
            sources["group"] = f"服务类型推荐 · {profile.get('kind', '通用服务')}"
        else:
            group_index = recommended_import_group(names)
            sources["group"] = "通用推荐"
    return values, group_index, sources


def _docker_import_context(host_id: str, container_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    host = docker_discovery_host(host_id)
    if not host:
        raise ConfigError("未找到 Docker 主机。")
    client = host.get("client")
    if not isinstance(client, DockerDiscoveryClient):
        raise ConfigError("该 Docker 主机没有可用的 Admin Discovery 连接。")
    container = client.get_container(container_id)
    if not container:
        raise ConfigError("未找到该 Docker 容器。")
    return host, container


@app.get("/docker/host/{host_id}/import/{container_id}", response_class=HTMLResponse)
def docker_import_wizard_multi(
    request: Request,
    host_id: str,
    container_id: str,
    group: int | None = None,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    try:
        host, container = _docker_import_context(host_id, container_id)
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        values, group_index, sources = docker_import_values(container, names, host, group)
        container = dict(container)
        container["published_ports"] = [p for p in dedupe_ports(container.get("ports") or []) if p.get("public")]
        return templates.TemplateResponse(
            request,
            "docker_import_wizard.html",
            context(
                request,
                "docker",
                container=container,
                docker_host=_docker_host_safe(host),
                groups=names,
                group_index=group_index,
                values=values,
                suggestion_sources=sources,
                service_profile=infer_service_profile(container),
                widget_catalog=WIDGET_CATALOG,
            ),
        )
    except Exception as exc:
        return redirect(f"/docker?host={quote(host_id)}", error=f"导入容器失败：{exc}")


@app.get("/docker/host/{host_id}/import/{container_id}/edit", response_class=HTMLResponse)
def docker_import_edit_multi(
    request: Request,
    host_id: str,
    container_id: str,
    group_index: int | None = None,
    name: str | None = None,
    href: str | None = None,
    icon: str | None = None,
    description: str | None = None,
    siteMonitor: str | None = None,
    ping: str | None = None,
    widget_type: str | None = None,
    widget_url: str | None = None,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    try:
        host, container = _docker_import_context(host_id, container_id)
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        values, resolved_group, _ = docker_import_values(container, names, host, group_index)
        overrides = {
            "name": name,
            "href": href,
            "icon": icon,
            "description": description,
            "siteMonitor": siteMonitor,
            "ping": ping,
            "widget_type": widget_type,
        }
        for key, value in overrides.items():
            if value is not None:
                values[key] = value
        if widget_url is not None:
            values["widget_fields"]["url"] = widget_url
        if group_index is not None and 0 <= group_index < len(names):
            resolved_group = group_index
        return render_service_form(
            request,
            mode="new",
            group_index=resolved_group,
            item_index=None,
            groups=names,
            values=values,
            docker_source=f"{host.get('name') or host_id} / {container.get('name', '')}",
        )
    except Exception as exc:
        return redirect(f"/docker?host={quote(host_id)}", error=f"导入容器失败：{exc}")


# Compatibility routes for bookmarks/tests from pre-v0.4.0 links. They resolve the first available host.
@app.get("/docker/import/{container_id}", response_class=HTMLResponse)
def docker_import_wizard_legacy(
    request: Request,
    container_id: str,
    group: int | None = None,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    host = docker_discovery_host()
    if not host:
        return redirect("/docker", error="Docker 容器发现未启用。")
    target = f"/docker/host/{quote(str(host['id']))}/import/{quote(container_id)}"
    if group is not None:
        target += f"?group={group}"
    return RedirectResponse(target, status_code=307)


@app.get("/docker/import/{container_id}/edit", response_class=HTMLResponse)
def docker_import_edit_legacy(
    request: Request,
    container_id: str,
    _: None = Depends(auth_guard),
) -> RedirectResponse:
    host = docker_discovery_host()
    if not host:
        return redirect("/docker", error="Docker 容器发现未启用。")
    query = request.url.query
    target = f"/docker/host/{quote(str(host['id']))}/import/{quote(container_id)}/edit"
    if query:
        target += "?" + query
    return RedirectResponse(target, status_code=307)


HOMEPAGE_COLOR_OPTIONS = [
    "slate", "gray", "zinc", "neutral", "stone", "amber", "yellow", "lime", "green", "emerald",
    "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose", "red", "white",
]
HOMEPAGE_LANGUAGE_OPTIONS = [
    "ca", "de", "en", "es", "fr", "he", "hr", "hu", "it", "nb-NO", "nl", "pt", "ru", "sv", "vi",
    "zh-Hans", "zh-Hant",
]
HOMEPAGE_HEADER_STYLES = ["underlined", "boxed", "clean", "boxedWidgets"]
HOMEPAGE_STATUS_STYLES = ["dot", "basic"]
HOMEPAGE_ICON_STYLES = ["gradient", "theme"]
HOMEPAGE_CARD_BLURS = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"]
HOMEPAGE_BACKGROUND_BLURS = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"]
HOMEPAGE_QUICKLAUNCH_PROVIDERS = ["google", "duckduckgo", "bing", "baidu", "brave", "custom"]
HOMEPAGE_MOBILE_BUTTON_POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right"]


def _settings_layout_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    layout = data.get("layout", {})
    rows: list[dict[str, Any]] = []
    service_names = group_names("services.yaml")
    bookmark_names = group_names("bookmarks.yaml")
    service_set = set(service_names)
    bookmark_set = set(bookmark_names)

    if isinstance(layout, dict):
        for name, raw_cfg in layout.items():
            cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
            source = "服务 + 书签" if name in service_set and name in bookmark_set else ("服务" if name in service_set else ("书签" if name in bookmark_set else "仅布局"))
            rows.append(
                {
                    "name": str(name),
                    "source": source,
                    "configured": True,
                    "style": cfg.get("style", ""),
                    "columns": cfg.get("columns", ""),
                    "tab": cfg.get("tab", ""),
                    "icon": cfg.get("icon", ""),
                    "iconsOnly": bool(cfg.get("iconsOnly", False)),
                    "header": cfg.get("header", True) is not False,
                    "useEqualHeights": bool(cfg.get("useEqualHeights", False)),
                    "initiallyCollapsed": bool(cfg.get("initiallyCollapsed", False)),
                    "extra": store.dump_fragment(
                        mask_secrets(
                            CommentedMap(
                                (k, copy.deepcopy(v))
                                for k, v in cfg.items()
                                if k
                                not in {
                                    "style",
                                    "columns",
                                    "tab",
                                    "icon",
                                    "iconsOnly",
                                    "header",
                                    "useEqualHeights",
                                    "initiallyCollapsed",
                                }
                            )
                        )
                    ),
                }
            )

    existing = {row["name"] for row in rows}
    for name in service_names + bookmark_names:
        if name in existing:
            continue
        source = "服务 + 书签" if name in service_set and name in bookmark_set else ("服务" if name in service_set else "书签")
        rows.append(
            {
                "name": name,
                "source": source,
                "configured": False,
                "style": "",
                "columns": "",
                "tab": "",
                "icon": "",
                "iconsOnly": False,
                "header": True,
                "useEqualHeights": False,
                "initiallyCollapsed": False,
                "extra": "",
            }
        )
        existing.add(name)
    return rows


def _settings_values(data: dict[str, Any]) -> dict[str, Any]:
    background = data.get("background", {})
    if isinstance(background, str):
        background = {"image": background}
    if not isinstance(background, dict):
        background = {}
    quicklaunch = data.get("quicklaunch", {})
    if not isinstance(quicklaunch, dict):
        quicklaunch = {}

    if "blur" not in background:
        background_blur_mode = "__unset__"
    elif background.get("blur") == "":
        background_blur_mode = "__empty__"
    else:
        background_blur_mode = str(background.get("blur") or "__unset__")

    return {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "startUrl": data.get("startUrl", ""),
        "base": data.get("base", ""),
        "language": data.get("language", ""),
        "favicon": data.get("favicon", ""),
        "theme": data.get("theme", ""),
        "color": data.get("color", ""),
        "headerStyle": data.get("headerStyle", ""),
        "target": data.get("target", ""),
        "statusStyle": data.get("statusStyle", ""),
        "iconStyle": data.get("iconStyle", ""),
        "cardBlur": data.get("cardBlur", ""),
        "bookmarksStyle": data.get("bookmarksStyle", ""),
        "maxGroupColumns": data.get("maxGroupColumns", ""),
        "maxBookmarkGroupColumns": data.get("maxBookmarkGroupColumns", ""),
        "fullWidth": bool(data.get("fullWidth", False)),
        "hideVersion": bool(data.get("hideVersion", False)),
        "disableUpdateCheck": bool(data.get("disableUpdateCheck", False)),
        "showStats": bool(data.get("showStats", False)),
        "hideErrors": bool(data.get("hideErrors", False)),
        "disableIndexing": bool(data.get("disableIndexing", False)),
        "useEqualHeights": bool(data.get("useEqualHeights", False)),
        "disableCollapse": bool(data.get("disableCollapse", False)),
        "groupsInitiallyCollapsed": bool(data.get("groupsInitiallyCollapsed", False)),
        "background": background,
        "background_blur_mode": background_blur_mode,
        "quicklaunch": {
            "provider": quicklaunch.get("provider", ""),
            "searchDescriptions": bool(quicklaunch.get("searchDescriptions", False)),
            "hideInternetSearch": bool(quicklaunch.get("hideInternetSearch", False)),
            "showSearchSuggestions": bool(quicklaunch.get("showSearchSuggestions", False)),
            "hideVisitURL": bool(quicklaunch.get("hideVisitURL", False)),
            "url": quicklaunch.get("url", ""),
            "target": quicklaunch.get("target", ""),
            "suggestionUrl": quicklaunch.get("suggestionUrl", ""),
            "mobileButtonPosition": quicklaunch.get("mobileButtonPosition", ""),
        },
        "layout": _settings_layout_rows(data),
    }


def _set_optional_string(data: CommentedMap, old: dict[str, Any], form: Any, key: str) -> None:
    value = str(form.get(key, "")).strip()
    if value:
        data[key] = value
    elif key in old and old.get(key) == "":
        data[key] = ""


def _set_optional_bool(data: CommentedMap, old: dict[str, Any], form: Any, key: str) -> None:
    if form.get(key):
        data[key] = True
    elif key in old and old.get(key) is False:
        data[key] = False


def _build_settings_change(form: Any) -> CommentedMap:
    old = store.load("settings.yaml")
    data = CommentedMap()

    string_fields = [
        "language", "title", "description", "startUrl", "base", "favicon", "theme", "color", "headerStyle",
        "target", "statusStyle", "iconStyle", "cardBlur", "bookmarksStyle",
    ]
    for key in string_fields:
        _set_optional_string(data, old, form, key)

    for key in [
        "fullWidth", "hideVersion", "disableUpdateCheck", "showStats", "hideErrors", "disableIndexing",
        "useEqualHeights", "disableCollapse", "groupsInitiallyCollapsed",
    ]:
        _set_optional_bool(data, old, form, key)

    for key, minimum, maximum in [
        ("maxGroupColumns", 5, 8),
        ("maxBookmarkGroupColumns", 1, 8),
    ]:
        raw = str(form.get(key, "")).strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigError(f"{key} 必须是整数。") from exc
        if value < minimum or value > maximum:
            raise ConfigError(f"{key} 必须在 {minimum}–{maximum} 之间。")
        data[key] = value

    old_background = old.get("background", CommentedMap())
    if isinstance(old_background, str):
        old_background = CommentedMap({"image": old_background})
    background = copy.deepcopy(old_background) if isinstance(old_background, dict) else CommentedMap()

    image = str(form.get("background_image", "")).strip()
    if image:
        background["image"] = image
    else:
        background.pop("image", None)

    if "background_blur_mode" in form:
        blur_mode = str(form.get("background_blur_mode", "__unset__"))
        if blur_mode == "__unset__":
            background.pop("blur", None)
        elif blur_mode == "__empty__":
            background["blur"] = ""
        else:
            background["blur"] = blur_mode
    else:
        # Backwards compatibility with older form submissions/tests.
        blur_value = str(form.get("background_blur", "")).strip()
        if blur_value:
            background["blur"] = blur_value
        elif isinstance(old_background, dict) and "blur" in old_background and old_background.get("blur") == "":
            background["blur"] = ""
        else:
            background.pop("blur", None)

    for key in ["saturate", "brightness", "opacity"]:
        raw = str(form.get(f"background_{key}", "")).strip()
        if raw:
            try:
                value = int(raw)
            except ValueError as exc:
                raise ConfigError(f"背景 {key} 必须是整数。") from exc
            if key == "opacity" and not 0 <= value <= 100:
                raise ConfigError("背景 opacity 必须在 0–100 之间。")
            if key in {"saturate", "brightness"} and not 0 <= value <= 200:
                raise ConfigError(f"背景 {key} 必须在 0–200 之间。")
            background[key] = value
        else:
            background.pop(key, None)
    if background:
        data["background"] = background

    existing_ql = old.get("quicklaunch") if isinstance(old.get("quicklaunch"), dict) else CommentedMap()
    ql = copy.deepcopy(existing_ql)
    provider = str(form.get("quicklaunch_provider", "")).strip()
    if provider:
        ql["provider"] = provider
    else:
        ql.pop("provider", None)

    full_form = str(form.get("settings_form_version", "")) == "3"
    if full_form:
        for key in ["searchDescriptions", "hideInternetSearch", "showSearchSuggestions", "hideVisitURL"]:
            if form.get(f"quicklaunch_{key}"):
                ql[key] = True
            else:
                ql.pop(key, None)
        mobile = str(form.get("quicklaunch_mobileButtonPosition", "")).strip()
        if mobile:
            ql["mobileButtonPosition"] = mobile
        else:
            ql.pop("mobileButtonPosition", None)
        if provider == "custom":
            for key in ["url", "target", "suggestionUrl"]:
                value = str(form.get(f"quicklaunch_{key}", "")).strip()
                if value:
                    ql[key] = value
                else:
                    ql.pop(key, None)
        else:
            for key in ["url", "target", "suggestionUrl"]:
                ql.pop(key, None)
    if ql:
        data["quicklaunch"] = ql

    layout_names = form.getlist("layout_name")
    old_layout = old.get("layout") if isinstance(old.get("layout"), dict) else {}
    layout = CommentedMap()
    for idx, name_value in enumerate(layout_names):
        name = str(name_value).strip()
        if not name:
            continue
        cfg = CommentedMap()
        prefix = f"layout_{idx}_"
        style = str(form.get(prefix + "style", "")).strip()
        columns = str(form.get(prefix + "columns", "")).strip()
        tab = str(form.get(prefix + "tab", "")).strip()
        icon = str(form.get(prefix + "icon", "")).strip()
        if style:
            cfg["style"] = style
        if columns:
            try:
                column_value = int(columns)
            except ValueError as exc:
                raise ConfigError(f"分组“{name}”的列数必须是整数。") from exc
            if not 1 <= column_value <= 12:
                raise ConfigError(f"分组“{name}”的列数必须在 1–12 之间。")
            cfg["columns"] = column_value
        if tab:
            cfg["tab"] = tab
        if icon:
            cfg["icon"] = icon
        if form.get(prefix + "iconsOnly"):
            cfg["iconsOnly"] = True
        if not form.get(prefix + "header"):
            cfg["header"] = False
        if form.get(prefix + "useEqualHeights"):
            cfg["useEqualHeights"] = True
        if form.get(prefix + "initiallyCollapsed"):
            cfg["initiallyCollapsed"] = True

        extra_cfg = store.parse_fragment(str(form.get(prefix + "extra", "")), dict)
        old_cfg = old_layout.get(name, {}) if isinstance(old_layout, dict) else {}
        if isinstance(old_cfg, dict):
            try:
                extra_cfg = restore_masked_secrets(extra_cfg, old_cfg)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
        for key, value in extra_cfg.items():
            if key not in cfg:
                cfg[key] = value

        was_configured = str(form.get(prefix + "configured", "0")) == "1"
        if cfg or was_configured:
            layout[name] = cfg
    if layout:
        data["layout"] = layout

    extra = store.parse_fragment(str(form.get("extra", "")), dict)
    try:
        extra = restore_masked_secrets(extra, old)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    for key, value in extra.items():
        if key not in data:
            data[key] = value
    return data


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        data = store.load("settings.yaml")
        values = _settings_values(data)
        known = {
            "title", "description", "startUrl", "base", "language", "favicon", "theme", "color", "headerStyle",
            "target", "statusStyle", "iconStyle", "cardBlur", "bookmarksStyle", "maxGroupColumns",
            "maxBookmarkGroupColumns", "fullWidth", "hideVersion", "disableUpdateCheck", "showStats", "hideErrors",
            "disableIndexing", "useEqualHeights", "disableCollapse", "groupsInitiallyCollapsed", "background",
            "quicklaunch", "layout",
        }
        extra = CommentedMap((k, copy.deepcopy(v)) for k, v in data.items() if k not in known)
        values["extra"] = store.dump_fragment(mask_secrets(extra)) if extra else ""
        error = request.query_params.get("error")
    except ConfigError as exc:
        values, error = {}, str(exc)
    return templates.TemplateResponse(
        request,
        "settings.html",
        context(
            request,
            "settings",
            values=values,
            ok=request.query_params.get("ok"),
            error=error,
            colors=HOMEPAGE_COLOR_OPTIONS,
            languages=HOMEPAGE_LANGUAGE_OPTIONS,
            header_styles=HOMEPAGE_HEADER_STYLES,
            status_styles=HOMEPAGE_STATUS_STYLES,
            icon_styles=HOMEPAGE_ICON_STYLES,
            card_blurs=HOMEPAGE_CARD_BLURS,
            background_blurs=HOMEPAGE_BACKGROUND_BLURS,
            quicklaunch_providers=HOMEPAGE_QUICKLAUNCH_PROVIDERS,
            mobile_button_positions=HOMEPAGE_MOBILE_BUTTON_POSITIONS,
        ),
    )


@app.post("/api/settings/preview")
async def preview_settings_change(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        current = store.load("settings.yaml")
        proposed = _build_settings_change(form)
        before = store.dump(mask_secrets(current)).splitlines()
        after = store.dump(mask_secrets(proposed)).splitlines()
        diff = "\n".join(
            difflib.unified_diff(before, after, fromfile="settings.yaml · 当前", tofile="settings.yaml · 保存后", lineterm="")
        )
        return JSONResponse({"ok": True, "changed": before != after, "diff": diff or "无实际变化。"})
    except (ConfigError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/settings")
async def save_settings(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        old = store.load("settings.yaml")
        data = _build_settings_change(form)
        if old == data:
            return redirect("/settings", ok="未检测到设置变化：settings.yaml 未写入，也没有生成新备份。")
        store.write_data("settings.yaml", data, actor(request), "update settings")
        return redirect("/settings", ok="页面设置已保存。请在 Homepage 右下角点击刷新图标使设置重新生成。")
    except ConfigError as exc:
        return redirect("/settings", error=str(exc))


def widgets_view() -> list[dict[str, Any]]:
    data = store.load("widgets.yaml")
    rows = []
    for index, entry in enumerate(data):
        try:
            name, cfg = first_pair(entry)
            rows.append({"index": index, "name": name, "config": store.dump_fragment(mask_secrets(cfg))})
        except ConfigError:
            rows.append({"index": index, "name": f"无效组件 #{index + 1}", "config": store.dump_fragment(mask_secrets(entry))})
    return rows


@app.get("/widgets", response_class=HTMLResponse)
def widgets_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        rows = widgets_view()
        error = request.query_params.get("error")
    except ConfigError as exc:
        rows, error = [], str(exc)
    return templates.TemplateResponse(
        request,
        "widgets.html",
        context(
            request,
            "widgets",
            rows=rows,
            ok=request.query_params.get("ok"),
            error=error,
        ),
    )


@app.get("/widgets/new", response_class=HTMLResponse)
def new_widget(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "widget_form.html",
        context(request, "widgets", mode="new", index=None, name="", config="{}"),
    )


@app.get("/widgets/{index}/edit", response_class=HTMLResponse)
def edit_widget(request: Request, index: int, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        row = widgets_view()[index]
    except (ConfigError, IndexError) as exc:
        return redirect("/widgets", error=str(exc))
    return templates.TemplateResponse(
        request,
        "widget_form.html",
        context(request, "widgets", mode="edit", index=index, name=row["name"], config=row["config"]),
    )


async def save_widget(request: Request, index: int | None) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        name = str(form.get("name", "")).strip()
        if not name:
            raise ConfigError("组件类型不能为空。")
        cfg = store.parse_any(str(form.get("config", "")))
        data = store.load("widgets.yaml")
        if index is not None:
            try:
                _, old_cfg = first_pair(data[index])
                cfg = restore_masked_secrets(cfg, old_cfg)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
        entry = CommentedMap({name: cfg})
        if index is None:
            data.append(entry)
            action = f"create widget {name}"
        else:
            data[index] = entry
            action = f"update widget {name}"
        store.write_data("widgets.yaml", data, actor(request), action)
        return redirect("/widgets", ok=f"顶部组件“{name}”已保存。")
    except (ConfigError, IndexError) as exc:
        return redirect("/widgets", error=str(exc))


@app.post("/widgets/create")
async def create_widget(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    return await save_widget(request, None)


@app.post("/widgets/{index}/update")
async def update_widget(request: Request, index: int, _: None = Depends(auth_guard)) -> RedirectResponse:
    return await save_widget(request, index)


@app.post("/widgets/{index}/delete")
async def delete_widget(request: Request, index: int, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("widgets.yaml")
        name, _ = first_pair(data[index])
        del data[index]
        store.write_data("widgets.yaml", data, actor(request), f"delete widget {name}")
        return redirect("/widgets", ok=f"已删除组件“{name}”。")
    except (ConfigError, IndexError) as exc:
        return redirect("/widgets", error=str(exc))


@app.post("/widgets/{index}/move")
async def move_widget(request: Request, index: int, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    direction = str(form.get("direction", ""))
    try:
        data = store.load("widgets.yaml")
        destination = index - 1 if direction == "up" else index + 1
        if 0 <= destination < len(data):
            data[index], data[destination] = data[destination], data[index]
            store.write_data("widgets.yaml", data, actor(request), f"move widget {index} {direction}")
        return redirect("/widgets", ok="组件顺序已更新。")
    except ConfigError as exc:
        return redirect("/widgets", error=str(exc))


@app.post("/api/widgets/reorder")
async def reorder_widget(request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    verify_csrf(request, request.headers.get("x-csrf-token"))
    payload = await request.json()
    try:
        source_index = int(payload["source_index"])
        target_index = int(payload["target_index"])
        data = store.load("widgets.yaml")
        item = data.pop(source_index)
        if target_index > source_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(data)))
        data.insert(target_index, item)
        store.write_data("widgets.yaml", data, actor(request), "drag widget")
        return JSONResponse({"ok": True})
    except (KeyError, ValueError, IndexError, ConfigError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.get("/yaml", response_class=HTMLResponse)
def yaml_index(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return redirect("/yaml/services.yaml")


@app.get("/yaml/{filename}", response_class=HTMLResponse)
def yaml_editor(request: Request, filename: str, _: None = Depends(auth_guard)) -> HTMLResponse:
    reveal = request.query_params.get("reveal") == "1"
    try:
        if filename.endswith((".yaml", ".yml")) and not reveal:
            data = store.load(filename)
            text = store.dump(mask_secrets(data))
            masked = True
        else:
            text = store.read_text(filename)
            masked = False
        error = request.query_params.get("error")
    except ConfigError as exc:
        raise HTTPException(404, detail=str(exc))
    return templates.TemplateResponse(
        request,
        "yaml_editor.html",
        context(
            request,
            "yaml",
            filename=filename,
            files=list(ALLOWED_FILES.keys()),
            text=text,
            masked=masked,
            reveal=reveal,
            secret_placeholder=SECRET_PLACEHOLDER,
            ok=request.query_params.get("ok"),
            error=error,
        ),
    )


@app.post("/api/yaml/{filename}/diff")
async def preview_yaml_diff(filename: str, request: Request, _: None = Depends(auth_guard)) -> JSONResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    text = str(form.get("content", ""))
    masked = str(form.get("masked", "")) == "1"
    try:
        current_text = store.read_text(filename)
        if filename.endswith((".yaml", ".yml")):
            current = store.load(filename)
            edited = store.validate_text(filename, text)
            if masked:
                try:
                    proposed = restore_masked_secrets(edited, current)
                except ValueError as exc:
                    raise ConfigError(str(exc)) from exc
            else:
                proposed = edited
            before = store.dump(mask_secrets(current)).splitlines()
            after = store.dump(mask_secrets(proposed)).splitlines()
        else:
            store.validate_text(filename, text)
            before = current_text.splitlines()
            after = text.splitlines()
        diff = "\n".join(difflib.unified_diff(before, after, fromfile=f"{filename} · 当前", tofile=f"{filename} · 保存后", lineterm=""))
        return JSONResponse({"ok": True, "changed": before != after, "diff": diff or "无实际变化。"})
    except ConfigError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


@app.post("/yaml/{filename}")
async def save_yaml(filename: str, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    text = str(form.get("content", ""))
    masked = str(form.get("masked", "")) == "1"
    try:
        if masked and filename.endswith((".yaml", ".yml")):
            original = store.load(filename)
            edited = store.validate_text(filename, text)
            try:
                restored = restore_masked_secrets(edited, original)
            except ValueError as exc:
                raise ConfigError(str(exc)) from exc
            if deep_plain(restored) == deep_plain(original):
                suffix = "" if masked else "?reveal=1"
                separator = "&" if suffix else "?"
                return RedirectResponse(f"/yaml/{filename}{suffix}{separator}ok={quote(filename + ' 没有实际变化，未写入，也没有生成备份。')}", status_code=303)
            store.write_data(filename, restored, actor(request), "advanced editor save (masked)")
        else:
            if text == store.read_text(filename):
                suffix = "" if masked else "?reveal=1"
                separator = "&" if suffix else "?"
                return RedirectResponse(f"/yaml/{filename}{suffix}{separator}ok={quote(filename + ' 没有实际变化，未写入，也没有生成备份。')}", status_code=303)
            store.write_text(filename, text, actor(request), "advanced editor save")
        suffix = "" if masked else "?reveal=1"
        separator = "&" if suffix else "?"
        return RedirectResponse(
            f"/yaml/{filename}{suffix}{separator}ok={quote(filename + ' 已保存并通过语法校验。')}",
            status_code=303,
        )
    except ConfigError as exc:
        base = f"/yaml/{filename}" + ("" if masked else "?reveal=1")
        separator = "&" if "?" in base else "?"
        return RedirectResponse(base + separator + "error=" + quote(str(exc)), status_code=303)


@app.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "backups.html",
        context(
            request,
            "backups",
            backups=store.list_backups(),
            backup_limit=store.backup_limit(),
            backup_limit_default=max(1, min(settings.backup_limit, 500)),
            backup_limit_custom=store.backup_limit_is_custom(),
            ok=request.query_params.get("ok"),
            error=request.query_params.get("error"),
        ),
    )


@app.post("/backups/settings")
async def update_backup_settings(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        limit = int(str(form.get("backup_limit", "")).strip())
        saved = store.set_backup_limit(limit, actor(request))
        return redirect("/backups", ok=f"备份保留上限已更新为 {saved} 组；超出部分已按时间自动清理。")
    except (TypeError, ValueError):
        return redirect("/backups", error="请输入 1 到 500 之间的整数。")
    except ConfigError as exc:
        return redirect("/backups", error=str(exc))


@app.post("/backups/settings/reset")
async def reset_backup_settings(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        value = store.reset_backup_limit(actor(request))
        return redirect("/backups", ok=f"已恢复环境默认备份上限：{value} 组。")
    except ConfigError as exc:
        return redirect("/backups", error=str(exc))


@app.post("/backups/{backup_id}/{filename}/restore")
async def restore_backup(
    request: Request, backup_id: str, filename: str, _: None = Depends(auth_guard)
) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        store.restore(backup_id, filename, actor(request))
        return redirect("/backups", ok=f"已从 {backup_id} 恢复 {filename}。恢复前的当前文件也已自动备份。")
    except ConfigError as exc:
        return redirect("/backups", error=str(exc))


@app.post("/backups/{backup_id}/delete")
async def delete_backup(
    request: Request, backup_id: str, _: None = Depends(auth_guard)
) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        store.delete_backup(backup_id, actor(request))
        return redirect("/backups", ok=f"备份 {backup_id} 已删除。")
    except ConfigError as exc:
        return redirect("/backups", error=str(exc))


@app.post("/backups/delete-all")
async def delete_all_backups(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        count = store.delete_all_backups(actor(request))
        return redirect("/backups", ok=f"已删除 {count} 组备份。" if count else "当前没有可删除的备份。")
    except ConfigError as exc:
        return redirect("/backups", error=str(exc))


@app.exception_handler(ConfigError)
def config_error_handler(request: Request, exc: ConfigError) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        context(request, "", title="配置错误", message=str(exc)),
        status_code=400,
    )
