from __future__ import annotations

import asyncio
import copy
from contextlib import asynccontextmanager, suppress
import difflib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
from .proxmox_client import ProxmoxConnection, ProxmoxDiscoveryClient, ProxmoxDiscoveryError
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


def configured_docker_containers() -> dict[str, list[dict[str, str]]]:
    configured: dict[str, list[dict[str, str]]] = {}
    try:
        data = store.load("services.yaml")
    except ConfigError:
        return configured
    for group_entry in data:
        try:
            group_name, items = first_pair(group_entry)
        except ConfigError:
            continue
        if not isinstance(items, list):
            continue
        for entry in items:
            try:
                service_name, details = first_pair(entry)
            except ConfigError:
                continue
            if isinstance(details, dict) and details.get("container"):
                key = str(details.get("container")).casefold()
                configured.setdefault(key, []).append({"group": group_name, "service": service_name})
    return configured


def first_docker_server_name() -> str:
    if settings.docker_server_name:
        return settings.docker_server_name
    try:
        data = store.load("docker.yaml")
    except ConfigError:
        return ""
    if isinstance(data, dict) and data:
        return str(next(iter(data.keys())))
    return ""


def docker_server_info() -> dict[str, Any]:
    name = first_docker_server_name()
    info: dict[str, Any] = {
        "name": name,
        "mode": "none",
        "host": "",
        "port": "",
        "socket": "",
        "recommended": False,
    }
    if not name:
        return info
    try:
        data = store.load("docker.yaml")
    except ConfigError:
        return info
    cfg = data.get(name) if isinstance(data, dict) else None
    if not isinstance(cfg, dict):
        return info
    if cfg.get("socket"):
        info.update({"mode": "socket", "socket": str(cfg.get("socket"))})
        return info
    if cfg.get("host"):
        host = str(cfg.get("host"))
        try:
            port = int(cfg.get("port", 2375))
        except (TypeError, ValueError):
            port = 2375
        recommended = host == settings.homepage_docker_proxy_host and port == settings.homepage_docker_proxy_port
        info.update({"mode": "proxy" if recommended else "remote", "host": host, "port": port, "recommended": recommended})
    return info


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
            bindings[(node, vmid_int, ptype)] = {k: v for k, v in service.items() if k != "details"}
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
    for resource in resources:
        # proxmoxNode must match the proxmox.yaml key, not necessarily the physical node label.
        resource["binding"] = bindings.get((selected, int(resource["vmid"]), str(resource["type"])))
    return templates.TemplateResponse(
        request,
        "proxmox.html",
        context(
            request,
            "proxmox",
            connections=[{"name": name, "url": conn.url} for name, conn in connections.items()],
            selected=selected,
            resources=resources,
            service_choices=[{k: v for k, v in item.items() if k != "details"} for item in _service_choices()],
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
        url = str(widget.get("url") or "").strip()
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
        store.write_data("services.yaml", data, actor(request), f"bind service {service_name} to proxmox {server}/{vmid}")
        return redirect(f"/proxmox?server={quote(server)}", ok=f"已将“{service_name}”关联到 {ptype.upper()} {vmid}。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect(f"/proxmox?server={quote(server)}" if server else "/proxmox", error=str(exc))


@app.get("/docker", response_class=HTMLResponse)
def docker_page(
    request: Request,
    show_internal: bool = False,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    containers: list[dict[str, Any]] = []
    error = request.query_params.get("error")
    configured = configured_docker_containers()
    proxy_healthy = False
    hidden_internal_count = 0
    if not docker_discovery.enabled():
        error = error or "Docker 容器发现未启用。请使用当前 Compose（包含共享只读 Docker Proxy）。"
    else:
        proxy_healthy = docker_discovery.ping()
        try:
            containers = docker_discovery.list_containers()
        except Exception as exc:
            error = error or f"无法读取 Docker 容器：{exc}"
    visible: list[dict[str, Any]] = []
    internal_names = {"homepage-docker-proxy", "homepage-admin-docker-proxy", "docker-proxy"}
    for item in containers:
        name = str(item.get("name", ""))
        item["published_ports"] = [p for p in dedupe_ports(item.get("ports") or []) if p.get("public")]
        labels = item.get("labels") or {}
        item["homepage_labeled"] = any(str(k).startswith("homepage.") for k in labels)
        matches = configured.get(name.casefold(), [])
        item["configured"] = bool(matches)
        item["configured_matches"] = matches
        item["role"] = container_role(item)
        if settings.hide_internal_containers and not show_internal and name.casefold() in internal_names:
            hidden_internal_count += 1
            continue
        visible.append(item)
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
            docker_server=first_docker_server_name(),
            docker_server_info=docker_server_info(),
            proxy_healthy=proxy_healthy,
            proxy_host=settings.homepage_docker_proxy_host,
            proxy_port=settings.homepage_docker_proxy_port,
            show_internal=show_internal,
            hidden_internal_count=hidden_internal_count,
            service_groups=groups,
            recommended_group_index=recommended_import_group(groups),
        ),
    )


@app.post("/docker/setup-homepage")
async def docker_setup_homepage(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("docker.yaml")
        if not isinstance(data, dict):
            raise ConfigError("docker.yaml 必须是对象映射。")
        if data:
            return redirect("/docker", error="docker.yaml 已有配置。可使用“切换为只读代理”迁移当前 Docker server。")
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
        # Keep swarm and other compatible options, but a plain internal HTTP proxy does not use TLS/protocol overrides.
        cfg.pop("tls", None)
        cfg.pop("protocol", None)
        cfg.pop("headers", None)
        store.write_data("docker.yaml", data, actor(request), f"migrate docker server {name} to read-only proxy")
        return redirect(
            "/docker",
            ok=f"已将 {name} 切换为只读代理。请确认 Homepage 也加入 homepage-tools Docker 网络，并移除直接 socket 挂载。",
        )
    except ConfigError as exc:
        return redirect("/docker", error=str(exc))


def docker_import_values(container: dict[str, Any], names: list[str], requested_group: int | None = None) -> tuple[dict[str, Any], int, dict[str, str]]:
    values = empty_service_values()
    sources: dict[str, str] = {}
    profile = infer_service_profile(container)
    label_values = homepage_labels_to_values(container)
    for key in ["name", "icon", "href", "description", "siteMonitor", "ping", "server", "container"]:
        if label_values.get(key):
            values[key] = label_values[key]
            sources[key] = "Homepage Label"

    if not values["name"]:
        values["name"] = str(container.get("name", "Docker Service"))
        sources["name"] = "容器名称"
    if not values["container"]:
        values["container"] = str(container.get("name", ""))
        sources["container"] = "容器名称"
    if not values["server"]:
        values["server"] = first_docker_server_name()
        sources["server"] = "docker.yaml"

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
            host = settings.docker_public_host or public_host_from_url(settings.homepage_url)
            values["href"] = f"http://{host}:{port}"
            sources["href"] = "发布端口"
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


@app.get("/docker/import/{container_id}", response_class=HTMLResponse)
def docker_import_wizard(
    request: Request,
    container_id: str,
    group: int | None = None,
    _: None = Depends(auth_guard),
) -> HTMLResponse:
    if not docker_discovery.enabled():
        return redirect("/docker", error="Docker 容器发现未启用。")
    try:
        container = docker_discovery.get_container(container_id)
        if not container:
            return redirect("/docker", error="未找到该 Docker 容器。")
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        values, group_index, sources = docker_import_values(container, names, group)
        container = dict(container)
        container["published_ports"] = [p for p in dedupe_ports(container.get("ports") or []) if p.get("public")]
        return templates.TemplateResponse(
            request,
            "docker_import_wizard.html",
            context(
                request,
                "docker",
                container=container,
                groups=names,
                group_index=group_index,
                values=values,
                suggestion_sources=sources,
                service_profile=infer_service_profile(container),
                widget_catalog=WIDGET_CATALOG,
            ),
        )
    except Exception as exc:
        return redirect("/docker", error=f"导入容器失败：{exc}")


@app.get("/docker/import/{container_id}/edit", response_class=HTMLResponse)
def docker_import_edit(
    request: Request,
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
    if not docker_discovery.enabled():
        return redirect("/docker", error="Docker 容器发现未启用。")
    try:
        container = docker_discovery.get_container(container_id)
        if not container:
            return redirect("/docker", error="未找到该 Docker 容器。")
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        values, resolved_group, _ = docker_import_values(container, names, group_index)
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
            docker_source=str(container.get("name", "")),
        )
    except Exception as exc:
        return redirect("/docker", error=f"导入容器失败：{exc}")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        data = store.load("settings.yaml")
        background = data.get("background", {})
        if isinstance(background, str):
            background = {"image": background}
        if not isinstance(background, dict):
            background = {}
        quicklaunch = data.get("quicklaunch", {})
        if not isinstance(quicklaunch, dict):
            quicklaunch = {}
        layout = data.get("layout", {})
        layout_rows = []
        if isinstance(layout, dict):
            for name, cfg in layout.items():
                cfg = cfg if isinstance(cfg, dict) else {}
                layout_rows.append(
                    {
                        "name": str(name),
                        "style": cfg.get("style", ""),
                        "columns": cfg.get("columns", ""),
                        "tab": cfg.get("tab", ""),
                        "icon": cfg.get("icon", ""),
                        "iconsOnly": bool(cfg.get("iconsOnly", False)),
                        "header": cfg.get("header", True) is not False,
                        "useEqualHeights": bool(cfg.get("useEqualHeights", False)),
                        "collapsible": bool(cfg.get("collapsible", False)),
                        "initiallyCollapsed": bool(cfg.get("initiallyCollapsed", False)),
                        "extra": store.dump_fragment(
                            mask_secrets(CommentedMap(
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
                                    "collapsible",
                                    "initiallyCollapsed",
                                }
                            ))
                        ),
                    }
                )
        existing_layout_names = {row["name"] for row in layout_rows}
        for missing_name in group_names("services.yaml") + group_names("bookmarks.yaml"):
            if missing_name not in existing_layout_names:
                layout_rows.append({
                    "name": missing_name,
                    "style": "row",
                    "columns": 4 if missing_name in group_names("services.yaml") else 5,
                    "tab": "",
                    "icon": "",
                    "iconsOnly": False,
                    "header": True,
                    "useEqualHeights": True,
                    "collapsible": False,
                    "initiallyCollapsed": False,
                    "extra": "",
                })
                existing_layout_names.add(missing_name)

        values = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "language": data.get("language", "zh-CN"),
            "favicon": data.get("favicon", ""),
            "theme": data.get("theme", ""),
            "color": data.get("color", ""),
            "headerStyle": data.get("headerStyle", ""),
            "target": data.get("target", ""),
            "statusStyle": data.get("statusStyle", ""),
            "iconStyle": data.get("iconStyle", ""),
            "cardBlur": data.get("cardBlur", ""),
            "fullWidth": bool(data.get("fullWidth", False)),
            "hideVersion": bool(data.get("hideVersion", False)),
            "background": background,
            "quicklaunch_provider": quicklaunch.get("provider", ""),
            "layout": layout_rows,
        }
        known = {
            "title",
            "description",
            "language",
            "favicon",
            "theme",
            "color",
            "headerStyle",
            "target",
            "statusStyle",
            "iconStyle",
            "cardBlur",
            "fullWidth",
            "hideVersion",
            "background",
            "quicklaunch",
            "layout",
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
            service_groups=group_names("services.yaml"),
            bookmark_groups=group_names("bookmarks.yaml"),
        ),
    )


