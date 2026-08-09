from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .widget_catalog import WIDGET_CATALOG


class WidgetTestError(RuntimeError):
    pass


def _base(url: str) -> str:
    value = str(url or "").strip().rstrip("/")
    if not value:
        raise WidgetTestError("缺少 Widget 地址。")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise WidgetTestError("连接测试目前要求 http:// 或 https:// 地址。")
    return value


def _basic_auth(config: dict[str, Any]) -> tuple[str, str] | None:
    username = str(config.get("username") or "")
    password = str(config.get("password") or "")
    return (username, password) if username or password else None


def _result(message: str, metrics: list[dict[str, Any]] | None = None, *, level: str = "deep") -> dict[str, Any]:
    return {"ok": True, "message": message, "metrics": metrics or [], "level": level}


async def _basic_reachability(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    auth = _basic_auth(config)
    async with httpx.AsyncClient(timeout=5.0, verify=False, follow_redirects=True) as client:
        response = await client.get(url, auth=auth)
    if response.status_code >= 500:
        raise WidgetTestError(f"服务可达，但返回 HTTP {response.status_code}。")
    return _result(f"服务地址可达（HTTP {response.status_code}）。此 Widget 当前执行基础连通测试。", level="basic")


async def _test_jellyfin(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    key = str(config.get("key") or "")
    if not key:
        raise WidgetTestError("缺少 Jellyfin API Key。")
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        response = await client.get(f"{url}/System/Info", headers={"X-Emby-Token": key})
    if response.status_code in {401, 403}:
        raise WidgetTestError("Jellyfin API Key 无效或权限不足。")
    response.raise_for_status()
    payload = response.json() if response.content else {}
    version = payload.get("Version") if isinstance(payload, dict) else None
    name = payload.get("ServerName") if isinstance(payload, dict) else None
    metrics = []
    if name:
        metrics.append({"label": "Server", "value": name})
    if version:
        metrics.append({"label": "Version", "value": version})
    return _result("Jellyfin API 认证成功。", metrics)


async def _test_portainer(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    key = str(config.get("key") or "")
    env = config.get("env")
    if not key:
        raise WidgetTestError("缺少 Portainer API Key。")
    if env in (None, ""):
        raise WidgetTestError("缺少 Portainer Environment ID。")
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        response = await client.get(
            f"{url}/api/endpoints/{env}/docker/containers/json",
            params={"all": "1"},
            headers={"X-API-Key": key},
        )
    if response.status_code in {401, 403}:
        raise WidgetTestError("Portainer API Key 无效或没有访问该 Environment 的权限。")
    if response.status_code == 404:
        raise WidgetTestError("Portainer 返回 404：请检查 Environment ID 是否正确。")
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise WidgetTestError("Portainer 返回了非预期数据。")
    running = sum(1 for item in items if str(item.get("State", "")).lower() == "running")
    total = len(items)
    return _result(
        "Portainer API 认证成功，Environment 可用。",
        [
            {"label": "Running", "value": running},
            {"label": "Stopped", "value": max(0, total - running)},
            {"label": "Total", "value": total},
        ],
    )


async def _test_proxmox(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    username = str(config.get("username") or "")
    secret = str(config.get("password") or "")
    if not username or not secret:
        raise WidgetTestError("缺少 Proxmox API Token ID 或 Token Secret。")
    headers = {"Authorization": f"PVEAPIToken={username}={secret}"}
    async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
        response = await client.get(f"{url}/api2/json/cluster/resources", params={"type": "vm"}, headers=headers)
        if response.status_code in {401, 403}:
            raise WidgetTestError("Proxmox Token 无效或权限不足。")
        response.raise_for_status()
        data = response.json().get("data", [])
        nodes = await client.get(f"{url}/api2/json/nodes", headers=headers)
        nodes.raise_for_status()
        node_data = nodes.json().get("data", [])
    vms = [item for item in data if item.get("type") == "qemu"]
    lxcs = [item for item in data if item.get("type") == "lxc"]
    return _result(
        "Proxmox API Token 认证成功。",
        [
            {"label": "VM", "value": f"{sum(1 for x in vms if x.get('status') == 'running')}/{len(vms)}"},
            {"label": "LXC", "value": f"{sum(1 for x in lxcs if x.get('status') == 'running')}/{len(lxcs)}"},
            {"label": "Nodes", "value": len(node_data)},
        ],
    )


async def _test_homeassistant(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    key = str(config.get("key") or "")
    if not key:
        raise WidgetTestError("缺少 Home Assistant 长期访问令牌。")
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        response = await client.get(f"{url}/api/", headers={"Authorization": f"Bearer {key}"})
    if response.status_code in {401, 403}:
        raise WidgetTestError("Home Assistant 长期访问令牌无效。")
    response.raise_for_status()
    return _result("Home Assistant API 认证成功。")


async def _test_qbittorrent(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    username = str(config.get("username") or "")
    password = str(config.get("password") or "")
    async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
        if username or password:
            login = await client.post(f"{url}/api/v2/auth/login", data={"username": username, "password": password})
            if login.status_code >= 400 or login.text.strip().lower().startswith("fail"):
                raise WidgetTestError("qBittorrent WebUI 用户名或密码错误。")
        response = await client.get(f"{url}/api/v2/torrents/info")
    if response.status_code in {401, 403}:
        raise WidgetTestError("qBittorrent API 认证失败。")
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise WidgetTestError("qBittorrent 返回了非预期数据。")
    downloading = sum(1 for item in items if "dl" in str(item.get("state", "")).lower() or str(item.get("state", "")).lower() in {"downloading", "stalleddl", "metadl"})
    seeding = sum(1 for item in items if "up" in str(item.get("state", "")).lower() or str(item.get("state", "")).lower() in {"uploading", "stalledup", "forcedup"})
    return _result("qBittorrent API 认证成功。", [{"label": "Downloading", "value": downloading}, {"label": "Seeding", "value": seeding}, {"label": "Total", "value": len(items)}])


async def _test_transmission(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    rpc_url = str(config.get("rpcUrl") or "/transmission/").strip() or "/transmission/"
    if not rpc_url.startswith("/"):
        rpc_url = "/" + rpc_url
    endpoint = f"{url}{rpc_url.rstrip('/')}/rpc"
    auth = _basic_auth(config)
    body = {"method": "session-stats"}
    async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
        response = await client.post(endpoint, json=body, auth=auth)
        if response.status_code == 409:
            session_id = response.headers.get("X-Transmission-Session-Id")
            if not session_id:
                raise WidgetTestError("Transmission 未返回 Session ID。")
            response = await client.post(endpoint, json=body, auth=auth, headers={"X-Transmission-Session-Id": session_id})
    if response.status_code in {401, 403}:
        raise WidgetTestError("Transmission 用户名或密码错误。")
    response.raise_for_status()
    payload = response.json()
    args = payload.get("arguments", {}) if isinstance(payload, dict) else {}
    return _result(
        "Transmission RPC 连接成功。",
        [
            {"label": "Active", "value": args.get("activeTorrentCount", 0)},
            {"label": "Paused", "value": args.get("pausedTorrentCount", 0)},
            {"label": "Total", "value": args.get("torrentCount", 0)},
        ],
    )


async def _test_glances(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    version = int(config.get("version") or 3)
    auth = _basic_auth(config)
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        response = await client.get(f"{url}/api/{version}/status", auth=auth)
    if response.status_code in {401, 403}:
        raise WidgetTestError("Glances API 认证失败。")
    response.raise_for_status()
    return _result(f"Glances API v{version} 可达。")


async def _test_customapi(config: dict[str, Any]) -> dict[str, Any]:
    url = _base(str(config.get("url") or ""))
    method = str(config.get("method") or "GET").upper()
    if method not in {"GET", "POST"}:
        raise WidgetTestError("Custom API 测试目前支持 GET / POST。")
    headers = config.get("headers") if isinstance(config.get("headers"), dict) else {}
    request_body = config.get("requestBody")
    async with httpx.AsyncClient(timeout=6.0, verify=False, follow_redirects=True) as client:
        response = await client.request(method, url, headers=headers, json=request_body if isinstance(request_body, (dict, list)) else None)
    if response.status_code >= 400:
        raise WidgetTestError(f"Custom API 返回 HTTP {response.status_code}。")
    content_type = response.headers.get("content-type", "")
    metrics = [{"label": "HTTP", "value": response.status_code}]
    if "json" in content_type:
        try:
            payload = response.json()
            kind = "array" if isinstance(payload, list) else "object" if isinstance(payload, dict) else type(payload).__name__
            metrics.append({"label": "JSON", "value": kind})
        except ValueError:
            pass
    return _result("Custom API 请求成功。", metrics)


async def test_widget(widget_type: str, config: dict[str, Any]) -> dict[str, Any]:
    widget_type = str(widget_type or "").strip().lower()
    schema = WIDGET_CATALOG.get(widget_type)
    if not schema:
        raise WidgetTestError("该 Widget 尚未加入连接测试目录，可继续使用 YAML 配置。")

    missing = []
    for field in schema.get("fields", []):
        if field.get("required") and not config.get(field.get("name")):
            missing.append(str(field.get("label") or field.get("name")))
    if missing:
        raise WidgetTestError("缺少必填字段：" + "、".join(missing))

    mode = schema.get("test", "basic")
    testers = {
        "jellyfin": _test_jellyfin,
        "portainer": _test_portainer,
        "proxmox": _test_proxmox,
        "homeassistant": _test_homeassistant,
        "qbittorrent": _test_qbittorrent,
        "transmission": _test_transmission,
        "glances": _test_glances,
        "customapi": _test_customapi,
        "basic": _basic_reachability,
    }
    if mode == "config":
        return _result("该 Widget 已收录官方索引，但当前没有专属 API 测试器；已完成配置级校验。请按官方文档填写其余 YAML 配置。", level="config")
    tester = testers.get(str(mode), _basic_reachability)
    try:
        return await tester(config)
    except WidgetTestError:
        raise
    except httpx.TimeoutException as exc:
        raise WidgetTestError("连接超时：请检查地址、端口、防火墙或容器网络。") from exc
    except httpx.ConnectError as exc:
        raise WidgetTestError("无法建立连接：请检查地址、端口、DNS 或服务是否运行。") from exc
    except httpx.HTTPStatusError as exc:
        raise WidgetTestError(f"服务返回 HTTP {exc.response.status_code}。") from exc
    except (ValueError, TypeError) as exc:
        raise WidgetTestError(f"服务返回数据无法解析：{exc}") from exc
