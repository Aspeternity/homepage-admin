from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


@dataclass
class DockerDiscoveryClient:
    base_url: str
    timeout: float = 3.0

    def enabled(self) -> bool:
        return bool(self.base_url.strip())

    def list_containers(self) -> list[dict]:
        if not self.enabled():
            return []
        with httpx.Client(base_url=self.base_url.rstrip("/"), timeout=self.timeout) as client:
            response = client.get("/api/containers")
            response.raise_for_status()
            payload = response.json()
        return list(payload.get("containers", []))

    def get_container(self, container_id: str) -> dict | None:
        for container in self.list_containers():
            if container.get("id", "").startswith(container_id) or container.get("id") == container_id:
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
    for port in container.get("ports") or []:
        public = port.get("public")
        proto = str(port.get("type", "tcp"))
        if public and proto == "tcp":
            return int(public)
    return None


def infer_icon_and_widget(container: dict) -> tuple[str, str]:
    haystack = f"{container.get('name','')} {container.get('image','')}".lower()
    candidates = [
        ("jellyfin", "sh-jellyfin", "jellyfin"),
        ("qbittorrent", "sh-qbittorrent", "qbittorrent"),
        ("transmission", "sh-transmission", "transmission"),
        ("home-assistant", "sh-home-assistant", "homeassistant"),
        ("homeassistant", "sh-home-assistant", "homeassistant"),
        ("portainer", "sh-portainer", "portainer"),
        ("proxmox", "sh-proxmox", "proxmox"),
        ("vaultwarden", "sh-vaultwarden", ""),
        ("nginx-proxy-manager", "sh-nginxproxymanager", ""),
        ("moviepilot", "sh-moviepilot", ""),
        ("metube", "sh-metube", ""),
    ]
    for needle, icon, widget in candidates:
        if needle in haystack:
            return icon, widget
    return "", ""


def public_host_from_url(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    return parsed.hostname or "localhost"