@app.post("/settings")
async def save_settings(request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        old = store.load("settings.yaml")
        data = CommentedMap()
        for key in ["language", "title", "description", "favicon", "theme", "color", "headerStyle", "target", "statusStyle", "iconStyle", "cardBlur"]:
            value = str(form.get(key, "")).strip()
            if value:
                data[key] = value
            elif key in old and old.get(key) == "":
                # Preserve an explicitly-empty value when the form is unchanged.
                # Some Homepage options distinguish an empty value from an absent key.
                data[key] = ""
        if form.get("fullWidth"):
            data["fullWidth"] = True
        elif "fullWidth" in old and old.get("fullWidth") is False:
            data["fullWidth"] = False
        if form.get("hideVersion"):
            data["hideVersion"] = True
        elif "hideVersion" in old and old.get("hideVersion") is False:
            data["hideVersion"] = False

        old_background = old.get("background", CommentedMap())
        if isinstance(old_background, str):
            old_background = CommentedMap({"image": old_background})
        background = copy.deepcopy(old_background) if isinstance(old_background, dict) else CommentedMap()

        image = str(form.get("background_image", "")).strip()
        if image:
            background["image"] = image
        else:
            background.pop("image", None)

        # Homepage accepts blur: "" as a real filter value.  A blank HTML input
        # therefore cannot blindly mean "delete blur" when the existing YAML
        # explicitly contains an empty string.  Preserve that exact state on a
        # no-op save; clearing a non-empty blur value still removes the key.
        blur_value = str(form.get("background_blur", "")).strip()
        if blur_value:
            background["blur"] = blur_value
        elif isinstance(old_background, dict) and "blur" in old_background and old_background.get("blur") == "":
            background["blur"] = ""
        else:
            background.pop("blur", None)

        for key in ["saturate", "brightness", "opacity"]:
            value = str(form.get(f"background_{key}", "")).strip()
            if value:
                try:
                    background[key] = int(value)
                except ValueError:
                    raise ConfigError(f"背景 {key} 必须是整数。")
            else:
                background.pop(key, None)
        if background:
            data["background"] = background

        provider = str(form.get("quicklaunch_provider", "")).strip()
        existing_ql = old.get("quicklaunch") if isinstance(old.get("quicklaunch"), dict) else CommentedMap()
        ql = copy.deepcopy(existing_ql)
        if provider:
            ql["provider"] = provider
        else:
            ql.pop("provider", None)
        if ql:
            data["quicklaunch"] = ql

        layout_names = form.getlist("layout_name")
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
                    cfg["columns"] = int(columns)
                except ValueError:
                    raise ConfigError(f"分组“{name}”的列数必须是整数。")
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
            if form.get(prefix + "collapsible"):
                cfg["collapsible"] = True
            if form.get(prefix + "initiallyCollapsed"):
                cfg["initiallyCollapsed"] = True
            extra_cfg = store.parse_fragment(str(form.get(prefix + "extra", "")), dict)
            old_layout = old.get("layout") if isinstance(old.get("layout"), dict) else {}
            old_cfg = old_layout.get(name, {}) if isinstance(old_layout, dict) else {}
            if isinstance(old_cfg, dict):
                try:
                    extra_cfg = restore_masked_secrets(extra_cfg, old_cfg)
                except ValueError as exc:
                    raise ConfigError(str(exc)) from exc
            for key, value in extra_cfg.items():
                if key not in cfg:
                    cfg[key] = value
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

        # A true no-op must not rewrite settings.yaml.  Besides avoiding a noisy
        # backup, this preserves comments and intentionally-empty YAML values.
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
