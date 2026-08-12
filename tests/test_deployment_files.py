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
        assert "networks" not in admin
        assert "depends_on" not in admin
        serialized = (ROOT / name).read_text(encoding="utf-8")
        assert "/var/run/docker.sock" not in serialized
        assert "homepage-tools" not in serialized
        assert "homepage-docker-proxy" not in serialized


def test_v053_default_production_compose_has_no_credentials_or_env_file():
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
        assert admin["ports"] == ["3001:3001"]
        assert any(str(item).endswith(":/config") for item in admin["volumes"])
        assert "homepage-admin-data:/data" in admin["volumes"]
        assert "homepage-admin-data" in data.get("volumes", {})


def test_optional_proxy_example_is_separate_and_read_only():
    data = _load_compose("docker-compose.docker-proxy.example.yml")
    proxy = data["services"]["docker-socket-proxy"]
    assert proxy["environment"]["POST"] == "0"
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in proxy["volumes"]
    assert proxy["ports"]


def test_env_example_marks_auth_as_legacy_optional_only():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "does not require an .env file" in text
    assert "# ADMIN_USERNAME=" in text
    assert "# ADMIN_PASSWORD=" in text
    assert "# SESSION_SECRET=" in text
    assert "Legacy compatibility only" in text
    assert "HOMEPAGE_DOCKER_PROXY_HOST" not in text
    assert "DOCKER_DISCOVERY_URL" not in text
