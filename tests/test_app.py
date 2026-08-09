from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from ruamel.yaml import YAML

from app.main import app
from app.secrets import SECRET_PREFIX, mask_secrets
from app.settings import settings
from app.store import store


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
    for path in ["/services", "/bookmarks", "/settings", "/widgets", "/widget-center", "/widget-schema", "/docker", "/proxmox", "/yaml/services.yaml", "/backups"]:
        assert client.get(path).status_code == 200


def test_service_secret_is_not_rendered_and_is_preserved() -> None:
    client = TestClient(app)
    csrf = login(client)
    edit = client.get("/services/item/0/0/edit")
    assert edit.status_code == 200
    assert "super-secret-key" not in edit.text
    assert '"secret_saved": {"key": true}' in edit.text

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
            "widget_field_url": "https://jellyfin.example",
            "widget_field_key": "",
            "widget_field_enableBlocks": "true",
            "widget_extra": "",
            "extra": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    data = YAML(typ="safe").load((settings.config_dir / "services.yaml").read_text(encoding="utf-8"))
    assert data[0]["Core"][0]["Jellyfin"]["widget"]["key"] == "super-secret-key"
    assert data[0]["Core"][0]["Jellyfin"]["widget"]["enableBlocks"] is True


def test_advanced_editor_masks_and_restores_secret() -> None:
    client = TestClient(app)
    csrf = login(client)
    page = client.get("/yaml/services.yaml")
    assert page.status_code == 200
    assert "super-secret-key" not in page.text
    assert SECRET_PREFIX in page.text

    masked = mask_secrets(store.load("services.yaml"))
    masked[0]["Core"][0]["Jellyfin"]["description"] = "Changed through masked editor"
    content = store.dump(masked)
    response = client.post(
        "/yaml/services.yaml",
        data={"csrf": csrf, "masked": "1", "content": content},
        follow_redirects=False,
    )
    assert response.status_code == 303
    data = YAML(typ="safe").load((settings.config_dir / "services.yaml").read_text(encoding="utf-8"))
    assert data[0]["Core"][0]["Jellyfin"]["widget"]["key"] == "super-secret-key"
    assert data[0]["Core"][0]["Jellyfin"]["description"] == "Changed through masked editor"


