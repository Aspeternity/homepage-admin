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


def test_optional_proxy_example_is_separate_and_read_only():
    data = _load_compose("docker-compose.docker-proxy.example.yml")
    proxy = data["services"]["docker-socket-proxy"]
    assert proxy["environment"]["POST"] == "0"
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in proxy["volumes"]
    assert proxy["ports"]


def test_env_example_does_not_require_shared_proxy_settings():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "HOMEPAGE_DOCKER_PROXY_HOST" not in text
    assert "HOMEPAGE_DOCKER_PROXY_PORT" not in text
    assert "DOCKER_DISCOVERY_URL" not in text
    assert "HOMEPAGE_HOST_CONFIG_DIR=" in text
    assert "HOMEPAGE_ADMIN_DATA_DIR=" in text
