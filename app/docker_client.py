from __future__ import annotations

from dataclasses import dataclass
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

    def enabled(self) -> bool:
        return bool(self.base_url.strip())

    def ping(self) -> bool:
        if not self.enabled():
            return False
        base = self.base_url.rstrip("/")
        try:
            with httpx.Client(base_url=base, timeout=self.timeout) as client:
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
        base = self.base_url.rstrip("/")
        with httpx.Client(base_url=base, timeout=self.timeout) as client:
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
        ("lsky", "sh-lskypro", ""),
        ("mkdocs", "sh-mkdocs", ""),
    ]
    for needle, icon, widget in candidates:
        if needle in haystack:
            return icon, widget
    return "", ""


def public_host_from_url(homepage_url: str) -> str:
    parsed = urlparse(homepage_url)
    return parsed.hostname or "localhost"
