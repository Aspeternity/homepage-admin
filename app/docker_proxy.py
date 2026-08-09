from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException

from .docker_client import dedupe_ports, safe_labels

app = FastAPI(title="Homepage Admin Docker Discovery Proxy", docs_url=None, redoc_url=None, openapi_url=None)
DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")


def _docker_get(path: str) -> Any:
    transport = httpx.HTTPTransport(uds=DOCKER_SOCKET)
    try:
        with httpx.Client(transport=transport, base_url="http://docker", timeout=3.0) as client:
            response = client.get(path)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Docker API unavailable: {exc}") from exc


def _safe_labels(labels: dict[str, str] | None) -> dict[str, str]:
    # Backwards-compatible export kept for v0.2.0 tests/users.
    return safe_labels(labels)


def _sanitize_container(item: dict[str, Any]) -> dict[str, Any]:
    names = item.get("Names") or []
    name = str(names[0]).lstrip("/") if names else str(item.get("Id", ""))[:12]
    ports = dedupe_ports(item.get("Ports") or [])
    return {
        "id": str(item.get("Id", "")),
        "name": name,
        "image": str(item.get("Image", "")),
        "state": str(item.get("State", "")),
        "status": str(item.get("Status", "")),
        "ports": ports,
        "labels": _safe_labels(item.get("Labels")),
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    transport = httpx.HTTPTransport(uds=DOCKER_SOCKET)
    try:
        with httpx.Client(transport=transport, base_url="http://docker", timeout=3.0) as client:
            response = client.get("/_ping")
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Docker API unavailable: {exc}") from exc
    return {"status": "ok"}


@app.get("/api/containers")
def containers() -> dict[str, list[dict[str, Any]]]:
    raw = _docker_get("/containers/json?all=1")
    if not isinstance(raw, list):
        raise HTTPException(status_code=502, detail="Unexpected Docker API response")
    containers = [_sanitize_container(item) for item in raw if isinstance(item, dict)]
    containers.sort(key=lambda item: (item.get("state") != "running", str(item.get("name", "")).lower()))
    return {"containers": containers}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9100)
