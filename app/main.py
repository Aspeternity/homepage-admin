from __future__ import annotations

import copy
import json
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
from .security import ensure_csrf, login_limiter, require_auth, verify_csrf, verify_password
from .settings import settings
from .store import ALLOWED_FILES, ConfigError, deep_plain, store

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Homepage Admin", version=__version__, docs_url=None, redoc_url=None)
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
            subtitle="管理 bookmarks.yaml 中的轻量链接和 PT 站点。",
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


def service_form_values(data: list[Any], group_index: int, item_index: int | None) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": "",
        "icon": "",
        "href": "",
        "description": "",
        "target": "",
        "siteMonitor": "",
        "ping": "",
        "server": "",
        "container": "",
        "widget_type": "",
        "widget_url": "",
        "widget_has_key": False,
        "widget_extra": "",
        "extra": "",
        "multiple_widgets": False,
    }
    if item_index is None:
        return values
    _, items = first_pair(data[group_index])
    name, details = first_pair(items[item_index])
    if not isinstance(details, dict):
        raise ConfigError("嵌套分组暂不支持表单编辑，请使用高级 YAML 编辑器。")
    values["name"] = name
    known = {"icon", "href", "description", "target", "siteMonitor", "ping", "server", "container"}
    for key in known:
        values[key] = details.get(key, "")
    extra = CommentedMap((k, copy.deepcopy(v)) for k, v in details.items() if k not in known | {"widget"})
    if "widgets" in details:
        values["multiple_widgets"] = True
    widget = details.get("widget")
    if isinstance(widget, dict):
        values["widget_type"] = widget.get("type", "")
        values["widget_url"] = widget.get("url", "")
        values["widget_has_key"] = "key" in widget and bool(widget.get("key"))
        widget_extra = CommentedMap(
            (k, copy.deepcopy(v)) for k, v in widget.items() if k not in {"type", "url", "key"}
        )
        values["widget_extra"] = store.dump_fragment(widget_extra) if widget_extra else ""
    values["extra"] = store.dump_fragment(extra) if extra else ""
    return values


