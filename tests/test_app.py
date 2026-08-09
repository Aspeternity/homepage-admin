from __future__ import annotations

import re

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
    for path in ["/services", "/bookmarks", "/settings", "/widgets", "/widget-center", "/docker", "/proxmox", "/yaml/services.yaml", "/backups"]:
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
    assert 'value="http://homepage.local:18080"' in editor.text


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
