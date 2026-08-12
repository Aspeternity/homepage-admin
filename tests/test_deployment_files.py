from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_compose(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_default_compose_is_single_container_without_shared_network_or_proxy():
    for name in ("docker-compose.yml", "docker-compose.ghcr.yml", "docker-compose.portainer.yml"):
        data = _load_compose(name)
        services = data["services"]
        assert list(services) == ["homepage-admin"]
        admin = services["homepage-admin"]
        assert admin["network_mode"] == "bridge"
        assert "networks" not in admin
        assert "depends_on" not in admin
        serialized = (ROOT / name).read_text(encoding="utf-8")
        assert "/var/run/docker.sock" not in serialized
        assert "homepage-tools" not in serialized
        assert "homepage-docker-proxy" not in serialized


def test_v054_default_production_compose_uses_host_data_directory_and_no_credentials():
    for name in ("docker-compose.ghcr.yml", "docker-compose.portainer.yml"):
        data = _load_compose(name)
        admin = data["services"]["homepage-admin"]
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "environment" not in admin
        assert "env_file" not in admin
        assert "user" not in admin
        assert "ADMIN_USERNAME" not in text
        assert "ADMIN_PASSWORD" not in text
        assert "SESSION_SECRET" not in text
        assert "PUID" not in text
        assert "PGID" not in text
        assert admin["network_mode"] == "bridge"
        assert admin["ports"] == ["3001:3001"]
        assert any(str(item).endswith(":/config") for item in admin["volumes"])
        assert "./data:/data" in admin["volumes"]
        assert "volumes" not in data or not data.get("volumes")


def test_optional_proxy_example_is_separate_read_only_bridge_and_has_simple_port_mapping():
    data = _load_compose("docker-compose.docker-proxy.example.yml")
    proxy = data["services"]["docker-socket-proxy"]
    assert proxy["network_mode"] == "bridge"
    assert proxy["environment"]["POST"] == "0"
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in proxy["volumes"]
    assert proxy["ports"] == ["2375:2375"]
    assert "192.0.2.20:2375:2375" not in (ROOT / "docker-compose.docker-proxy.example.yml").read_text(encoding="utf-8")


def test_readme_full_compose_examples_use_bridge_and_unbound_port_mapping():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.count("network_mode: bridge") >= 2
    assert '- "3001:3001"' in text
    assert '- "2375:2375"' in text
    assert "192.0.2.20:2375:2375" not in text
    assert "homepage-admin-data:/data" not in text
    assert "./data:/data" in text


def test_env_example_marks_auth_as_legacy_optional_only():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "does not require an .env file" in text
    assert "# ADMIN_USERNAME=" in text
    assert "# ADMIN_PASSWORD=" in text
    assert "# SESSION_SECRET=" in text
    assert "Legacy compatibility only" in text
    assert "HOMEPAGE_DOCKER_PROXY_HOST" not in text
    assert "DOCKER_DISCOVERY_URL" not in text