@app.get("/services/item/new", response_class=HTMLResponse)
def new_service(request: Request, group: int = 0, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        data = store.load("services.yaml")
        names = group_names("services.yaml")
        if not names:
            return redirect("/services", error="请先创建一个服务分组。")
        group = min(max(group, 0), len(names) - 1)
        values = service_form_values(data, group, None)
        error = None
    except ConfigError as exc:
        names, values, error = [], {}, str(exc)
    return templates.TemplateResponse(
        request,
        "service_form.html",
        context(request, "services", mode="new", group_index=group, item_index=None, groups=names, values=values, error=error),
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
    return templates.TemplateResponse(
        request,
        "service_form.html",
        context(
            request,
            "services",
            mode="edit",
            group_index=group_index,
            item_index=item_index,
            groups=names,
            values=values,
            error=error,
        ),
    )


async def save_service(request: Request, group_index: int, item_index: int | None) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    try:
        data = store.load("services.yaml")
        target_group = int(str(form.get("group_index", group_index)))
        name = str(form.get("name", "")).strip()
        if not name:
            raise ConfigError("服务名称不能为空。")
        details = CommentedMap()
        field_order = ["icon", "href", "description", "target", "siteMonitor", "ping", "server", "container"]
        for key in field_order:
            value = str(form.get(key, "")).strip()
            if value:
                details[key] = value
        extra = store.parse_fragment(str(form.get("extra", "")), dict)
        for key, value in extra.items():
            if key in details or key == "widget":
                continue
            details[key] = value

        old_widget_key = None
        if item_index is not None:
            _, old_items = first_pair(data[group_index])
            _, old_details = first_pair(old_items[item_index])
            if isinstance(old_details, dict) and isinstance(old_details.get("widget"), dict):
                old_widget_key = old_details["widget"].get("key")

        widget_type = str(form.get("widget_type", "")).strip()
        widget_url = str(form.get("widget_url", "")).strip()
        widget_key = str(form.get("widget_key", "")).strip()
        widget_extra_text = str(form.get("widget_extra", ""))
        if widget_type or widget_url or widget_key or old_widget_key or widget_extra_text.strip():
            widget = CommentedMap()
            if widget_type:
                widget["type"] = widget_type
            if widget_url:
                widget["url"] = widget_url
            if widget_key:
                widget["key"] = widget_key
            elif old_widget_key:
                widget["key"] = old_widget_key
            widget_extra = store.parse_fragment(widget_extra_text, dict)
            for key, value in widget_extra.items():
                if key not in widget:
                    widget[key] = value
            details["widget"] = widget

        new_entry = CommentedMap({name: details})
        if item_index is None:
            _, target_items = first_pair(data[target_group])
            target_items.append(new_entry)
            action = f"create service {name}"
        else:
            _, source_items = first_pair(data[group_index])
            if target_group == group_index:
                source_items[item_index] = new_entry
            else:
                del source_items[item_index]
                _, target_items = first_pair(data[target_group])
                target_items.append(new_entry)
            action = f"update service {name}"
        store.write_data("services.yaml", data, actor(request), action)
        return redirect("/services", ok=f"服务“{name}”已保存。")
    except (ConfigError, IndexError, ValueError) as exc:
        return redirect("/services", error=str(exc))


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
    values["extra"] = store.dump_fragment(extra) if extra else ""
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
        for key, value in extra.items():
            if key not in details:
                details[key] = value
        details_list = CommentedSeq([details])
        if item_index is not None:
            _, source_items = first_pair(data[group_index])
            _, old_list = first_pair(source_items[item_index])
            if isinstance(old_list, list) and len(old_list) > 1:
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
        if source_group == target_group and target_index > source_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(target_items)))
        target_items.insert(target_index, item)
        store.write_data(filename, data, actor(request), "drag item")
        return JSONResponse({"ok": True})
    except (KeyError, ValueError, IndexError, ConfigError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


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
                                    "collapsible",
                                    "initiallyCollapsed",
                                }
                            )
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
        values["extra"] = store.dump_fragment(extra) if extra else ""
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
        if form.get("fullWidth"):
            data["fullWidth"] = True
        if form.get("hideVersion"):
            data["hideVersion"] = True

        old_background = old.get("background", CommentedMap())
        if isinstance(old_background, str):
            old_background = CommentedMap({"image": old_background})
        background = copy.deepcopy(old_background) if isinstance(old_background, dict) else CommentedMap()
        for known_key in ["image", "blur", "saturate", "brightness", "opacity"]:
            background.pop(known_key, None)
        image = str(form.get("background_image", "")).strip()
        if image:
            background["image"] = image
        for key in ["blur", "saturate", "brightness", "opacity"]:
            value = str(form.get(f"background_{key}", "")).strip()
            if value:
                if key in {"saturate", "brightness", "opacity"}:
                    try:
                        background[key] = int(value)
                    except ValueError:
                        raise ConfigError(f"背景 {key} 必须是整数。")
                else:
                    background[key] = value
        if background:
            data["background"] = background

        provider = str(form.get("quicklaunch_provider", "")).strip()
        if provider:
            existing_ql = old.get("quicklaunch") if isinstance(old.get("quicklaunch"), dict) else CommentedMap()
            ql = copy.deepcopy(existing_ql)
            ql["provider"] = provider
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
            for key, value in extra_cfg.items():
                if key not in cfg:
                    cfg[key] = value
            layout[name] = cfg
        if layout:
            data["layout"] = layout

        extra = store.parse_fragment(str(form.get("extra", "")), dict)
        for key, value in extra.items():
            if key not in data:
                data[key] = value
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
            rows.append({"index": index, "name": name, "config": store.dump_fragment(cfg)})
        except ConfigError:
            rows.append({"index": index, "name": f"无效组件 #{index + 1}", "config": store.dump_fragment(entry)})
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


@app.get("/yaml", response_class=HTMLResponse)
def yaml_index(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return redirect("/yaml/services.yaml")


@app.get("/yaml/{filename}", response_class=HTMLResponse)
def yaml_editor(request: Request, filename: str, _: None = Depends(auth_guard)) -> HTMLResponse:
    try:
        text = store.read_text(filename)
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
            ok=request.query_params.get("ok"),
            error=error,
        ),
    )


@app.post("/yaml/{filename}")
async def save_yaml(filename: str, request: Request, _: None = Depends(auth_guard)) -> RedirectResponse:
    form = await request.form()
    verify_csrf(request, str(form.get("csrf", "")))
    text = str(form.get("content", ""))
    try:
        store.write_text(filename, text, actor(request), "advanced editor save")
        return redirect(f"/yaml/{filename}", ok=f"{filename} 已保存并通过语法校验。")
    except ConfigError as exc:
        return redirect(f"/yaml/{filename}", error=str(exc))


@app.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request, _: None = Depends(auth_guard)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "backups.html",
        context(
            request,
            "backups",
            backups=store.list_backups(),
            ok=request.query_params.get("ok"),
            error=request.query_params.get("error"),
        ),
    )


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


@app.exception_handler(ConfigError)
def config_error_handler(request: Request, exc: ConfigError) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error.html",
        context(request, "", title="配置错误", message=str(exc)),
        status_code=400,
    )
