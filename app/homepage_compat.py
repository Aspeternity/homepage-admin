from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import threading
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LATEST_RELEASE_API = "https://api.github.com/repos/gethomepage/homepage/releases/latest"
SUPPORTED_THROUGH = "2.2.0"
USER_AGENT = "Homepage-Admin-Compatibility/0.5.5"

_RELEASE_CACHE_LOCK = threading.RLock()
_RELEASE_CACHE: dict[str, Any] = {"fetched_at": 0.0, "payload": None}
_RELEASE_CACHE_TTL = 30 * 60


def normalize_version(value: str | None) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?<!\d)v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", text)
    if not match:
        return ""
    return ".".join(match.groups())


def version_tuple(value: str | None) -> tuple[int, int, int] | None:
    normalized = normalize_version(value)
    if not normalized:
        return None
    major, minor, patch = normalized.split(".")
    return int(major), int(minor), int(patch)


def compare_versions(left: str | None, right: str | None) -> int | None:
    a = version_tuple(left)
    b = version_tuple(right)
    if not a or not b:
        return None
    return (a > b) - (a < b)


def extract_homepage_version_from_container(container: dict[str, Any]) -> str:
    labels = container.get("labels") or {}
    for key in (
        "org.opencontainers.image.version",
        "homepage.version",
    ):
        value = normalize_version(str(labels.get(key) or ""))
        if value:
            return value

    image = str(container.get("image") or "").strip()
    if not re.search(r"(?:^|/)(?:gethomepage/)?homepage(?::|@|$)", image, flags=re.IGNORECASE):
        return ""
    if ":" not in image or "@" in image.split(":", 1)[-1]:
        return ""
    tag = image.rsplit(":", 1)[-1]
    if tag.casefold() in {"latest", "main", "dev", "stable"}:
        return ""
    return normalize_version(tag)


def detect_homepage_version_from_hosts(hosts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Best-effort Homepage version discovery through configured read-only Docker hosts."""
    host_list = [host for host in list(hosts)[:8] if host.get("client") is not None]
    candidates: list[dict[str, str]] = []
    errors: list[str] = []

    def scan(host: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
        client = host.get("client")
        host_name = str(host.get("name") or host.get("homepage_server") or "Docker")
        try:
            containers = client.list_containers()
        except Exception as exc:
            return [], f"{host_name}: {exc}"
        found: list[dict[str, str]] = []
        for container in containers:
            image = str(container.get("image") or "")
            name = str(container.get("name") or "")
            if not re.search(r"(?:^|/)(?:gethomepage/)?homepage(?::|@|$)", image, flags=re.IGNORECASE):
                continue
            found.append({
                "version": extract_homepage_version_from_container(container),
                "host": host_name,
                "container": name or "Homepage",
                "image": image,
            })
        return found, ""

    if host_list:
        with ThreadPoolExecutor(max_workers=min(4, len(host_list))) as executor:
            futures = [executor.submit(scan, host) for host in host_list]
            for future in as_completed(futures):
                found, error = future.result()
                candidates.extend(found)
                if error:
                    errors.append(error)

    # Prefer a candidate with an actual semantic version. If the container only uses :latest,
    # still report that Homepage was found and explain why the version is unknown.
    candidates.sort(key=lambda item: (not bool(item.get("version")), item.get("host", ""), item.get("container", "")))
    selected = candidates[0] if candidates else None
    return {
        "found": bool(selected),
        "version": str(selected.get("version") if selected else ""),
        "source": "docker" if selected else "",
        "host": str(selected.get("host") if selected else ""),
        "container": str(selected.get("container") if selected else ""),
        "image": str(selected.get("image") if selected else ""),
        "errors": errors[:5],
        "candidates": candidates,
    }


def latest_homepage_release(timeout: float = 3.0, force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    with _RELEASE_CACHE_LOCK:
        cached = _RELEASE_CACHE.get("payload")
        fetched_at = float(_RELEASE_CACHE.get("fetched_at") or 0)
        if not force and cached and now - fetched_at < _RELEASE_CACHE_TTL:
            return dict(cached)

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(LATEST_RELEASE_API, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed GitHub API endpoint
            payload = json.loads(response.read().decode("utf-8"))
        version = normalize_version(str(payload.get("tag_name") or payload.get("name") or ""))
        result = {
            "ok": bool(version),
            "version": version,
            "tag": str(payload.get("tag_name") or ""),
            "published_at": str(payload.get("published_at") or ""),
            "url": str(payload.get("html_url") or "https://github.com/gethomepage/homepage/releases"),
            "error": "" if version else "GitHub 最新 Release 未返回可识别版本。",
        }
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        result = {
            "ok": False,
            "version": "",
            "tag": "",
            "published_at": "",
            "url": "https://github.com/gethomepage/homepage/releases",
            "error": str(exc),
        }

    with _RELEASE_CACHE_LOCK:
        _RELEASE_CACHE["fetched_at"] = now
        _RELEASE_CACHE["payload"] = dict(result)
    return result


def compatibility_summary(current_version: str | None, latest_version: str | None = None) -> dict[str, Any]:
    version = normalize_version(current_version)
    vt = version_tuple(version)
    latest = normalize_version(latest_version)
    warnings: list[dict[str, str]] = []
    capabilities = {
        "auth": False,
        "oidc": False,
        "mcp": False,
        "custom_css_public_with_auth": False,
    }
    if vt:
        capabilities["auth"] = vt >= (2, 0, 0)
        capabilities["oidc"] = vt >= (2, 0, 0)
        capabilities["mcp"] = vt >= (2, 0, 0)
        capabilities["custom_css_public_with_auth"] = vt >= (2, 0, 0)
        if vt == (2, 1, 1):
            warnings.append({
                "level": "danger",
                "title": "Homepage v2.1.1 已知 YAML 解析问题",
                "message": "官方已在 v2.1.2 修复该问题，建议至少升级到 v2.1.2。",
            })
        if vt < (2, 0, 0):
            warnings.append({
                "level": "warning",
                "title": "Homepage 1.x",
                "message": "内置密码/OIDC 认证和 MCP 为 Homepage 2.x 功能。",
            })
    if version and latest and compare_versions(version, latest) == -1:
        warnings.append({
            "level": "info",
            "title": f"官方已有新版 v{latest}",
            "message": f"当前检测到 v{version}。升级前建议先在 Homepage Admin 创建完整快照。",
        })
    return {
        "version": version,
        "known": bool(vt),
        "latest_version": latest,
        "capabilities": capabilities,
        "warnings": warnings,
        "supported_through": SUPPORTED_THROUGH,
        "supported_status": "known" if vt and vt <= version_tuple(SUPPORTED_THROUGH) else ("newer" if vt else "unknown"),
    }
