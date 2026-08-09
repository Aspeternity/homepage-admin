from __future__ import annotations

from typing import Any

# Curated first-party Homepage widget forms for the services most relevant to homelab users.
# Unknown/unsupported fields are still preserved in the YAML "extra" editor.
WIDGET_CATALOG: dict[str, dict[str, Any]] = {
    "jellyfin": {
        "label": "Jellyfin",
        "docs": "https://gethomepage.dev/widgets/services/jellyfin/",
        "fields": [
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "https://jellyfin.example.com"},
            {"name": "key", "label": "API Key", "kind": "secret"},
            {"name": "version", "label": "Widget API 版本", "kind": "number", "placeholder": "1 或 2"},
            {"name": "enableBlocks", "label": "启用媒体统计块", "kind": "bool"},
            {"name": "enableNowPlaying", "label": "显示正在播放", "kind": "bool"},
            {"name": "enableUser", "label": "显示用户", "kind": "bool"},
            {"name": "enableMediaControl", "label": "启用媒体控制", "kind": "bool"},
            {"name": "showEpisodeNumber", "label": "显示剧集编号", "kind": "bool"},
            {"name": "expandOneStreamToTwoRows", "label": "单流展开两行", "kind": "bool"},
        ],
    },
    "qbittorrent": {
        "label": "qBittorrent",
        "docs": "https://gethomepage.dev/widgets/services/qbittorrent/",
        "fields": [
            {"name": "url", "label": "WebUI 地址", "kind": "text", "placeholder": "http://qbittorrent:8080"},
            {"name": "username", "label": "用户名", "kind": "text"},
            {"name": "password", "label": "密码", "kind": "secret"},
            {"name": "enableLeechProgress", "label": "显示下载进度", "kind": "bool"},
            {"name": "enableLeechSize", "label": "显示下载大小", "kind": "bool"},
        ],
    },
    "transmission": {
        "label": "Transmission",
        "docs": "https://gethomepage.dev/widgets/services/transmission/",
        "fields": [
            {"name": "url", "label": "Web 地址", "kind": "text", "placeholder": "http://transmission:9091"},
            {"name": "username", "label": "用户名", "kind": "text"},
            {"name": "password", "label": "密码", "kind": "secret"},
            {"name": "rpcUrl", "label": "RPC 路径", "kind": "text", "placeholder": "/transmission/"},
        ],
    },
    "minecraft": {
        "label": "Minecraft",
        "docs": "https://gethomepage.dev/widgets/services/minecraft/",
        "fields": [
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "udp://10.10.1.254:25565"},
        ],
    },
    "homeassistant": {
        "label": "Home Assistant",
        "docs": "https://gethomepage.dev/widgets/services/homeassistant/",
        "fields": [
            {"name": "url", "label": "Home Assistant 地址", "kind": "text", "placeholder": "http://homeassistant:8123"},
            {"name": "key", "label": "长期访问令牌", "kind": "secret"},
            {"name": "custom", "label": "自定义状态 / 模板", "kind": "yaml", "rows": 7, "placeholder": "- state: sensor.total_power\n- template: '{{ states.light|selectattr(\"state\",\"equalto\",\"on\")|list|length }}'"},
        ],
    },
    "portainer": {
        "label": "Portainer",
        "docs": "https://gethomepage.dev/widgets/services/portainer/",
        "fields": [
            {"name": "url", "label": "Portainer 地址", "kind": "text", "placeholder": "https://portainer:9443"},
            {"name": "env", "label": "Environment ID", "kind": "number", "placeholder": "1"},
            {"name": "kubernetes", "label": "Kubernetes 模式", "kind": "bool"},
            {"name": "key", "label": "API Key", "kind": "secret"},
        ],
    },
    "proxmox": {
        "label": "Proxmox",
        "docs": "https://gethomepage.dev/widgets/services/proxmox/",
        "fields": [
            {"name": "url", "label": "Proxmox 地址", "kind": "text", "placeholder": "https://pve:8006"},
            {"name": "username", "label": "API Token ID", "kind": "text", "placeholder": "api@pam!homepage"},
            {"name": "password", "label": "Token Secret", "kind": "secret"},
            {"name": "node", "label": "节点（可选）", "kind": "text", "placeholder": "pve"},
        ],
    },
}


def catalog_field_names(widget_type: str) -> set[str]:
    schema = WIDGET_CATALOG.get(widget_type, {})
    return {str(field["name"]) for field in schema.get("fields", [])}


def catalog_secret_names(widget_type: str) -> set[str]:
    schema = WIDGET_CATALOG.get(widget_type, {})
    return {
        str(field["name"])
        for field in schema.get("fields", [])
        if field.get("kind") == "secret"
    }
