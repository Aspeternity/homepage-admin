from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


SECRET_LABEL_MARKERS = ("password", "passwd", "secret", "token", "authorization", ".key")
ALLOWED_LABEL_PREFIXES = ("homepage.", "com.docker.compose.")


def safe_labels(labels: dict[str, Any] | None) -> dict[str, str]:
    """Return only discovery-relevant labels and never expose common secret labels."""
    if not labels:
        return {}
    safe: dict[str, str] = {}
    for key, value in labels.items():
        key_text = str(key)
        lowered = key_text.lower()
        if not key_text.startswith(ALLOWED_LABEL_PREFIXES):
            continue
        if any(marker in lowered for marker in SECRET_LABEL_MARKERS):
            continue
        safe[key_text] = str(value)
    return safe


def dedupe_ports(ports: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Collapse duplicate IPv4/IPv6 bindings into one host->container mapping."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, str]] = set()
    for port in ports or []:
        private = port.get("private", port.get("PrivatePort"))
        public = port.get("public", port.get("PublicPort"))
        proto = str(port.get("type", port.get("Type", "tcp")))
        key = (public, private, proto)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "private": private,
                "public": public,
                "ip": port.get("ip", port.get("IP")),
                "type": proto,
            }
        )
    return result


def sanitize_docker_container(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw Docker /containers/json item to the admin discovery shape."""
    if "name" in item and "id" in item and "ports" in item:
        # Compatibility with the v0.2.0 purpose-built discovery proxy.
        return {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "image": str(item.get("image", "")),
            "state": str(item.get("state", "")),
            "status": str(item.get("status", "")),
            "ports": dedupe_ports(item.get("ports") or []),
            "labels": safe_labels(item.get("labels") or {}),
        }

    names = item.get("Names") or []
    name = str(names[0]).lstrip("/") if names else str(item.get("Id", ""))[:12]
    return {
        "id": str(item.get("Id", "")),
        "name": name,
        "image": str(item.get("Image", "")),
        "state": str(item.get("State", "")),
        "status": str(item.get("Status", "")),
        "ports": dedupe_ports(item.get("Ports") or []),
        "labels": safe_labels(item.get("Labels") or {}),
    }


@dataclass
class DockerDiscoveryClient:
    base_url: str
    timeout: float = 3.0
    headers: dict[str, str] | None = None
    verify: bool | str = True
    cert: str | tuple[str, str] | None = None

    def enabled(self) -> bool:
        return bool(self.base_url.strip())

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers=self.headers or {},
            verify=self.verify,
            cert=self.cert,
            follow_redirects=True,
        )

    def ping(self) -> bool:
        if not self.enabled():
            return False
        try:
            with self._client() as client:
                response = client.get("/_ping")
                if response.status_code < 400:
                    return response.text.strip().upper() in {"OK", ""}
                # Compatibility with the v0.2.0 custom discovery proxy.
                response = client.get("/healthz")
                return response.status_code < 400
        except (httpx.HTTPError, OSError):
            return False

    def list_containers(self) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        with self._client() as client:
            response = client.get("/containers/json", params={"all": "1"})
            if response.status_code == 404:
                # Smooth upgrade path from the v0.2.0 custom sidecar.
                response = client.get("/api/containers")
                response.raise_for_status()
                payload = response.json()
                raw = payload.get("containers", []) if isinstance(payload, dict) else []
            else:
                response.raise_for_status()
                raw = response.json()
        if not isinstance(raw, list):
            return []
        containers = [sanitize_docker_container(item) for item in raw if isinstance(item, dict)]
        containers.sort(key=lambda item: (item.get("state") != "running", str(item.get("name", "")).casefold()))
        return containers

    def get_container(self, container_id: str) -> dict[str, Any] | None:
        for container in self.list_containers():
            current = str(container.get("id", ""))
            if current.startswith(container_id) or current == container_id:
                return container
        return None


def homepage_labels_to_values(container: dict) -> dict:
    labels = container.get("labels") or {}
    values: dict[str, object] = {}
    mapping = {
        "homepage.name": "name",
        "homepage.icon": "icon",
        "homepage.href": "href",
        "homepage.description": "description",
        "homepage.siteMonitor": "siteMonitor",
        "homepage.ping": "ping",
        "homepage.server": "server",
        "homepage.container": "container",
    }
    for label, field in mapping.items():
        if label in labels:
            values[field] = labels[label]
    widget: dict[str, object] = {}
    prefix = "homepage.widget."
    for key, value in labels.items():
        if key.startswith(prefix):
            widget[key[len(prefix):]] = value
    if widget:
        values["widget"] = widget
    group = labels.get("homepage.group")
    if group:
        values["group"] = group
    return values


def first_published_port(container: dict) -> int | None:
    for port in dedupe_ports(container.get("ports") or []):
        public = port.get("public")
        proto = str(port.get("type", "tcp"))
        if public and proto == "tcp":
            return int(public)
    return None


SERVICE_PROFILES: list[dict[str, Any]] = [
    {"needles": ("jellyfin",), "icon": "sh-jellyfin", "widget": "jellyfin", "description": "影视媒体中心", "kind": "影音媒体", "confidence": "高", "group_hints": ("群晖NAS", "媒体", "Media")},
    {"needles": ("qbittorrent",), "icon": "sh-qbittorrent", "widget": "qbittorrent", "description": "qBittorrent 下载器", "kind": "下载工具", "confidence": "高", "group_hints": ("群晖NAS", "下载", "Downloads")},
    {"needles": ("transmission",), "icon": "sh-transmission", "widget": "transmission", "description": "Transmission 下载器", "kind": "下载工具", "confidence": "高", "group_hints": ("群晖NAS", "下载", "Downloads")},
    {"needles": ("home-assistant", "homeassistant"), "icon": "sh-home-assistant", "widget": "homeassistant", "description": "Home Assistant 智能家居", "kind": "智能家居", "confidence": "高", "group_hints": ("内网Tools", "智能家居", "Home")},
    {"needles": ("portainer",), "icon": "sh-portainer", "widget": "portainer", "description": "Docker 容器管理", "kind": "容器管理", "confidence": "高", "group_hints": ("内网Tools", "Tools", "管理")},
    {"needles": ("proxmox",), "icon": "sh-proxmox", "widget": "proxmox", "description": "Proxmox 虚拟化管理", "kind": "虚拟化管理", "confidence": "高", "group_hints": ("内网Tools", "Tools", "管理")},
    {"needles": ("vaultwarden",), "icon": "sh-vaultwarden", "widget": "", "description": "Vaultwarden 密码管理", "kind": "密码管理", "confidence": "高", "group_hints": ("群晖NAS", "内网Tools", "安全")},
    {"needles": ("nginx-proxy-manager",), "icon": "sh-nginxproxymanager", "widget": "", "description": "Nginx Proxy Manager 反向代理", "kind": "反向代理", "confidence": "高", "group_hints": ("内网Tools", "Tools", "网络")},
    {"needles": ("moviepilot",), "icon": "mdi-movie-open", "widget": "", "description": "MoviePilot 影视自动化", "kind": "影音自动化", "confidence": "高", "group_hints": ("群晖NAS", "媒体", "Media")},
    {"needles": ("metube",), "icon": "sh-metube", "widget": "", "description": "MeTube 视频下载", "kind": "下载工具", "confidence": "高", "group_hints": ("群晖NAS", "下载", "Downloads")},
    {"needles": ("lsky",), "icon": "mdi-image-multiple", "widget": "", "description": "Lsky Pro 图床管理", "kind": "图床服务", "confidence": "高", "group_hints": ("群晖NAS", "内网Tools", "图床")},
    {"needles": ("mkdocs",), "icon": "sh-mkdocs", "widget": "", "description": "MkDocs 文档站点", "kind": "文档站点", "confidence": "高", "group_hints": ("群晖NAS", "内网Tools", "文档")},
    {"needles": ("phpmyadmin",), "icon": "sh-phpmyadmin", "widget": "", "description": "phpMyAdmin 数据库管理", "kind": "数据库管理", "confidence": "高", "group_hints": ("内网Tools", "群晖NAS", "数据库")},
    {"needles": ("mysql",), "icon": "sh-mysql", "widget": "", "description": "MySQL 数据库", "kind": "数据库", "confidence": "高", "group_hints": ("内网Tools", "群晖NAS", "数据库")},
    {"needles": ("komari",), "icon": "mdi-server-network", "widget": "", "description": "Komari 服务器监控", "kind": "服务器监控", "confidence": "高", "group_hints": ("内网Tools", "监控", "Monitoring", "Tools")},
    {"needles": ("cookiecloud",), "icon": "", "widget": "", "description": "CookieCloud Cookie 同步", "kind": "同步工具", "confidence": "高", "group_hints": ("内网Tools", "Tools", "同步")},
    {"needles": ("rustdesk",), "icon": "sh-rustdesk", "widget": "", "description": "RustDesk 远程桌面", "kind": "远程桌面", "confidence": "高", "group_hints": ("内网Tools", "Tools", "远程")},
    {"needles": ("1panel",), "icon": "sh-1panel", "widget": "", "description": "1Panel 服务器运维面板", "kind": "服务器面板", "confidence": "高", "group_hints": ("内网Tools", "Tools", "管理")},
    {"needles": ("gethomepage/homepage", " homepage "), "icon": "sh-homepage", "widget": "", "description": "Homepage 导航面板", "kind": "导航面板", "confidence": "高", "group_hints": ("内网Tools", "Tools", "导航")},
]


def infer_service_profile(container: dict) -> dict[str, Any]:
    """Infer non-sensitive Homepage defaults from the container name/image."""
    haystack = f" {container.get('name','')} {container.get('image','')} ".lower()
    for profile in SERVICE_PROFILES:
        if any(needle in haystack for needle in profile["needles"]):
            return dict(profile)
    return {
        "needles": (),
        "icon": "",
        "widget": "",
        "description": "",
        "kind": "通用 Docker 服务",
        "confidence": "低",
        "group_hints": (),
    }


def infer_icon_and_widget(container: dict) -> tuple[str, str]:
    profile = infer_service_profile(container)
    return str(profile.get("icon", "")), str(profile.get("widget", ""))


def recommend_group_index(names: list[str], profile: dict[str, Any]) -> int | None:
    """Find the closest existing Homepage group for a recognized service profile."""
    if not names:
        return None
    normalized = [(index, name.strip().casefold()) for index, name in enumerate(names)]
    hints = [str(hint).strip().casefold() for hint in profile.get("group_hints", ()) if str(hint).strip()]
    for hint in hints:
        for index, name in normalized:
            if name == hint:
                return index
    for hint in hints:
        if len(hint) < 2:
            continue
        for index, name in normalized:
            if hint in name or name in hint:
                return index
    return None

def public_host_from_url(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    return parsed.hostname or "localhost"


def infer_service_description(container: dict) -> str:
    """Return a short, human-friendly description for common self-hosted images."""
    return str(infer_service_profile(container).get("description", ""))
