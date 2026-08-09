from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from ruamel.yaml import YAML

from app.main import app
from app.settings import settings


def login(client: TestClient) -> str:
    response = client.post(
        "/login",
        data={"username": "admin", "password": "test-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/services")
    return re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)


def test_login_and_main_pages() -> None:
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    assert client.get("/services", follow_redirects=False).status_code == 303
    login(client)
    for path in ["/services", "/bookmarks", "/settings", "/widgets", "/yaml/services.yaml", "/backups"]:
        assert client.get(path).status_code == 200


def test_service_secret_is_not_rendered_and_is_preserved() -> None:
    client = TestClient(app)
    csrf = login(client)
    edit = client.get("/services/item/0/0/edit")
    assert edit.status_code == 200
    assert "super-secret-key" not in edit.text

    response = client.post(
        "/services/item/0/0/update",
        data={
            "csrf": csrf,
            "name": "Jellyfin",
            "group_index": "0",
            "icon": "jellyfin.png",
            "href": "https://jellyfin.example",
            "description": "Media",
            "target": "",
            "siteMonitor": "",
            "ping": "",
            "server": "",
            "container": "",
            "widget_type": "jellyfin",
            "widget_url": "https://jellyfin.example",
            "widget_key": "",
            "widget_extra": "enableBlocks: true",
            "extra": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    data = YAML(typ="safe").load((settings.config_dir / "services.yaml").read_text(encoding="utf-8"))
    assert data[0]["Core"][0]["Jellyfin"]["widget"]["key"] == "super-secret-key"
    assert data[0]["Core"][0]["Jellyfin"]["widget"]["enableBlocks"] is True


def test_invalid_yaml_does_not_replace_file() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "services.yaml"
    before = path.read_text(encoding="utf-8")
    response = client.post(
        "/yaml/services.yaml",
        data={"csrf": csrf, "content": "- invalid: [yaml"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert path.read_text(encoding="utf-8") == before


def test_backup_is_created() -> None:
    client = TestClient(app)
    csrf = login(client)
    current = (settings.config_dir / "widgets.yaml").read_text(encoding="utf-8")
    response = client.post(
        "/yaml/widgets.yaml",
        data={"csrf": csrf, "content": current + "\n"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    backups = list((settings.data_dir / "backups").glob("*/widgets.yaml"))
    assert backups
