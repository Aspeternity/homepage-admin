from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ProxmoxDiscoveryError(RuntimeError):
    pass


def normalize_proxmox_url(value: str) -> str:
    """Return the base Proxmox URL Homepage expects (no trailing slash)."""
    return str(value or "").strip().rstrip("/")


@dataclass
class ProxmoxConnection:
    name: str
    url: str
    token: str
    secret: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"PVEAPIToken={self.token}={self.secret}"}


class ProxmoxDiscoveryClient:
    def __init__(self, timeout: float = 6.0) -> None:
        self.timeout = timeout

    async def discover(self, connection: ProxmoxConnection) -> list[dict[str, Any]]:
        base = normalize_proxmox_url(connection.url)
        if not base:
            raise ProxmoxDiscoveryError("Proxmox URL 为空。")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
                response = await client.get(
                    f"{base}/api2/json/cluster/resources",
                    params={"type": "vm"},
                    headers=connection.headers,
                )
            if response.status_code in {401, 403}:
                raise ProxmoxDiscoveryError("Proxmox Token 无效或权限不足。")
            response.raise_for_status()
            payload = response.json()
        except ProxmoxDiscoveryError:
            raise
        except httpx.TimeoutException as exc:
            raise ProxmoxDiscoveryError("连接 Proxmox 超时。") from exc
        except httpx.ConnectError as exc:
            raise ProxmoxDiscoveryError("无法连接 Proxmox，请检查 URL、网络或证书入口。") from exc
        except httpx.HTTPStatusError as exc:
            raise ProxmoxDiscoveryError(f"Proxmox 返回 HTTP {exc.response.status_code}。") from exc
        except (ValueError, TypeError) as exc:
            raise ProxmoxDiscoveryError(f"Proxmox 返回数据无法解析：{exc}") from exc

        raw = payload.get("data", []) if isinstance(payload, dict) else []
        resources: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict) or item.get("type") not in {"qemu", "lxc"}:
                continue
            mem = int(item.get("mem") or 0)
            maxmem = int(item.get("maxmem") or 0)
            cpu = float(item.get("cpu") or 0.0)
            resources.append(
                {
                    "vmid": int(item.get("vmid") or 0),
                    "name": str(item.get("name") or f"VM {item.get('vmid', '')}"),
                    "type": str(item.get("type")),
                    "node": str(item.get("node") or connection.name),
                    "status": str(item.get("status") or "unknown"),
                    "cpu_percent": round(cpu * 100, 1),
                    "memory_percent": round(mem / maxmem * 100, 1) if maxmem else 0.0,
                    "mem": mem,
                    "maxmem": maxmem,
                    "uptime": int(item.get("uptime") or 0),
                }
            )
        resources.sort(key=lambda item: (item["type"] != "qemu", item["vmid"]))
        return resources