def test_invalid_yaml_does_not_replace_file() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "services.yaml"
    before = path.read_text(encoding="utf-8")
    response = client.post(
        "/yaml/services.yaml",
        data={"csrf": csrf, "masked": "0", "content": "- invalid: [yaml"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert path.read_text(encoding="utf-8") == before


def test_group_drag_reorder_api() -> None:
    client = TestClient(app)
    csrf = login(client)
    original = (settings.config_dir / "bookmarks.yaml").read_text(encoding="utf-8")
    try:
        (settings.config_dir / "bookmarks.yaml").write_text(
            "---\n- One: []\n- Two: []\n- Three: []\n",
            encoding="utf-8",
        )
        response = client.post(
            "/api/bookmarks/group/reorder",
            headers={"x-csrf-token": csrf},
            json={"source_index": 0, "target_index": 3},
        )
        assert response.status_code == 200
        data = YAML(typ="safe").load((settings.config_dir / "bookmarks.yaml").read_text(encoding="utf-8"))
        assert list(data[0].keys()) == ["Two"]
        assert list(data[2].keys()) == ["One"]
    finally:
        (settings.config_dir / "bookmarks.yaml").write_text(original, encoding="utf-8")


def test_docker_import_wizard_and_detailed_editor(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    sample = {
        "id": "abc123def456",
        "name": "qbittorrent",
        "image": "lscr.io/linuxserver/qbittorrent:latest",
        "state": "running",
        "status": "Up 1 hour",
        "ports": [{"private": 8080, "public": 18080, "type": "tcp", "ip": "0.0.0.0"}],
        "labels": {},
    }
    monkeypatch.setattr(main_module.docker_discovery, "base_url", "http://docker-proxy:9100")
    monkeypatch.setattr(main_module.docker_discovery, "get_container", lambda _id: sample)

    wizard = client.get("/docker/import/abc123def456?group=0")
    assert wizard.status_code == 200
    assert "Docker 导入向导" in wizard.text
    assert 'value="qbittorrent"' in wizard.text
    assert 'value="sh-qbittorrent"' in wizard.text
    assert "qBittorrent 下载器" in wizard.text
    assert "18080" in wizard.text
    assert 'data-wizard-yaml' in wizard.text

    editor = client.get(
        "/docker/import/abc123def456/edit",
        params={
            "group_index": 0,
            "name": "qBittorrent Main",
            "description": "下载服务",
            "widget_type": "qbittorrent",
            "widget_url": "http://homepage.local:18080",
        },
    )
    assert editor.status_code == 200
    assert 'value="qBittorrent Main"' in editor.text
    assert 'value="qbittorrent" list="widget-type-options"' in editor.text
    assert 'http://homepage.local:18080' in editor.text


def test_backup_is_created() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "widgets.yaml"
    current = path.read_text(encoding="utf-8")
    parsed = YAML(typ="safe").load(current) or []
    parsed.append({"datetime": {"format": {"timeStyle": "short"}}})
    from io import StringIO
    stream = StringIO()
    YAML().dump(parsed, stream)
    response = client.post(
        "/yaml/widgets.yaml",
        data={"csrf": csrf, "masked": "1", "content": stream.getvalue()},
        follow_redirects=False,
    )
    assert response.status_code == 303
    backups = list((settings.data_dir / "backups").glob("*/widgets.yaml"))
    assert backups


def test_backup_can_be_deleted_from_ui() -> None:
    client = TestClient(app)
    csrf = login(client)
    current = (settings.config_dir / "widgets.yaml").read_text(encoding="utf-8")
    response = client.post(
        "/yaml/widgets.yaml",
        data={"csrf": csrf, "masked": "1", "content": current + "\n"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    backups = store.list_backups()
    assert backups
    backup_id = backups[0]["id"]

    page = client.get("/backups")
    assert f'/backups/{backup_id}/delete' in page.text
    assert "/backups/delete-all" in page.text

    deleted = client.post(
        f"/backups/{backup_id}/delete",
        data={"csrf": csrf},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    assert not (settings.data_dir / "backups" / backup_id).exists()


def test_item_drag_same_group_to_end() -> None:
    client = TestClient(app)
    csrf = login(client)
    original = (settings.config_dir / "bookmarks.yaml").read_text(encoding="utf-8")
    try:
        (settings.config_dir / "bookmarks.yaml").write_text(
            "---\n- Links:\n    - A:\n        - href: https://a.example\n    - B:\n        - href: https://b.example\n    - C:\n        - href: https://c.example\n",
            encoding="utf-8",
        )
        response = client.post(
            "/api/bookmarks/move",
            headers={"x-csrf-token": csrf},
            json={"source_group": 0, "source_index": 0, "target_group": 0, "target_index": 2},
        )
        assert response.status_code == 200
        data = YAML(typ="safe").load((settings.config_dir / "bookmarks.yaml").read_text(encoding="utf-8"))
        names = [next(iter(item.keys())) for item in data[0]["Links"]]
        assert names == ["B", "C", "A"]
    finally:
        (settings.config_dir / "bookmarks.yaml").write_text(original, encoding="utf-8")


def test_docker_proxy_filters_sensitive_homepage_labels() -> None:
    from app.docker_proxy import _safe_labels

    labels = _safe_labels(
        {
            "homepage.name": "Jellyfin",
            "homepage.widget.type": "jellyfin",
            "homepage.widget.key": "do-not-leak",
            "homepage.widget.headers.Authorization": "Bearer do-not-leak",
            "com.docker.compose.project": "media",
            "unrelated.secret": "ignored",
        }
    )
    assert labels["homepage.name"] == "Jellyfin"
    assert labels["homepage.widget.type"] == "jellyfin"
    assert labels["com.docker.compose.project"] == "media"
    assert "homepage.widget.key" not in labels
    assert "homepage.widget.headers.Authorization" not in labels


def test_create_local_docker_server_when_docker_yaml_empty() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "docker.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text("---\n", encoding="utf-8")
        response = client.post(
            "/docker/setup-homepage",
            data={"csrf": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert data["local-docker"]["host"] == "homepage-docker-proxy"
        assert data["local-docker"]["port"] == 2375
    finally:
        path.write_text(original, encoding="utf-8")


def test_masked_secret_survives_reorder_but_cannot_move_to_public_field() -> None:
    from app.secrets import restore_masked_secrets

    original = [
        {"Core": [
            {"Jellyfin": {"description": "Media", "widget": {"type": "jellyfin", "key": "secret-a"}}},
            {"Other": {"description": "Other"}},
        ]}
    ]
    masked = mask_secrets(original)
    masked[0]["Core"].reverse()
    restored = restore_masked_secrets(masked, original)
    assert restored[0]["Core"][1]["Jellyfin"]["widget"]["key"] == "secret-a"

    masked = mask_secrets(original)
    token = masked[0]["Core"][0]["Jellyfin"]["widget"]["key"]
    masked[0]["Core"][0]["Jellyfin"]["description"] = token
    import pytest
    with pytest.raises(ValueError):
        restore_masked_secrets(masked, original)


def test_settings_provider_secret_is_masked_and_preserved() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "settings.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(
            "---\ntitle: Test\nproviders:\n  openweathermap: provider-secret\n",
            encoding="utf-8",
        )
        page = client.get("/settings")
        assert page.status_code == 200
        assert "provider-secret" not in page.text
        assert SECRET_PREFIX in page.text

        masked_extra = mask_secrets({"providers": {"openweathermap": "provider-secret"}})
        response = client.post(
            "/settings",
            data={"csrf": csrf, "title": "Test 2", "extra": store.dump_fragment(masked_extra)},
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert data["providers"]["openweathermap"] == "provider-secret"
    finally:
        path.write_text(original, encoding="utf-8")


def test_top_widget_secret_is_masked_and_preserved() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "widgets.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(
            "---\n- customapi:\n    url: https://example.invalid\n    token: widget-secret\n",
            encoding="utf-8",
        )
        page = client.get("/widgets/0/edit")
        assert page.status_code == 200
        assert "widget-secret" not in page.text
        assert SECRET_PREFIX in page.text

        masked_cfg = mask_secrets({"url": "https://example.invalid", "token": "widget-secret"})
        response = client.post(
            "/widgets/0/update",
            data={"csrf": csrf, "name": "customapi", "config": store.dump_fragment(masked_cfg)},
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert data[0]["customapi"]["token"] == "widget-secret"
    finally:
        path.write_text(original, encoding="utf-8")


def test_unknown_service_widget_extra_secret_is_masked_and_preserved() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "services.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(
            "---\n- Core:\n    - Custom:\n        href: https://example.invalid\n        widget:\n          type: customapi\n          url: https://example.invalid\n          token: custom-widget-secret\n",
            encoding="utf-8",
        )
        page = client.get("/services/item/0/0/edit")
        assert page.status_code == 200
        assert "custom-widget-secret" not in page.text
        assert SECRET_PREFIX in page.text

        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        masked_widget = mask_secrets({"token": data[0]["Core"][0]["Custom"]["widget"]["token"]})
        response = client.post(
            "/services/item/0/0/update",
            data={
                "csrf": csrf,
                "name": "Custom",
                "group_index": "0",
                "href": "https://example.invalid",
                "widget_type": "customapi",
                "widget_field_url": "https://example.invalid",
                "widget_extra": store.dump_fragment(masked_widget),
                "extra": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        saved = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert saved[0]["Core"][0]["Custom"]["widget"]["token"] == "custom-widget-secret"
    finally:
        path.write_text(original, encoding="utf-8")


def test_theme_menu_assets_are_present() -> None:
    client = TestClient(app)
    login(client)
    page = client.get("/services")
    assert 'data-theme-menu-toggle' in page.text
    assert 'data-theme-choice="light"' in page.text
    assert 'data-theme-choice="dark"' in page.text
    assert 'data-theme-choice="system"' in page.text
    assert "切换浅色" not in page.text
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    assert 'html[data-theme="light"]' in (root / "app/static/app.css").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "homepage-admin-theme" in js
    assert "prefers-color-scheme" in js


def test_dedupe_ipv4_ipv6_port_bindings() -> None:
    from app.docker_client import dedupe_ports

    ports = dedupe_ports([
        {"PrivatePort": 8089, "PublicPort": 8089, "IP": "0.0.0.0", "Type": "tcp"},
        {"PrivatePort": 8089, "PublicPort": 8089, "IP": "::", "Type": "tcp"},
        {"PrivatePort": 9000, "PublicPort": 19000, "IP": "0.0.0.0", "Type": "tcp"},
    ])
    assert len(ports) == 2
    assert ports[0]["public"] == 8089


def test_migrate_socket_server_to_read_only_proxy() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "docker.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text("---\nlocal-docker:\n  socket: /var/run/docker.sock\n", encoding="utf-8")
        response = client.post(
            "/docker/migrate-homepage-proxy",
            data={"csrf": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert "socket" not in data["local-docker"]
        assert data["local-docker"]["host"] == "homepage-docker-proxy"
        assert data["local-docker"]["port"] == 2375
    finally:
        path.write_text(original, encoding="utf-8")


def test_docker_page_hides_internal_proxy_and_marks_existing_case_insensitive(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    services_path = settings.config_dir / "services.yaml"
    original = services_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            "---\n- Core:\n    - Lsky:\n        server: local-docker\n        container: LSKY-PRO\n",
            encoding="utf-8",
        )
        sample = [
            {"id": "1", "name": "lsky-pro", "image": "lsky", "state": "running", "status": "Up", "ports": [], "labels": {}},
            {"id": "2", "name": "homepage-admin-docker-proxy", "image": "proxy", "state": "running", "status": "Up", "ports": [], "labels": {}},
        ]
        monkeypatch.setattr(main_module.docker_discovery, "base_url", "http://proxy")
        monkeypatch.setattr(main_module.docker_discovery, "ping", lambda: True)
        monkeypatch.setattr(main_module.docker_discovery, "list_containers", lambda: sample)
        page = client.get("/docker")
        assert page.status_code == 200
        assert "lsky-pro" in page.text
        assert "已在 services.yaml" in page.text
        assert "homepage-admin-docker-proxy" not in page.text
        shown = client.get("/docker?show_internal=true")
        assert "homepage-admin-docker-proxy" in shown.text
    finally:
        services_path.write_text(original, encoding="utf-8")


def test_backup_limit_can_be_configured_and_reset() -> None:
    client = TestClient(app)
    csrf = login(client)
    prefs = settings.data_dir / "admin-settings.json"
    original = prefs.read_text(encoding="utf-8") if prefs.exists() else None
    try:
        response = client.post(
            "/backups/settings",
            data={"csrf": csrf, "backup_limit": "12"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert store.backup_limit() == 12
        page = client.get("/backups")
        assert 'name="backup_limit" value="12"' in page.text
        assert "自定义" in page.text

        invalid = client.post(
            "/backups/settings",
            data={"csrf": csrf, "backup_limit": "0"},
            follow_redirects=False,
        )
        assert invalid.status_code == 303
        assert store.backup_limit() == 12

        reset = client.post(
            "/backups/settings/reset",
            data={"csrf": csrf},
            follow_redirects=False,
        )
        assert reset.status_code == 303
        assert store.backup_limit() == max(1, min(settings.backup_limit, 500))
    finally:
        if original is None:
            prefs.unlink(missing_ok=True)
        else:
            prefs.write_text(original, encoding="utf-8")


def test_service_profile_recommends_existing_group() -> None:
    from app.docker_client import infer_service_profile, recommend_group_index

    komari = {
        "name": "Komari",
        "image": "ghcr.io/komari-monitor/komari:latest",
    }
    profile = infer_service_profile(komari)
    assert profile["kind"] == "服务器监控"
    assert profile["description"] == "Komari 服务器监控"
    assert profile["confidence"] == "高"
    assert recommend_group_index(["Widgets", "群晖NAS", "内网Tools"], profile) == 2


def test_v024_wizard_alignment_and_auto_group_assets_are_present() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    docker_template = (root / "app/templates/docker.html").read_text(encoding="utf-8")
    wizard_template = (root / "app/templates/docker_import_wizard.html").read_text(encoding="utf-8")
    assert ".wizard-fields-grid > .wizard-field" in css
    assert "grid-template-rows: auto 42px 14px" in css
    assert "homepage-admin-docker-import-group-v2" in js
    assert "智能推荐（按服务类型）" in docker_template
    assert "识别为：{{ service_profile.kind }}" in wizard_template
    assert "data-preview-icon-image" in wizard_template


def test_v024_lsky_and_unlisted_selfhst_icons_use_verified_mdi_fallbacks() -> None:
    from app.docker_client import infer_service_profile

    lsky = infer_service_profile({"name": "Lsky-pro", "image": "halcyonazure/lsky-pro-docker:latest"})
    komari = infer_service_profile({"name": "Komari", "image": "ghcr.io/komari-monitor/komari:latest"})
    moviepilot = infer_service_profile({"name": "MoviePilot", "image": "jxxghp/moviepilot:latest"})
    assert lsky["icon"] == "mdi-image-multiple"
    assert komari["icon"] == "mdi-server-network"
    assert moviepilot["icon"] == "mdi-movie-open"
    assert not lsky["icon"].startswith("sh-lsky")
    assert not komari["icon"].startswith("sh-komari")
    assert not moviepilot["icon"].startswith("sh-moviepilot")


def test_v024_settings_noop_preserves_explicit_empty_background_blur() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "settings.yaml"
    original = path.read_text(encoding="utf-8")
    backup_root = settings.data_dir / "backups"
    try:
        text = '''---
# keep this comment
language: zh-CN
title: ASP Homepage
logpath: /
hideVersion: true
favicon: https://example.invalid/favicon.png
layout:
  Widgets:
    useEqualHeights: true
    style: row
    columns: 4
quicklaunch:
  provider: google # keep provider comment
headerStyle: underlined
background:
  image: https://example.invalid/background.jpg
  blur: "" # an explicit empty value is meaningful to Homepage
  saturate: 70
  brightness: 95
  opacity: 80
providers:
  weatherapi: provider-secret
'''
        path.write_text(text, encoding="utf-8")
        before_backups = {p.name for p in backup_root.iterdir() if p.is_dir()} if backup_root.exists() else set()
        masked_extra = mask_secrets({"logpath": "/", "providers": {"weatherapi": "provider-secret"}})
        response = client.post(
            "/settings",
            data={
                "csrf": csrf,
                "language": "zh-CN",
                "title": "ASP Homepage",
                "favicon": "https://example.invalid/favicon.png",
                "headerStyle": "underlined",
                "hideVersion": "on",
                "background_image": "https://example.invalid/background.jpg",
                "background_blur": "",
                "background_saturate": "70",
                "background_brightness": "95",
                "background_opacity": "80",
                "quicklaunch_provider": "google",
                "layout_name": "Widgets",
                "layout_0_style": "row",
                "layout_0_columns": "4",
                "layout_0_header": "on",
                "layout_0_useEqualHeights": "on",
                "layout_0_extra": "",
                "extra": store.dump_fragment(masked_extra),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "settings.yaml" in response.headers["location"] or response.headers["location"].startswith("/settings")
        assert path.read_text(encoding="utf-8") == text
        parsed = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert "blur" in parsed["background"]
        assert parsed["background"]["blur"] == ""
        after_backups = {p.name for p in backup_root.iterdir() if p.is_dir()} if backup_root.exists() else set()
        assert after_backups == before_backups
    finally:
        path.write_text(original, encoding="utf-8")


def test_v024_settings_background_zero_values_render_and_survive() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "settings.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(
            '''---
title: Zero Test
background:
  image: /images/bg.jpg
  saturate: 0
  brightness: 0
  opacity: 0
''',
            encoding="utf-8",
        )
        page = client.get("/settings")
        assert page.status_code == 200
        assert 'name="background_saturate" value="0"' in page.text
        assert 'name="background_brightness" value="0"' in page.text
        assert 'name="background_opacity" value="0"' in page.text
        response = client.post(
            "/settings",
            data={
                "csrf": csrf,
                "title": "Zero Test",
                "background_image": "/images/bg.jpg",
                "background_saturate": "0",
                "background_brightness": "0",
                "background_opacity": "0",
                "extra": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        parsed = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        assert parsed["background"]["saturate"] == 0
        assert parsed["background"]["brightness"] == 0
        assert parsed["background"]["opacity"] == 0
    finally:
        path.write_text(original, encoding="utf-8")


def test_v030_multi_widget_save_writes_widgets_list_and_preserves_secret() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "services.yaml"
    original = path.read_text(encoding="utf-8")
    try:
        response = client.post(
            "/services/item/0/0/update",
            data={
                "csrf": csrf,
                "source_group_index": "0",
                "source_item_index": "0",
                "name": "Jellyfin",
                "group_index": "0",
                "icon": "jellyfin.png",
                "href": "https://jellyfin.example",
                "widget_slots": "0,1",
                "widgets_0_original_index": "0",
                "widgets_0_type": "jellyfin",
                "widgets_0_field_url": "https://jellyfin.example",
                "widgets_0_field_key": "",
                "widgets_0_fields": ["movies", "series"],
                "widgets_0_extra": "",
                "widgets_1_original_index": "-1",
                "widgets_1_type": "portainer",
                "widgets_1_field_url": "http://portainer:9000",
                "widgets_1_field_env": "1",
                "widgets_1_field_key": "new-portainer-secret",
                "widgets_1_fields": ["running", "total"],
                "widgets_1_extra": "",
                "extra": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        details = data[0]["Core"][0]["Jellyfin"]
        assert "widget" not in details
        assert len(details["widgets"]) == 2
        assert details["widgets"][0]["type"] == "jellyfin"
        assert details["widgets"][0]["key"] == "super-secret-key"
        assert details["widgets"][0]["fields"] == ["movies", "series"]
        assert details["widgets"][1]["type"] == "portainer"
        assert details["widgets"][1]["key"] == "new-portainer-secret"
        assert details["widgets"][1]["env"] == 1
    finally:
        path.write_text(original, encoding="utf-8")


def test_v030_service_preview_masks_new_secret_and_returns_diff() -> None:
    client = TestClient(app)
    csrf = login(client)
    response = client.post(
        "/api/services/preview",
        data={
            "csrf": csrf,
            "source_group_index": "0",
            "source_item_index": "0",
            "name": "Jellyfin",
            "group_index": "0",
            "href": "https://jellyfin.example/new",
            "widget_slots": "0",
            "widgets_0_original_index": "0",
            "widgets_0_type": "jellyfin",
            "widgets_0_field_url": "https://jellyfin.example/new",
            "widgets_0_field_key": "brand-new-secret-value",
            "widgets_0_extra": "",
            "extra": "",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["changed"] is True
    assert "services.yaml" in payload["diff"]
    assert "brand-new-secret-value" not in payload["diff"]
    assert SECRET_PREFIX in payload["diff"]


def test_v030_widget_center_has_metadata_driven_catalog() -> None:
    client = TestClient(app)
    login(client)
    page = client.get("/widget-center")
    assert page.status_code == 200
    assert "Widget 中心" in page.text
    assert "Proxmox VE" in page.text
    assert "Home Assistant" in page.text
    assert "Synology DiskStation" in page.text
    assert "Custom API" in page.text
    assert "data-widget-search" in page.text
    assert "data-widget-category" in page.text
    assert "/services/item/new?widget=proxmox" in page.text


def test_v030_widget_test_reuses_saved_secret_without_echoing_it(monkeypatch) -> None:
    from app import main as main_module

    captured = {}

    async def fake_test(widget_type, config):
        captured["type"] = widget_type
        captured["config"] = dict(config)
        return {"message": "连接正常", "level": "deep", "metrics": [{"label": "Test", "value": "OK"}]}

    monkeypatch.setattr(main_module, "test_widget", fake_test)
    client = TestClient(app)
    csrf = login(client)
    response = client.post(
        "/api/widgets/test",
        headers={"x-csrf-token": csrf},
        json={
            "type": "jellyfin",
            "config": {"url": "https://jellyfin.example"},
            "group_index": 0,
            "item_index": "0",
            "original_index": 0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert captured["type"] == "jellyfin"
    assert captured["config"]["key"] == "super-secret-key"
    assert "super-secret-key" not in response.text


def test_v030_proxmox_can_import_existing_widget_connection_and_discover(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    services_path = settings.config_dir / "services.yaml"
    proxmox_path = settings.config_dir / "proxmox.yaml"
    services_original = services_path.read_text(encoding="utf-8")
    proxmox_original = proxmox_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            '''---
- Widgets:
    - Proxmox VE:
        href: https://10.10.1.2:8006
        widget:
          type: proxmox
          url: https://10.10.1.2:8006
          username: homepage@pve!homepage
          password: proxmox-token-secret
          node: asp-pve
''',
            encoding="utf-8",
        )
        proxmox_path.write_text("---\n", encoding="utf-8")
        page = client.get("/proxmox")
        assert page.status_code == 200
        assert "从此 Widget 导入" in page.text
        assert "proxmox-token-secret" not in page.text

        imported = client.post(
            "/proxmox/import-connection",
            data={"csrf": csrf, "group_index": "0", "item_index": "0"},
            follow_redirects=False,
        )
        assert imported.status_code == 303
        proxmox = YAML(typ="safe").load(proxmox_path.read_text(encoding="utf-8"))
        assert proxmox["asp-pve"]["url"] == "https://10.10.1.2:8006"
        assert proxmox["asp-pve"]["token"] == "homepage@pve!homepage"
        assert proxmox["asp-pve"]["secret"] == "proxmox-token-secret"

        async def fake_discover(connection):
            assert connection.name == "asp-pve"
            assert connection.secret == "proxmox-token-secret"
            return [{
                "vmid": 100,
                "name": "HomeAssistant",
                "type": "qemu",
                "node": "asp-pve",
                "status": "running",
                "cpu_percent": 4,
                "memory_percent": 32,
            }]

        monkeypatch.setattr(main_module.proxmox_discovery, "discover", fake_discover)
        discovered = client.get("/proxmox?server=asp-pve")
        assert discovered.status_code == 200
        assert "HomeAssistant" in discovered.text
        assert "QEMU 100" in discovered.text
        assert "以此 VM/LXC 新建服务" in discovered.text
        assert "proxmox-token-secret" not in discovered.text
    finally:
        services_path.write_text(services_original, encoding="utf-8")
        proxmox_path.write_text(proxmox_original, encoding="utf-8")


def test_v030_proxmox_bind_sets_service_mapping() -> None:
    client = TestClient(app)
    csrf = login(client)
    services_path = settings.config_dir / "services.yaml"
    proxmox_path = settings.config_dir / "proxmox.yaml"
    services_original = services_path.read_text(encoding="utf-8")
    proxmox_original = proxmox_path.read_text(encoding="utf-8")
    try:
        proxmox_path.write_text(
            '''---
asp-pve:
  url: https://10.10.1.2:8006
  token: homepage@pve!homepage
  secret: proxmox-token-secret
''',
            encoding="utf-8",
        )
        response = client.post(
            "/proxmox/bind",
            data={
                "csrf": csrf,
                "server": "asp-pve",
                "group_index": "0",
                "item_index": "0",
                "vmid": "104",
                "type": "qemu",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(services_path.read_text(encoding="utf-8"))
        details = data[0]["Core"][0]["Jellyfin"]
        assert details["proxmoxNode"] == "asp-pve"
        assert details["proxmoxVMID"] == 104
        assert "proxmoxType" not in details
    finally:
        services_path.write_text(services_original, encoding="utf-8")
        proxmox_path.write_text(proxmox_original, encoding="utf-8")


def test_v030_advanced_yaml_noop_does_not_create_backup() -> None:
    client = TestClient(app)
    csrf = login(client)
    path = settings.config_dir / "widgets.yaml"
    current = path.read_text(encoding="utf-8")
    backup_root = settings.data_dir / "backups"
    before = {p.name for p in backup_root.iterdir() if p.is_dir()} if backup_root.exists() else set()
    response = client.post(
        "/yaml/widgets.yaml",
        data={"csrf": csrf, "masked": "1", "content": current},
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = {p.name for p in backup_root.iterdir() if p.is_dir()} if backup_root.exists() else set()
    assert after == before


def test_v032_widget_center_offline_fallback_and_hidden_empty_state() -> None:
    from app.widget_catalog import ENHANCED_WIDGET_CATALOG, OFFICIAL_WIDGET_INDEX, WIDGET_CATALOG

    assert len(OFFICIAL_WIDGET_INDEX) >= 150
    assert len(WIDGET_CATALOG) >= len(OFFICIAL_WIDGET_INDEX)
    assert len(ENHANCED_WIDGET_CATALOG) == 15
    for type_id in [
        "adguard", "sonarr", "radarr", "seerr", "npm", "truenas", "unifi_drive", "watchtower", "zabbix",
    ]:
        assert type_id in WIDGET_CATALOG
    assert "nginxproxymanager" not in WIDGET_CATALOG
    assert WIDGET_CATALOG["npm"]["enhanced"] is True

    client = TestClient(app)
    login(client)
    page = client.get("/widget-center")
    assert page.status_code == 200
    assert "从 Homepage 官方 Service Widget 文档自动生成配置表单" in page.text
    assert "AdGuard Home" in page.text
    assert "Sonarr" in page.text
    assert "TrueNAS" in page.text
    assert "/services/item/new?widget=sonarr" in page.text
    assert "data-widget-center-empty hidden" in page.text

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert "[hidden] { display: none !important; }" in css
    assert ".back-to-top" in css


def test_v032_schema_parser_builds_dynamic_enhanced_form() -> None:
    from app.widget_schema_sync import parse_widget_document

    markdown = """---
title: Sonarr
description: Sonarr Widget Configuration
---
Allowed fields: `[\"wanted\", \"queued\", \"series\"]`.
```yaml
widget:
  type: sonarr
  url: http://sonarr.host.or.ip
  key: apikeyapikeyapikeyapikeyapikey
  enableQueue: true # optional, defaults to false
```
"""
    parsed = parse_widget_document(markdown, "sonarr")
    assert parsed is not None
    type_id, schema = parsed
    assert type_id == "sonarr"
    assert schema["auto_generated"] is True
    assert schema["enhanced"] is True
    assert schema["allowed_fields"] == ["wanted", "queued", "series"]
    fields = {field["name"]: field for field in schema["fields"]}
    assert fields["url"]["kind"] == "text"
    assert fields["key"]["kind"] == "secret"
    assert fields["enableQueue"]["kind"] == "bool"
    assert fields["enableQueue"]["required"] is False


def test_v032_schema_sync_can_add_new_official_widget_without_release(monkeypatch) -> None:
    from app import widget_catalog as catalog_module

    original = {key: dict(value) for key, value in catalog_module.WIDGET_CATALOG.items()}
    try:
        fake = {}
        # Safety guard requires a realistic catalog size.
        for index in range(60):
            type_id = f"futurewidget{index}"
            fake[type_id] = {
                "label": f"Future Widget {index}",
                "category": "应用",
                "description": "官方自动同步测试",
                "docs": "https://gethomepage.dev/widgets/services/",
                "icon": "mdi-puzzle-outline",
                "test": "basic",
                "allowed_fields": ["status"],
                "fields": [
                    {"name": "url", "label": "服务地址", "kind": "text", "required": True},
                    {"name": "apiToken", "label": "Api Token", "kind": "secret", "required": True},
                ],
                "enhanced": True,
                "auto_generated": True,
                "source_mode": "official-auto",
            }
        monkeypatch.setattr(catalog_module, "fetch_official_widget_schemas", lambda **_: (fake, {
            "source": "gethomepage/homepage", "ref": "dev", "synced_at": "2026-08-10T00:00:00Z",
            "document_count": 60, "widget_count": 60, "registry_count": 60, "error_count": 0, "errors": [],
        }))
        status = catalog_module.sync_widget_schema(force=True)
        assert "futurewidget59" in catalog_module.WIDGET_CATALOG
        assert catalog_module.WIDGET_CATALOG["futurewidget59"]["fields"][1]["kind"] == "secret"
        assert status["official_auto"] >= 60

        client = TestClient(app)
        login(client)
        page = client.get("/services/item/new?widget=futurewidget59")
        assert page.status_code == 200
        assert 'value="futurewidget59"' in page.text
        assert '"auto_generated": true' in page.text
    finally:
        catalog_module.reset_widget_schema_cache()
        catalog_module.WIDGET_CATALOG.clear()
        catalog_module.WIDGET_CATALOG.update(original)


def test_v032_bookmark_copy_is_general_and_back_to_top_is_global() -> None:
    client = TestClient(app)
    login(client)
    page = client.get("/bookmarks")
    assert page.status_code == 200
    assert "网站书签、快捷链接和分类" in page.text
    assert "PT 站点" not in page.text
    form = client.get("/bookmarks/item/new?group=0")
    assert "常用网站、工具、文档和其他快捷入口" in form.text
    assert "PT 站点" not in form.text
    assert "data-back-to-top" in page.text


def test_v032_widget_schema_management_page() -> None:
    client = TestClient(app)
    login(client)
    page = client.get("/widget-schema")
    assert page.status_code == 200
    assert "Widget Schema" in page.text
    assert "立即同步官方 Schema" in page.text


def test_v032_schema_parser_merges_multiple_official_examples() -> None:
    from app.widget_schema_sync import parse_widget_document

    markdown = '''---
title: Demo
description: Demo Widget Configuration
---
Allowed fields: `["one", "two"]`.
```yaml
widget:
  type: demo
  url: http://demo
  key: first-key
```
```yaml
widget:
  type: demo
  url: http://demo
  mode: advanced # optional
  nested:
    one: two
```
'''
    parsed = parse_widget_document(markdown, "demo")
    assert parsed is not None
    _, schema = parsed
    fields = {field["name"]: field for field in schema["fields"]}
    assert set(fields) == {"url", "key", "mode", "nested"}
    assert fields["mode"]["required"] is False
    assert fields["nested"]["kind"] == "yaml"


def test_v032_schema_management_offline_import(monkeypatch) -> None:
    import json
    from app import widget_catalog as catalog_module

    client = TestClient(app)
    csrf = login(client)
    fake = {
        f"imported{i}": {
            "label": f"Imported {i}",
            "category": "应用",
            "description": "Imported schema",
            "docs": "https://gethomepage.dev/widgets/services/",
            "test": "config",
            "allowed_fields": [],
            "fields": [{"name": "url", "label": "服务地址", "kind": "text", "required": True}],
            "enhanced": True,
            "auto_generated": True,
            "source_mode": "official-auto",
        }
        for i in range(20)
    }
    original = {key: dict(value) for key, value in catalog_module.WIDGET_CATALOG.items()}
    try:
        response = client.post(
            "/widget-schema/import",
            data={"csrf": csrf, "schema_json": json.dumps({"widgets": fake})},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "imported19" in catalog_module.WIDGET_CATALOG
    finally:
        catalog_module.reset_widget_schema_cache()
        catalog_module.WIDGET_CATALOG.clear()
        catalog_module.WIDGET_CATALOG.update(original)


def test_v032_auto_schema_number_fields_accept_decimal_values() -> None:
    from app.main import _coerce_widget_field

    assert _coerce_widget_field("number", "15") == 15
    assert _coerce_widget_field("number", "1.5") == 1.5
    assert _coerce_widget_field("number", "-0.25") == -0.25


def test_v032_schema_parser_handles_full_service_examples_and_commented_options() -> None:
    from app.widget_schema_sync import parse_widget_document

    markdown = '''---
title: Nested Demo
---
```yaml
- Apps:
    - Nested Demo:
        href: http://demo
        widget:
          type: nesteddemo
          url: http://demo
          key: secret-value
          # refreshInterval: 1500 # optional refresh interval
```
'''
    parsed = parse_widget_document(markdown, "nested-demo")
    assert parsed is not None
    widget_type, schema = parsed
    assert widget_type == "nesteddemo"
    fields = {field["name"]: field for field in schema["fields"]}
    assert set(fields) == {"url", "key", "refreshInterval"}
    assert fields["key"]["kind"] == "secret"
    assert fields["refreshInterval"]["kind"] == "number"
    assert fields["refreshInterval"]["required"] is False


def test_v033_widget_schema_default_ref_is_dev() -> None:
    from app.settings import settings
    assert settings.widget_schema_ref == "dev"


def test_v033_sync_cli_default_ref_is_dev() -> None:
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "scripts" / "sync_widget_schema.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--ref", default="dev")' in source
    assert 'default="master"' not in source


def test_v033_no_master_fallback_in_widget_catalog() -> None:
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app" / "widget_catalog.py").read_text(encoding="utf-8")
    assert 'widget_schema_ref", "master"' not in source


def test_v034_schema_page_uses_version_neutral_copy_and_local_time_renderer() -> None:
    client = TestClient(app)
    login(client)
    response = client.get("/widget-schema")
    assert response.status_code == 200
    assert "v0.3.2 不再依赖" not in response.text
    assert "自动同步计划" in response.text
    assert 'name="mode"' in response.text
    assert 'name="daily_time"' in response.text
    assert 'name="timezone"' in response.text
    source = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "data-local-datetime" in source
    assert "Intl.DateTimeFormat" in source


def test_v034_widget_schema_schedule_can_be_configured_and_reset() -> None:
    client = TestClient(app)
    csrf = login(client)
    try:
        response = client.post(
            "/widget-schema/schedule",
            data={
                "csrf": csrf,
                "auto_sync": "on",
                "mode": "daily",
                "interval_hours": "12",
                "daily_time": "04:30",
                "timezone": "Asia/Shanghai",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        prefs = store.widget_schema_sync_preferences()
        assert prefs["custom"] is True
        assert prefs["auto_sync"] is True
        assert prefs["mode"] == "daily"
        assert prefs["daily_time"] == "04:30"
        assert prefs["timezone"] == "Asia/Shanghai"
        page = client.get("/widget-schema")
        assert 'value="04:30"' in page.text
        assert 'value="Asia/Shanghai"' in page.text
    finally:
        store.reset_widget_schema_sync_preferences("test")
    assert store.widget_schema_sync_preferences()["custom"] is False


def test_v034_daily_widget_schema_schedule_uses_configured_timezone() -> None:
    from datetime import datetime, timezone
    from app import widget_catalog as catalog_module

    original_state = dict(catalog_module._SCHEMA_STATE)
    try:
        store.set_widget_schema_sync_preferences(
            auto_sync=True,
            mode="daily",
            interval_hours=24,
            daily_time="03:00",
            timezone_name="Asia/Shanghai",
            actor="test",
        )
        catalog_module._SCHEMA_STATE["synced_at"] = "2026-08-09T17:00:00Z"  # 01:00 Asia/Shanghai
        assert catalog_module.widget_schema_sync_due(datetime(2026, 8, 9, 18, 30, tzinfo=timezone.utc)) is False
        assert catalog_module.widget_schema_sync_due(datetime(2026, 8, 9, 19, 1, tzinfo=timezone.utc)) is True
        catalog_module._SCHEMA_STATE["synced_at"] = "2026-08-09T19:05:00Z"  # 03:05 Asia/Shanghai
        assert catalog_module.widget_schema_sync_due(datetime(2026, 8, 9, 20, 0, tzinfo=timezone.utc)) is False
        assert catalog_module.widget_schema_next_sync_at(datetime(2026, 8, 9, 20, 0, tzinfo=timezone.utc)) == "2026-08-10T19:00:00Z"
    finally:
        catalog_module._SCHEMA_STATE.clear()
        catalog_module._SCHEMA_STATE.update(original_state)
        store.reset_widget_schema_sync_preferences("test")


def test_v034_widget_schema_schedule_rejects_invalid_timezone() -> None:
    client = TestClient(app)
    csrf = login(client)
    response = client.post(
        "/widget-schema/schedule",
        data={
            "csrf": csrf,
            "auto_sync": "on",
            "mode": "daily",
            "interval_hours": "24",
            "daily_time": "03:00",
            "timezone": "Not/A-Timezone",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


def test_v035_homeassistant_custom_is_optional_after_schema_merge() -> None:
    from app.widget_catalog import _merge_synced_catalog

    synced = {
        "homeassistant": {
            "label": "Home Assistant",
            "fields": [
                {"name": "url", "kind": "text", "required": True},
                {"name": "key", "kind": "secret", "required": True},
                # Simulate a cache generated by v0.3.4, where example presence was
                # incorrectly interpreted as mandatory.
                {"name": "custom", "kind": "yaml", "required": True},
            ],
            "allowed_fields": ["people_home", "lights_on", "switches_on"],
        }
    }
    merged = _merge_synced_catalog(synced)["homeassistant"]
    fields = {field["name"]: field for field in merged["fields"]}
    assert fields["url"]["required"] is True
    assert fields["key"]["required"] is True
    assert fields["custom"]["required"] is False
    assert "可选" in fields["custom"]["label"]


def test_v035_official_examples_are_not_assumed_required_without_explicit_signal() -> None:
    from app.widget_schema_sync import parse_widget_document

    markdown = '''---
title: Example Widget
---
```yaml
widget:
  type: examplewidget
  url: http://example
  token: abc123
  extra: enabled
  mustHave: yes # required
```
'''
    parsed = parse_widget_document(markdown, "example-widget")
    assert parsed is not None
    _, schema = parsed
    fields = {field["name"]: field for field in schema["fields"]}
    assert fields["url"]["required"] is False
    assert fields["token"]["required"] is False
    assert fields["extra"]["required"] is False
    assert fields["mustHave"]["required"] is True
    assert fields["mustHave"]["required_source"] == "official-comment"


def test_v035_homeassistant_connection_test_does_not_require_custom(monkeypatch) -> None:
    import asyncio
    from app import widget_tester

    async def fake_ha(config):
        return {"ok": True, "message": "ok", "metrics": [], "level": "deep"}

    monkeypatch.setitem(widget_tester.WIDGET_CATALOG, "homeassistant", {
        "test": "homeassistant",
        "fields": [
            {"name": "url", "label": "Home Assistant 地址", "required": True},
            {"name": "key", "label": "长期访问令牌", "required": True},
            {"name": "custom", "label": "自定义状态 / 模板（可选）", "required": False},
        ],
    })
    monkeypatch.setattr(widget_tester, "_test_homeassistant", fake_ha)

    # test_widget builds its tester mapping at call time, so the patched function is used.
    result = asyncio.run(widget_tester.test_widget("homeassistant", {"url": "http://ha:8123", "key": "secret"}))
    assert result["ok"] is True


def test_v035_schema_schedule_controls_are_top_aligned() -> None:
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert ".schema-schedule-fields { align-items: start; }" in css
    assert ".schema-schedule-fields > label { align-content: start; }" in css


def test_v036_generated_widget_fields_reserve_help_row_for_alignment() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(encoding="utf-8")
    assert 'class="widget-schema-field"' in js
    assert 'field-help empty' in js
    assert '.widget-schema-field {' in css
    assert 'grid-template-rows: minmax(18px, auto) 42px minmax(15px, auto);' in css
    assert '.widget-schema-field > .field-help.empty { visibility: hidden; }' in css


def test_v036_schema_fetch_emits_real_progress(monkeypatch) -> None:
    from app import widget_schema_sync as sync_module

    listing = [
        {"name": "alpha.md", "download_url": "https://example.invalid/alpha"},
        {"name": "beta.md", "download_url": "https://example.invalid/beta"},
    ]
    docs = {
        "https://example.invalid/alpha": '''---\ntitle: Alpha\n---\n```yaml\nwidget:\n  type: alpha\n  url: http://alpha\n```\n''',
        "https://example.invalid/beta": '''---\ntitle: Beta\n---\n```yaml\nwidget:\n  type: beta\n  url: http://beta\n```\n''',
    }
    registry = 'const widgets = { alpha: alpha, beta: beta };'

    monkeypatch.setattr(sync_module, "_request_json", lambda url, timeout: listing)
    monkeypatch.setattr(sync_module, "_request_text", lambda url, timeout: registry if "widgets.js" in url else docs[url])
    progress = []
    schemas, meta = sync_module.fetch_official_widget_schemas(progress=progress.append, workers=2)

    assert set(schemas) >= {"alpha", "beta"}
    assert meta["document_count"] == 2
    assert any(item["stage"] == "documents" and item["current"] == 2 for item in progress)
    assert any(item["stage"] == "registry" for item in progress)
    assert progress[-1]["stage"] == "complete"
    assert progress[-1]["percent"] == 100


def test_v036_manual_schema_sync_job_exposes_progress(monkeypatch) -> None:
    import time
    from app import widget_catalog as catalog_module

    original = dict(catalog_module._MANUAL_SYNC_STATE)

    def fake_sync(*, force=True, progress_callback=None):
        assert force is True
        assert progress_callback is not None
        progress_callback({"stage": "documents", "message": "处理中", "current": 1, "total": 2, "percent": 50})
        time.sleep(0.02)
        progress_callback({"stage": "complete", "message": "完成", "current": 2, "total": 2, "percent": 100})
        return {"widget_count": 167, "generated_field_count": 514}

    monkeypatch.setattr(catalog_module, "sync_widget_schema", fake_sync)
    try:
        state = catalog_module.start_widget_schema_sync_job()
        assert state["running"] is True
        deadline = time.time() + 1
        while time.time() < deadline:
            state = catalog_module.widget_schema_sync_job_status()
            if not state["running"]:
                break
            time.sleep(0.01)
        assert state["running"] is False
        assert state["stage"] == "complete"
        assert state["percent"] == 100
        assert state["result"]["widget_count"] == 167
    finally:
        with catalog_module._MANUAL_SYNC_LOCK:
            catalog_module._MANUAL_SYNC_STATE.clear()
            catalog_module._MANUAL_SYNC_STATE.update(original)


def test_v036_schema_page_has_ajax_progress_ui() -> None:
    client = TestClient(app)
    login(client)
    response = client.get("/widget-schema")
    assert response.status_code == 200
    html = response.text
    assert 'data-schema-sync-form' in html
    assert 'data-schema-sync-progress' in html
    assert 'data-schema-sync-bar' in html
    assert '/api/widget-schema/sync/start' in (Path(__file__).resolve().parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_v037_proxmox_import_normalizes_trailing_slash() -> None:
    client = TestClient(app)
    csrf = login(client)
    services_path = settings.config_dir / "services.yaml"
    proxmox_path = settings.config_dir / "proxmox.yaml"
    services_original = services_path.read_text(encoding="utf-8")
    proxmox_original = proxmox_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            '''---
- Widgets:
    - Proxmox VE:
        widget:
          type: proxmox
          url: https://pve.example/
          username: homepage@pve!homepage
          password: token-secret
          node: asp-pve
''',
            encoding="utf-8",
        )
        proxmox_path.write_text("---\n", encoding="utf-8")
        response = client.post(
            "/proxmox/import-connection",
            data={"csrf": csrf, "group_index": "0", "item_index": "0"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        proxmox = YAML(typ="safe").load(proxmox_path.read_text(encoding="utf-8"))
        assert proxmox["asp-pve"]["url"] == "https://pve.example"
    finally:
        services_path.write_text(services_original, encoding="utf-8")
        proxmox_path.write_text(proxmox_original, encoding="utf-8")


def test_v037_proxmox_page_warns_and_can_normalize_existing_url(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    proxmox_path = settings.config_dir / "proxmox.yaml"
    original = proxmox_path.read_text(encoding="utf-8")
    try:
        proxmox_path.write_text(
            '''---
asp-pve:
  url: https://pve.example/
  token: homepage@pve!homepage
  secret: token-secret
''',
            encoding="utf-8",
        )

        async def fake_discover(connection):
            return [{
                "vmid": 100,
                "name": "HomeAssistant",
                "type": "qemu",
                "node": "asp-pve",
                "status": "running",
                "cpu_percent": 1.2,
                "memory_percent": 91.9,
            }]

        monkeypatch.setattr(main_module.proxmox_discovery, "discover", fake_discover)
        page = client.get("/proxmox?server=asp-pve")
        assert page.status_code == 200
        assert "检测到 Proxmox URL 末尾包含 /" in page.text
        assert "一键修复 URL" in page.text

        response = client.post(
            "/proxmox/normalize-connection",
            data={"csrf": csrf, "server": "asp-pve"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        proxmox = YAML(typ="safe").load(proxmox_path.read_text(encoding="utf-8"))
        assert proxmox["asp-pve"]["url"] == "https://pve.example"
    finally:
        proxmox_path.write_text(original, encoding="utf-8")


def test_v037_proxmox_uses_physical_node_for_binding_and_flags_missing_connection(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    proxmox_path = settings.config_dir / "proxmox.yaml"
    original = proxmox_path.read_text(encoding="utf-8")
    try:
        proxmox_path.write_text(
            '''---
cluster-entry:
  url: https://pve.example
  token: homepage@pve!homepage
  secret: token-secret
''',
            encoding="utf-8",
        )

        async def fake_discover(connection):
            return [{
                "vmid": 101,
                "name": "Reverse-Proxy",
                "type": "qemu",
                "node": "asp-pve",
                "status": "running",
                "cpu_percent": 0.5,
                "memory_percent": 68.0,
            }]

        monkeypatch.setattr(main_module.proxmox_discovery, "discover", fake_discover)
        page = client.get("/proxmox?server=cluster-entry")
        assert page.status_code == 200
        assert "发现未配置同名连接的实际 PVE 节点" in page.text
        assert "asp-pve" in page.text
        assert "不能安全生成 Homepage per-VM 关联" in page.text
        assert 'name="server" value="asp-pve"' not in page.text
    finally:
        proxmox_path.write_text(original, encoding="utf-8")


def test_v037_proxmox_binding_can_clear_existing_docker_integration(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    services_path = settings.config_dir / "services.yaml"
    proxmox_path = settings.config_dir / "proxmox.yaml"
    services_original = services_path.read_text(encoding="utf-8")
    proxmox_original = proxmox_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            '''---
- Widgets:
    - Home Assistant:
        href: https://home.example
        server: local-docker
        container: jellyfin
        widget:
          type: homeassistant
          url: https://home.example
          key: secret
''',
            encoding="utf-8",
        )
        proxmox_path.write_text(
            '''---
asp-pve:
  url: https://pve.example
  token: homepage@pve!homepage
  secret: token-secret
''',
            encoding="utf-8",
        )

        async def fake_discover(connection):
            return [{
                "vmid": 100,
                "name": "HomeAssistant",
                "type": "qemu",
                "node": "asp-pve",
                "status": "running",
                "cpu_percent": 1.2,
                "memory_percent": 91.9,
            }]

        monkeypatch.setattr(main_module.proxmox_discovery, "discover", fake_discover)
        page = client.get("/proxmox?server=asp-pve")
        assert 'data-has-docker="1"' in page.text

        response = client.post(
            "/proxmox/bind",
            data={
                "csrf": csrf,
                "server": "asp-pve",
                "group_index": "0",
                "item_index": "0",
                "vmid": "100",
                "type": "qemu",
                "clear_docker": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(services_path.read_text(encoding="utf-8"))
        details = data[0]["Widgets"][0]["Home Assistant"]
        assert details["proxmoxNode"] == "asp-pve"
        assert details["proxmoxVMID"] == 100
        assert "server" not in details
        assert "container" not in details
    finally:
        services_path.write_text(services_original, encoding="utf-8")
        proxmox_path.write_text(proxmox_original, encoding="utf-8")


def test_v037_service_editor_warns_when_docker_and_proxmox_are_both_configured() -> None:
    client = TestClient(app)
    login(client)
    services_path = settings.config_dir / "services.yaml"
    original = services_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            '''---
- Widgets:
    - Home Assistant:
        server: local-docker
        container: jellyfin
        proxmoxNode: asp-pve
        proxmoxVMID: 100
''',
            encoding="utf-8",
        )
        page = client.get("/services/item/0/0/edit")
        assert page.status_code == 200
        assert "检测到双重运行状态集成" in page.text
        assert "local-docker / jellyfin" in page.text
    finally:
        services_path.write_text(original, encoding="utf-8")


def test_v038_proxmox_service_editor_fields_are_row_aligned() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / "app/templates/service_form.html").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert 'class="form-grid three proxmox-service-grid"' in template
    assert template.count('class="proxmox-service-field"') == 3
    assert template.count('class="field-help empty"') >= 2
    assert ".proxmox-service-grid > .proxmox-service-field" in css
    assert "grid-template-rows: auto 42px minmax(16px, auto)" in css


def test_v038_proxmox_page_shows_edit_and_unbind_for_bound_service(monkeypatch) -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    services_path = settings.config_dir / "services.yaml"
    proxmox_path = settings.config_dir / "proxmox.yaml"
    services_original = services_path.read_text(encoding="utf-8")
    proxmox_original = proxmox_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            """---
- Widgets:
    - Home Assistant:
        proxmoxNode: asp-pve
        proxmoxVMID: 100
""",
            encoding="utf-8",
        )
        proxmox_path.write_text(
            """---
asp-pve:
  url: https://pve.example
  token: homepage@pve!homepage
  secret: token-secret
""",
            encoding="utf-8",
        )

        async def fake_discover(connection):
            return [{
                "vmid": 100,
                "name": "HomeAssistant",
                "type": "qemu",
                "node": "asp-pve",
                "status": "running",
                "cpu_percent": 1.2,
                "memory_percent": 91.9,
            }]

        monkeypatch.setattr(main_module.proxmox_discovery, "discover", fake_discover)
        page = client.get("/proxmox?server=asp-pve")
        assert page.status_code == 200
        assert "编辑服务" in page.text
        assert "取消关联" in page.text
        assert 'action="/proxmox/unbind"' in page.text
        assert "服务本身不会删除" in page.text
    finally:
        services_path.write_text(services_original, encoding="utf-8")
        proxmox_path.write_text(proxmox_original, encoding="utf-8")


def test_v038_proxmox_unbind_removes_only_proxmox_mapping() -> None:
    client = TestClient(app)
    csrf = login(client)
    services_path = settings.config_dir / "services.yaml"
    original = services_path.read_text(encoding="utf-8")
    try:
        services_path.write_text(
            """---
- Widgets:
    - Home Assistant:
        href: https://home.example
        description: Home Assistant 智能家居
        proxmoxNode: asp-pve
        proxmoxVMID: 100
        widget:
          type: homeassistant
          url: https://home.example
          key: secret
""",
            encoding="utf-8",
        )
        response = client.post(
            "/proxmox/unbind",
            data={
                "csrf": csrf,
                "server": "asp-pve",
                "node": "asp-pve",
                "vmid": "100",
                "type": "qemu",
                "group_index": "0",
                "item_index": "0",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(services_path.read_text(encoding="utf-8"))
        details = data[0]["Widgets"][0]["Home Assistant"]
        assert "proxmoxNode" not in details
        assert "proxmoxVMID" not in details
        assert "proxmoxType" not in details
        assert details["href"] == "https://home.example"
        assert details["widget"]["type"] == "homeassistant"
        assert details["widget"]["key"] == "secret"
    finally:
        services_path.write_text(original, encoding="utf-8")


def test_v039_proxmox_bound_actions_have_identical_button_sizing() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    template = (root / "app/templates/proxmox.html").read_text(encoding="utf-8")
    assert 'class="proxmox-bound-actions"' in template
    assert 'class="button secondary full"' in template
    assert 'class="button danger-outline full"' in template
    assert '.proxmox-bound-actions form { margin: 0; display: flex; min-width: 0; }' in css
    assert '.proxmox-bound-actions form > .button { width: 100%; min-height: 44px; height: 100%; }' in css


def test_v040_multi_docker_hosts_are_discovered_and_matched_by_server(monkeypatch) -> None:
    from app import main as main_module
    from app.docker_client import DockerDiscoveryClient

    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    services_path = settings.config_dir / "services.yaml"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_services = services_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text(
            "---\ndocker-a:\n  host: docker-a-proxy\n  port: 2375\ndocker-b:\n  host: 10.10.1.13\n  port: 2375\n",
            encoding="utf-8",
        )
        services_path.write_text(
            "---\n- Core:\n    - App A:\n        server: docker-a\n        container: same-app\n",
            encoding="utf-8",
        )
        sample = [{"id": "abc123def456", "name": "same-app", "image": "example/app:latest", "state": "running", "status": "Up", "ports": [], "labels": {}}]
        monkeypatch.setattr(DockerDiscoveryClient, "ping", lambda self: True)
        monkeypatch.setattr(DockerDiscoveryClient, "list_containers", lambda self: sample)
        page = client.get("/docker?host=all")
        assert page.status_code == 200
        assert "全部 Docker 主机" in page.text
        assert "docker-a" in page.text and "docker-b" in page.text
        assert page.text.count('data-added="1"') == 1
        assert page.text.count('data-added="0"') == 1
        assert "server: docker-a" in page.text
        assert "server: docker-b" in page.text
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        services_path.write_text(original_services, encoding="utf-8")


def test_v040_import_uses_selected_docker_host_server(monkeypatch) -> None:
    from app import main as main_module
    from app.docker_client import DockerDiscoveryClient

    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    original = docker_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text(
            "---\ndocker-main:\n  host: main-proxy\n  port: 2375\ngame-server:\n  host: 10.10.1.13\n  port: 2375\n",
            encoding="utf-8",
        )
        sample = [{"id": "game123456789", "name": "minecraft", "image": "itzg/minecraft-server:latest", "state": "running", "status": "Up", "ports": [{"private": 25565, "public": 25565, "type": "tcp", "ip": "0.0.0.0"}], "labels": {}}]
        monkeypatch.setattr(DockerDiscoveryClient, "ping", lambda self: True)
        monkeypatch.setattr(DockerDiscoveryClient, "list_containers", lambda self: sample)
        hosts = main_module.docker_discovery_hosts()
        game = next(item for item in hosts if item["homepage_server"] == "game-server")
        wizard = client.get(f"/docker/host/{game['id']}/import/game123456789")
        assert wizard.status_code == 200
        assert "game-server" in wizard.text
        assert 'data-wizard-static="server"' in wizard.text
        assert 'value="game-server"' in wizard.text
        assert "10.10.1.13:25565" in wizard.text
    finally:
        docker_path.write_text(original, encoding="utf-8")


def test_v040_custom_docker_host_can_save_test_and_sync_to_docker_yaml(monkeypatch) -> None:
    from app.docker_client import DockerDiscoveryClient

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\n", encoding="utf-8")
        monkeypatch.setattr(DockerDiscoveryClient, "ping", lambda self: True)
        monkeypatch.setattr(DockerDiscoveryClient, "list_containers", lambda self: [{"id": "1", "name": "minecraft", "image": "mc", "state": "running", "status": "Up", "ports": [], "labels": {}}])
        tested = client.post(
            "/api/docker/hosts/test",
            data={"csrf": csrf, "url": "http://10.10.1.13:2375", "homepage_server": "game-server"},
        )
        assert tested.status_code == 200
        assert tested.json()["containers"] == 1

        saved = client.post(
            "/docker/hosts/save",
            data={
                "csrf": csrf,
                "id": "game-server",
                "name": "Game-Server VM",
                "url": "http://10.10.1.13:2375",
                "homepage_server": "game-server",
                "public_host": "10.10.1.13",
                "sync_homepage": "1",
            },
            follow_redirects=False,
        )
        assert saved.status_code == 303
        assert any(item["id"] == "game-server" for item in store.docker_discovery_hosts())
        docker_data = YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
        assert docker_data["game-server"]["host"] == "10.10.1.13"
        assert docker_data["game-server"]["port"] == 2375
        manager = client.get("/docker/hosts")
        assert "Game-Server VM" in manager.text
        assert "Homepage 已配置" in manager.text
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v040_docker_yaml_headers_are_not_exposed_in_host_manager() -> None:
    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    original = docker_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text(
            "---\nsecure-docker:\n  host: docker.example.internal\n  port: 443\n  protocol: https\n  headers:\n    Authorization: Bearer top-secret-token\n",
            encoding="utf-8",
        )
        page = client.get("/docker/hosts")
        assert page.status_code == 200
        assert "secure-docker" in page.text
        assert "认证 Header" in page.text
        assert "top-secret-token" not in page.text
        assert "Bearer" not in page.text
    finally:
        docker_path.write_text(original, encoding="utf-8")


def test_v041_docker_yaml_host_has_visual_edit_and_delete_controls() -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    original = docker_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text("---\nlocal-docker:\n  host: homepage-docker-proxy\n  port: 2375\n", encoding="utf-8")
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "local-docker")
        page = client.get("/docker/hosts")
        assert page.status_code == 200
        assert f'/docker/hosts?edit={host["id"]}' in page.text
        assert f'/docker/hosts/delete/{host["id"]}' in page.text

        edit = client.get(f'/docker/hosts?edit={host["id"]}')
        assert edit.status_code == 200
        assert "编辑 Docker 主机" in edit.text
        assert 'name="homepage_server" value="local-docker"' in edit.text
        assert 'name="url" value="http://homepage-docker-proxy:2375"' in edit.text
        assert "编辑 docker.yaml Server" not in edit.text
        assert "编辑自定义连接" not in edit.text
    finally:
        docker_path.write_text(original, encoding="utf-8")


def test_v041_visual_docker_yaml_edit_preserves_advanced_fields() -> None:
    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    original = docker_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text(
            "---\nsecure:\n  host: old-host\n  port: 443\n  protocol: https\n  headers:\n    Authorization: Bearer keep-me\n  tls:\n    caFile: ca.pem\n  customFutureKey: preserved\n",
            encoding="utf-8",
        )
        response = client.post(
            "/docker/hosts/yaml-save",
            data={
                "csrf": csrf,
                "server_name": "secure",
                "mode": "remote",
                "host": "new-host",
                "port": "2375",
                "protocol": "http",
                "socket": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        data = YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
        assert data["secure"]["host"] == "new-host"
        assert data["secure"]["port"] == 2375
        assert data["secure"]["protocol"] == "http"
        assert data["secure"]["headers"]["Authorization"] == "Bearer keep-me"
        assert data["secure"]["tls"]["caFile"] == "ca.pem"
        assert data["secure"]["customFutureKey"] == "preserved"
    finally:
        docker_path.write_text(original, encoding="utf-8")


def test_v041_delete_wizard_lists_service_references_and_requires_delete_confirmation() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    services_path = settings.config_dir / "services.yaml"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_services = services_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text("---\nlocal-docker:\n  host: proxy\n  port: 2375\n", encoding="utf-8")
        services_path.write_text(
            "---\n- Core:\n    - Jellyfin:\n        server: local-docker\n        container: jellyfin\n    - qBittorrent:\n        server: local-docker\n        container: qbittorrent\n",
            encoding="utf-8",
        )
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "local-docker")
        page = client.get(f'/docker/hosts/delete/{host["id"]}')
        assert page.status_code == 200
        assert "当前 Server 被 2 个服务引用" in page.text
        assert "Jellyfin" in page.text and "qBittorrent" in page.text

        rejected = client.post(
            "/docker/hosts/delete-confirm",
            data={
                "csrf": csrf,
                "host_id": host["id"],
                "homepage_server": "local-docker",
                "remove_yaml": "1",
                "confirm_text": "",
            },
            follow_redirects=False,
        )
        assert rejected.status_code == 303
        assert "local-docker" in YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        services_path.write_text(original_services, encoding="utf-8")


def test_v041_delete_yaml_server_can_keep_or_clear_service_references() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    services_path = settings.config_dir / "services.yaml"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_services = services_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text("---\nold-server:\n  host: proxy\n  port: 2375\n", encoding="utf-8")
        services_path.write_text("---\n- Core:\n    - App:\n        server: old-server\n        container: app\n", encoding="utf-8")
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "old-server")
        response = client.post(
            "/docker/hosts/delete-confirm",
            data={
                "csrf": csrf,
                "host_id": host["id"],
                "homepage_server": "old-server",
                "remove_yaml": "1",
                "clear_refs": "1",
                "confirm_text": "DELETE",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "old-server" not in (YAML(typ="safe").load(docker_path.read_text(encoding="utf-8")) or {})
        services = YAML(typ="safe").load(services_path.read_text(encoding="utf-8"))
        details = services[0]["Core"][0]["App"]
        assert "server" not in details
        assert "container" not in details
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        services_path.write_text(original_services, encoding="utf-8")


def test_v041_custom_delete_wizard_can_remove_only_admin_layer() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\ngame-server:\n  host: 10.10.1.13\n  port: 2375\n", encoding="utf-8")
        store.save_docker_discovery_host(
            {"id": "game-server", "name": "Game VM", "url": "http://10.10.1.13:2375", "homepage_server": "game-server", "public_host": "10.10.1.13"},
            "test",
        )
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "game-server")
        response = client.post(
            "/docker/hosts/delete-confirm",
            data={
                "csrf": csrf,
                "host_id": host["id"],
                "homepage_server": "game-server",
                "remove_custom": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert not store.docker_discovery_hosts()
        assert "game-server" in YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v041_delete_yaml_server_can_intentionally_keep_service_references() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    services_path = settings.config_dir / "services.yaml"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_services = services_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text("---\nold-server:\n  host: proxy\n  port: 2375\n", encoding="utf-8")
        services_path.write_text("---\n- Core:\n    - App:\n        server: old-server\n        container: app\n", encoding="utf-8")
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "old-server")
        response = client.post(
            "/docker/hosts/delete-confirm",
            data={
                "csrf": csrf,
                "host_id": host["id"],
                "homepage_server": "old-server",
                "remove_yaml": "1",
                "confirm_text": "DELETE",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "old-server" not in (YAML(typ="safe").load(docker_path.read_text(encoding="utf-8")) or {})
        services = YAML(typ="safe").load(services_path.read_text(encoding="utf-8"))
        details = services[0]["Core"][0]["App"]
        assert details["server"] == "old-server"
        assert details["container"] == "app"
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        services_path.write_text(original_services, encoding="utf-8")


def test_v042_docker_discovery_page_removes_redundant_host_status_cards(monkeypatch) -> None:
    from app import main as main_module
    from app.docker_client import DockerDiscoveryClient

    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    original = docker_path.read_text(encoding="utf-8")
    try:
        docker_path.write_text("---\nlocal-docker:\n  host: homepage-docker-proxy\n  port: 2375\n", encoding="utf-8")
        monkeypatch.setattr(DockerDiscoveryClient, "ping", lambda self: True)
        monkeypatch.setattr(DockerDiscoveryClient, "list_containers", lambda self: [])
        page = client.get("/docker")
        assert page.status_code == 200
        assert "Docker 主机 / 连接" in page.text
        assert "docker-host-status-grid" not in page.text
        assert "Homepage Server：" not in page.text
    finally:
        docker_path.write_text(original, encoding="utf-8")


def test_v042_yaml_and_custom_hosts_use_same_edit_form() -> None:
    from app import main as main_module

    client = TestClient(app)
    login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text(
            "---\nlocal-docker:\n  host: homepage-docker-proxy\n  port: 2375\ngame-server:\n  host: 10.10.1.12\n  port: 2375\n",
            encoding="utf-8",
        )
        store.save_docker_discovery_host(
            {"id": "game-server", "name": "Game-Server VM", "url": "http://10.10.1.12:2375", "homepage_server": "game-server", "public_host": "10.10.1.12"},
            "test",
        )
        hosts = main_module.docker_discovery_hosts()
        local = next(item for item in hosts if item["homepage_server"] == "local-docker")
        game = next(item for item in hosts if item["homepage_server"] == "game-server")
        local_page = client.get(f'/docker/hosts?edit={local["id"]}')
        game_page = client.get(f'/docker/hosts?edit={game["id"]}')
        for page in (local_page, game_page):
            assert page.status_code == 200
            assert "编辑 Docker 主机" in page.text
            assert 'action="/docker/hosts/save"' in page.text
            assert "编辑 docker.yaml Server" not in page.text
            assert "编辑自定义连接" not in page.text
        assert 'value="local-docker"' in local_page.text
        assert 'value="Game-Server VM"' in game_page.text
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v042_add_host_always_creates_homepage_server_without_checkbox() -> None:
    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\n", encoding="utf-8")
        page = client.get("/docker/hosts")
        assert page.status_code == 200
        assert 'name="sync_homepage"' not in page.text
        assert "若 docker.yaml 没有同名 Server，则同时创建" not in page.text
        assert "连接信息只写" in page.text

        response = client.post(
            "/docker/hosts/save",
            data={
                "csrf": csrf,
                "name": "Game-Server VM",
                "url": "http://10.10.1.12:2375",
                "homepage_server": "game-server",
                "public_host": "10.10.1.12",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        docker_data = YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
        assert docker_data["game-server"]["host"] == "10.10.1.12"
        assert docker_data["game-server"]["port"] == 2375
        assert docker_data["game-server"]["protocol"] == "http"
        saved = store.docker_discovery_hosts()
        assert any(item["homepage_server"] == "game-server" and item["name"] == "Game-Server VM" for item in saved)
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v042_edit_yaml_only_host_adopts_unified_metadata_and_preserves_advanced_fields() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text(
            "---\nlocal-docker:\n  host: homepage-docker-proxy\n  port: 2375\n  headers:\n    X-Test: keep-secret\n  customFutureKey: keep-me\n",
            encoding="utf-8",
        )
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "local-docker")
        response = client.post(
            "/docker/hosts/save",
            data={
                "csrf": csrf,
                "original_id": "",
                "original_server": "local-docker",
                "name": "Docker VM",
                "url": "http://homepage-docker-proxy:2375",
                "homepage_server": "local-docker",
                "public_host": "10.10.1.11",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        docker_data = YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
        assert docker_data["local-docker"]["headers"]["X-Test"] == "keep-secret"
        assert docker_data["local-docker"]["customFutureKey"] == "keep-me"
        metadata = next(item for item in store.docker_discovery_hosts() if item["homepage_server"] == "local-docker")
        assert metadata["name"] == "Docker VM"
        assert metadata["public_host"] == "10.10.1.11"
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v042_unified_metadata_keeps_yaml_headers_for_discovery_client() -> None:
    from app import main as main_module

    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text(
            "---\nsecure:\n  host: docker.example.internal\n  port: 443\n  protocol: https\n  headers:\n    Authorization: Bearer keep-secret\n",
            encoding="utf-8",
        )
        store.save_docker_discovery_host(
            {"id": "secure", "name": "Secure Docker", "url": "https://docker.example.internal:443", "homepage_server": "secure", "public_host": "docker.example.internal"},
            "test",
        )
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "secure")
        assert host["client"].headers == {"Authorization": "Bearer keep-secret"}
        safe = main_module._docker_host_safe(host)
        assert "client" not in safe
        assert "keep-secret" not in repr(safe)
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_legacy_docker_rows_migrate_to_metadata_without_duplicate_connection() -> None:
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text(
            "---\nlocal-docker:\n  host: homepage-docker-proxy\n  port: 2375\ngame-server:\n  host: 10.10.1.12\n  port: 2375\n",
            encoding="utf-8",
        )
        prefs_path.write_text(
            json.dumps(
                {
                    "docker_discovery_hosts": [
                        {
                            "id": "local-docker",
                            "name": "Docker VM",
                            "url": "http://homepage-docker-proxy:2375",
                            "homepage_server": "local-docker",
                            "public_host": "10.10.1.11",
                        },
                        {
                            "id": "game-server",
                            "name": "Game-Server VM",
                            "url": "http://10.10.1.12:2375",
                            "homepage_server": "game-server",
                            "public_host": "10.10.1.12",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        assert store.migrate_legacy_docker_host_preferences("test") is True
        prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        assert "docker_discovery_hosts" not in prefs
        metadata = prefs["docker_host_metadata"]
        assert metadata["local-docker"] == {"display_name": "Docker VM", "public_host": "10.10.1.11"}
        assert metadata["game-server"] == {"display_name": "Game-Server VM", "public_host": "10.10.1.12"}
        serialized = json.dumps(prefs, ensure_ascii=False)
        assert "homepage-docker-proxy:2375" not in serialized
        assert "10.10.1.12:2375" not in serialized
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_legacy_different_discovery_url_becomes_explicit_override() -> None:
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\nlocal-docker:\n  socket: /var/run/docker.sock\n", encoding="utf-8")
        prefs_path.write_text(
            json.dumps(
                {
                    "docker_discovery_hosts": [
                        {
                            "id": "local-docker",
                            "name": "Docker VM",
                            "url": "http://homepage-docker-proxy:2375",
                            "homepage_server": "local-docker",
                            "public_host": "10.10.1.11",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        store.migrate_legacy_docker_host_preferences("test")
        metadata = store.docker_host_metadata()["local-docker"]
        assert metadata["discovery_override"] == "http://homepage-docker-proxy:2375"
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_add_host_writes_connection_only_to_docker_yaml() -> None:
    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\n", encoding="utf-8")
        prefs_path.unlink(missing_ok=True)
        response = client.post(
            "/docker/hosts/save",
            data={
                "csrf": csrf,
                "name": "Game-Server VM",
                "url": "http://10.10.1.12:2375",
                "homepage_server": "game-server",
                "public_host": "10.10.1.12",
                "discovery_override": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        docker_data = YAML(typ="safe").load(docker_path.read_text(encoding="utf-8"))
        assert docker_data["game-server"]["host"] == "10.10.1.12"
        assert docker_data["game-server"]["port"] == 2375
        prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
        assert "docker_discovery_hosts" not in prefs
        metadata = prefs["docker_host_metadata"]["game-server"]
        assert metadata == {"display_name": "Game-Server VM", "public_host": "10.10.1.12"}
        assert "url" not in metadata
        assert "homepage_server" not in metadata
        assert "host" not in metadata
        assert "port" not in metadata
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_discovery_reads_core_connection_from_docker_yaml_and_optional_override() -> None:
    from app import main as main_module

    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\ngame-server:\n  host: 10.10.1.12\n  port: 2375\n", encoding="utf-8")
        prefs_path.write_text(
            json.dumps(
                {
                    "docker_host_metadata": {
                        "game-server": {
                            "display_name": "Game VM",
                            "public_host": "10.10.1.12",
                            "discovery_override": "http://10.10.1.99:2375",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "game-server")
        assert host["core_url"] == "http://10.10.1.12:2375"
        assert host["url"] == "http://10.10.1.99:2375"
        assert host["discovery_override"] == "http://10.10.1.99:2375"
        assert host["name"] == "Game VM"
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_delete_host_removes_yaml_and_metadata_together() -> None:
    from app import main as main_module

    client = TestClient(app)
    csrf = login(client)
    docker_path = settings.config_dir / "docker.yaml"
    prefs_path = settings.data_dir / "admin-settings.json"
    original_docker = docker_path.read_text(encoding="utf-8")
    original_prefs = prefs_path.read_text(encoding="utf-8") if prefs_path.exists() else None
    try:
        docker_path.write_text("---\ngame-server:\n  host: 10.10.1.12\n  port: 2375\n", encoding="utf-8")
        store.save_docker_host_metadata("game-server", {"display_name": "Game VM", "public_host": "10.10.1.12"}, "test")
        host = next(item for item in main_module.docker_discovery_hosts() if item["homepage_server"] == "game-server")
        page = client.get(f'/docker/hosts/delete/{host["id"]}')
        assert page.status_code == 200
        assert 'name="remove_yaml" value="1"' in page.text
        assert 'name="remove_custom"' not in page.text
        response = client.post(
            "/docker/hosts/delete-confirm",
            data={
                "csrf": csrf,
                "host_id": host["id"],
                "homepage_server": "game-server",
                "remove_yaml": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "game-server" not in (YAML(typ="safe").load(docker_path.read_text(encoding="utf-8")) or {})
        assert "game-server" not in store.docker_host_metadata()
    finally:
        docker_path.write_text(original_docker, encoding="utf-8")
        if original_prefs is None:
            prefs_path.unlink(missing_ok=True)
        else:
            prefs_path.write_text(original_prefs, encoding="utf-8")


def test_v043_host_manager_explains_single_source_and_optional_override() -> None:
    client = TestClient(app)
    login(client)
    page = client.get("/docker/hosts")
    assert page.status_code == 200
    assert "docker.yaml" in page.text
    assert "唯一配置源" in page.text
    assert "Admin Discovery Override（可选）" in page.text
    assert "Admin 设置中不再复制 Server、Host、Port 或协议" in page.text
