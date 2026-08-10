from __future__ import annotations

from typing import Any, Callable

import copy
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .settings import settings
from .store import store
from .widget_schema_sync import fetch_official_widget_schemas

# Enhanced schemas for the widgets Homepage Admin understands deeply.
# The full official Service Widget index is merged below so every documented widget
# remains searchable even when a bespoke form has not been implemented yet.
ENHANCED_WIDGET_CATALOG: dict[str, dict[str, Any]] = {
    "jellyfin": {
        "label": "Jellyfin",
        "category": "媒体",
        "description": "影视媒体库与当前播放统计。",
        "docs": "https://gethomepage.dev/widgets/services/jellyfin/",
        "icon": "jellyfin.png",
        "test": "jellyfin",
        "allowed_fields": ["movies", "series", "episodes", "songs"],
        "fields": [
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "https://jellyfin.example.com", "required": True},
            {"name": "key", "label": "API Key", "kind": "secret", "required": True},
            {"name": "version", "label": "Widget API 版本", "kind": "number", "placeholder": "1 或 2"},
            {"name": "enableBlocks", "label": "启用媒体统计块", "kind": "bool"},
            {"name": "enableNowPlaying", "label": "显示正在播放", "kind": "bool"},
            {"name": "enableUser", "label": "显示用户", "kind": "bool"},
            {"name": "enableMediaControl", "label": "启用媒体控制", "kind": "bool"},
            {"name": "showEpisodeNumber", "label": "显示剧集编号", "kind": "bool"},
            {"name": "expandOneStreamToTwoRows", "label": "单流展开两行", "kind": "bool"},
        ],
    },
    "portainer": {
        "label": "Portainer",
        "category": "基础设施",
        "description": "Docker / Kubernetes Environment 容器统计。",
        "docs": "https://gethomepage.dev/widgets/services/portainer/",
        "icon": "portainer.png",
        "test": "portainer",
        "allowed_fields": ["running", "stopped", "total"],
        "fields": [
            {"name": "url", "label": "Portainer 地址", "kind": "text", "placeholder": "https://portainer:9443", "required": True},
            {"name": "env", "label": "Environment ID", "kind": "number", "placeholder": "1", "required": True},
            {"name": "kubernetes", "label": "Kubernetes 模式", "kind": "bool"},
            {"name": "key", "label": "API Key", "kind": "secret", "required": True},
        ],
    },
    "proxmox": {
        "label": "Proxmox VE",
        "category": "基础设施",
        "description": "PVE 集群 VM、LXC、CPU 与内存统计。",
        "docs": "https://gethomepage.dev/widgets/services/proxmox/",
        "icon": "proxmox.png",
        "test": "proxmox",
        "allowed_fields": ["vms", "lxc", "resources.cpu", "resources.mem"],
        "fields": [
            {"name": "url", "label": "Proxmox 地址", "kind": "text", "placeholder": "https://pve:8006", "required": True},
            {"name": "username", "label": "API Token ID", "kind": "text", "placeholder": "api@pam!homepage", "required": True},
            {"name": "password", "label": "Token Secret", "kind": "secret", "required": True},
            {"name": "node", "label": "节点（可选）", "kind": "text", "placeholder": "pve"},
        ],
    },
    "homeassistant": {
        "label": "Home Assistant",
        "category": "智能家居",
        "description": "人员、灯光、开关或自定义实体状态。",
        "docs": "https://gethomepage.dev/widgets/services/homeassistant/",
        "icon": "home-assistant.png",
        "test": "homeassistant",
        "allowed_fields": ["people_home", "lights_on", "switches_on"],
        "fields": [
            {"name": "url", "label": "Home Assistant 地址", "kind": "text", "placeholder": "http://homeassistant:8123", "required": True},
            {"name": "key", "label": "长期访问令牌", "kind": "secret", "required": True},
            {"name": "custom", "label": "自定义状态 / 模板（可选）", "kind": "yaml", "rows": 7, "required": False, "placeholder": "- state: sensor.total_power\n- template: '{{ states.light|selectattr(\"state\",\"equalto\",\"on\")|list|length }}'", "help": "可选，最多 4 个 state / template；设置 fields 时 Homepage 会忽略 custom。"},
        ],
    },
    "qbittorrent": {
        "label": "qBittorrent",
        "category": "下载",
        "description": "下载、上传、做种与活动任务统计。",
        "docs": "https://gethomepage.dev/widgets/services/qbittorrent/",
        "icon": "qbittorrent.png",
        "test": "qbittorrent",
        "allowed_fields": ["leech", "download", "seed", "upload"],
        "fields": [
            {"name": "url", "label": "WebUI 地址", "kind": "text", "placeholder": "http://qbittorrent:8080", "required": True},
            {"name": "username", "label": "用户名", "kind": "text"},
            {"name": "password", "label": "密码", "kind": "secret"},
            {"name": "enableLeechProgress", "label": "显示下载进度", "kind": "bool"},
            {"name": "enableLeechSize", "label": "显示下载大小", "kind": "bool"},
        ],
    },
    "transmission": {
        "label": "Transmission",
        "category": "下载",
        "description": "Transmission 下载 / 做种 / 传输统计。",
        "docs": "https://gethomepage.dev/widgets/services/transmission/",
        "icon": "transmission.png",
        "test": "transmission",
        "allowed_fields": ["leech", "download", "seed", "upload"],
        "fields": [
            {"name": "url", "label": "Web 地址", "kind": "text", "placeholder": "http://transmission:9091", "required": True},
            {"name": "username", "label": "用户名", "kind": "text"},
            {"name": "password", "label": "密码", "kind": "secret"},
            {"name": "rpcUrl", "label": "RPC 路径", "kind": "text", "placeholder": "/transmission/"},
        ],
    },
    "diskstation": {
        "label": "Synology DiskStation",
        "category": "存储",
        "description": "DSM 在线时间、卷可用空间、CPU 与内存。",
        "docs": "https://gethomepage.dev/widgets/services/diskstation/",
        "icon": "synology.png",
        "test": "basic",
        "allowed_fields": ["uptime", "volumeAvailable", "resources.cpu", "resources.mem"],
        "fields": [
            {"name": "url", "label": "DSM 地址", "kind": "text", "placeholder": "https://nas:5001", "required": True},
            {"name": "username", "label": "用户名", "kind": "text", "required": True},
            {"name": "password", "label": "密码", "kind": "secret", "required": True},
            {"name": "volume", "label": "卷（可选）", "kind": "text", "placeholder": "volume_1"},
        ],
        "notice": "Homepage 官方 DiskStation Widget 获取系统指标时要求 DSM Administrators 组账号；建议创建权限受限的专用账号。",
    },
    "openwrt": {
        "label": "OpenWRT / ImmortalWRT",
        "category": "网络",
        "description": "OpenWRT/ImmortalWRT 系统与网络接口信息。",
        "docs": "https://gethomepage.dev/widgets/services/openwrt/",
        "icon": "openwrt.png",
        "test": "basic",
        "fields": [
            {"name": "url", "label": "路由器地址", "kind": "text", "placeholder": "http://192.168.1.1", "required": True},
            {"name": "username", "label": "RPC 用户名", "kind": "text", "placeholder": "homepage", "required": True},
            {"name": "password", "label": "RPC 密码", "kind": "secret", "required": True},
            {"name": "interfaceName", "label": "接口（可选）", "kind": "text", "placeholder": "eth0"},
        ],
        "notice": "需要按 Homepage 官方文档为 rpcd 创建只读 ACL 与专用用户。",
    },
    "minecraft": {
        "label": "Minecraft",
        "category": "游戏",
        "description": "Minecraft 服务器在线状态与玩家信息。",
        "docs": "https://gethomepage.dev/widgets/services/minecraft/",
        "icon": "minecraft.png",
        "test": "config",
        "fields": [
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "udp://192.0.2.50:25565", "required": True},
        ],
    },
    "gamedig": {
        "label": "GameDig",
        "category": "游戏",
        "description": "通过 GameDig 查询多种游戏服务器状态。",
        "docs": "https://gethomepage.dev/widgets/services/gamedig/",
        "icon": "mdi-gamepad-variant",
        "test": "config",
        "allowed_fields": ["status", "name", "map", "currentPlayers", "players", "maxPlayers", "bots", "ping"],
        "fields": [
            {"name": "serverType", "label": "GameDig Server Type", "kind": "text", "placeholder": "minecraft", "required": True},
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "udp://server:port", "required": True},
            {"name": "gameToken", "label": "Game Token（可选）", "kind": "secret"},
        ],
    },
    "glances": {
        "label": "Glances",
        "category": "监控",
        "description": "主机 CPU、内存、磁盘、网络、进程和传感器。",
        "docs": "https://gethomepage.dev/widgets/services/glances/",
        "icon": "glances.png",
        "test": "glances",
        "fields": [
            {"name": "url", "label": "Glances 地址", "kind": "text", "placeholder": "http://host:61208", "required": True},
            {"name": "username", "label": "用户名（可选）", "kind": "text"},
            {"name": "password", "label": "密码（可选）", "kind": "secret"},
            {"name": "version", "label": "Glances API 版本", "kind": "number", "placeholder": "4（Glances v4+）"},
            {"name": "metric", "label": "Metric", "kind": "text", "placeholder": "info / cpu / memory / network:eth0", "required": True},
            {"name": "chart", "label": "显示图表", "kind": "bool"},
            {"name": "refreshInterval", "label": "刷新间隔 ms", "kind": "number", "placeholder": "5000"},
            {"name": "pointsLimit", "label": "图表点数", "kind": "number", "placeholder": "15"},
        ],
    },
    "uptimekuma": {
        "label": "Uptime Kuma",
        "category": "监控",
        "description": "Uptime Kuma 状态页监控摘要。",
        "docs": "https://gethomepage.dev/widgets/services/uptimekuma/",
        "icon": "uptime-kuma.png",
        "test": "basic",
        "fields": [
            {"name": "url", "label": "Uptime Kuma 地址", "kind": "text", "placeholder": "http://uptime-kuma:3001", "required": True},
            {"name": "slug", "label": "Status Page Slug", "kind": "text", "placeholder": "status", "required": True},
        ],
    },
    "npm": {
        "label": "NGINX Proxy Manager",
        "category": "网络",
        "description": "NPM 代理主机、证书等统计。",
        "docs": "https://gethomepage.dev/widgets/services/nginx-proxy-manager/",
        "icon": "nginx-proxy-manager.png",
        "test": "basic",
        "fields": [
            {"name": "url", "label": "NPM 地址", "kind": "text", "placeholder": "http://npm:81", "required": True},
            {"name": "username", "label": "用户名", "kind": "text", "required": True},
            {"name": "password", "label": "密码", "kind": "secret", "required": True},
        ],
    },
    "grafana": {
        "label": "Grafana",
        "category": "监控",
        "description": "Grafana Dashboard、数据源与告警统计。",
        "docs": "https://gethomepage.dev/widgets/services/grafana/",
        "icon": "grafana.png",
        "test": "basic",
        "allowed_fields": ["dashboards", "datasources", "totalalerts", "alertstriggered"],
        "fields": [
            {"name": "url", "label": "Grafana 地址", "kind": "text", "placeholder": "http://grafana:3000", "required": True},
            {"name": "username", "label": "用户名", "kind": "text", "required": True},
            {"name": "password", "label": "密码", "kind": "secret", "required": True},
            {"name": "version", "label": "Widget 版本", "kind": "number", "placeholder": "2"},
        ],
    },
    "customapi": {
        "label": "Custom API",
        "category": "通用",
        "description": "把任意 JSON HTTP API 映射成 Homepage 指标卡片。",
        "docs": "https://gethomepage.dev/widgets/services/customapi/",
        "icon": "mdi-api",
        "test": "customapi",
        "fields": [
            {"name": "url", "label": "API 地址", "kind": "text", "placeholder": "https://service/api/status", "required": True},
            {"name": "method", "label": "HTTP 方法", "kind": "select", "options": ["GET", "POST"], "placeholder": "GET"},
            {"name": "headers", "label": "Headers", "kind": "yaml", "rows": 5, "placeholder": "Authorization: Bearer xxx"},
            {"name": "requestBody", "label": "Request Body", "kind": "yaml", "rows": 5, "placeholder": "query: status"},
            {"name": "mappings", "label": "Mappings", "kind": "yaml", "rows": 9, "placeholder": "- field: data.total\n  label: Total\n  format: number"},
            {"name": "refreshInterval", "label": "刷新间隔 ms", "kind": "number", "placeholder": "10000"},
        ],
    },
}


# Full Homepage Service Widget index.  The official documentation contains many more
# integrations than we can reasonably give a bespoke form on day one.  v0.3.2 keeps
# all official widget types searchable here, while ENHANCED_WIDGET_CATALOG provides
# richer forms / field pickers / deep tests for the widgets we actively model.
#
# tuple: (type id, display label, broad category)
OFFICIAL_WIDGET_INDEX: list[tuple[str, str, str]] = [
    ("adguard", "AdGuard Home", "网络"),
    ("apcups", "APC UPS Monitoring", "监控"),
    ("arcane", "Arcane", "基础设施"),
    ("argocd", "ArgoCD", "基础设施"),
    ("atsumeru", "Atsumeru", "媒体"),
    ("audiobookshelf", "Audiobookshelf", "媒体"),
    ("authentik", "Authentik", "安全"),
    ("autobrr", "Autobrr", "下载"),
    ("azuredevops", "Azure DevOps", "开发"),
    ("backrest", "Backrest", "存储"),
    ("bazarr", "Bazarr", "媒体"),
    ("booklore", "Booklore", "媒体"),
    ("beszel", "Beszel", "监控"),
    ("caddy", "Caddy", "网络"),
    ("calendar", "Calendar", "通用"),
    ("calibreweb", "Calibre-Web", "媒体"),
    ("changedetectionio", "ChangeDetection.io", "监控"),
    ("channelsdvrserver", "Channels DVR Server", "媒体"),
    ("checkmk", "Checkmk", "监控"),
    ("cloudflared", "Cloudflare Tunnels", "网络"),
    ("coinmarketcap", "Coin Market Cap", "通用"),
    ("crowdsec", "CrowdSec", "安全"),
    ("customapi", "Custom API", "通用"),
    ("deluge", "Deluge", "下载"),
    ("develancacheui", "DeveLanCacheUI", "网络"),
    ("diskstation", "Synology DiskStation", "存储"),
    ("dispatcharr", "Dispatcharr", "媒体"),
    ("dockhand", "Dockhand", "基础设施"),
    ("downloadstation", "Synology DownloadStation", "下载"),
    ("emby", "Emby", "媒体"),
    ("esphome", "ESPHome", "智能家居"),
    ("evcc", "EVCC", "智能家居"),
    ("filebrowser", "Filebrowser", "存储"),
    ("fileflows", "Fileflows", "媒体"),
    ("firefly", "Firefly III", "应用"),
    ("flood", "Flood", "下载"),
    ("freshrss", "FreshRSS", "应用"),
    ("frigate", "Frigate", "智能家居"),
    ("fritzbox", "FRITZ!Box", "网络"),
    ("gamedig", "GameDig", "游戏"),
    ("gatus", "Gatus", "监控"),
    ("ghostfolio", "Ghostfolio", "应用"),
    ("gitea", "Gitea", "开发"),
    ("gitlab", "GitLab", "开发"),
    ("glances", "Glances", "监控"),
    ("gluetun", "Gluetun", "网络"),
    ("gotify", "Gotify", "应用"),
    ("grafana", "Grafana", "监控"),
    ("hdhomerun", "HDHomeRun", "媒体"),
    ("headscale", "Headscale", "网络"),
    ("healthchecks", "Healthchecks", "监控"),
    ("karakeep", "Karakeep", "应用"),
    ("homeassistant", "Home Assistant", "智能家居"),
    ("homebox", "HomeBox", "应用"),
    ("homebridge", "Homebridge", "智能家居"),
    ("iframe", "iFrame", "通用"),
    ("immich", "Immich", "媒体"),
    ("jackett", "Jackett", "下载"),
    ("jdownloader", "JDownloader", "下载"),
    ("jellyfin", "Jellyfin", "媒体"),
    ("jellystat", "Jellystat", "媒体"),
    ("kavita", "Kavita", "媒体"),
    ("komga", "Komga", "媒体"),
    ("komodo", "Komodo", "基础设施"),
    ("kopia", "Kopia", "存储"),
    ("lidarr", "Lidarr", "媒体"),
    ("linkwarden", "Linkwarden", "应用"),
    ("lubelogger", "LubeLogger", "应用"),
    ("mastodon", "Mastodon", "应用"),
    ("mailcow", "Mailcow", "应用"),
    ("mealie", "Mealie", "应用"),
    ("medusa", "Medusa", "媒体"),
    ("mikrotik", "Mikrotik", "网络"),
    ("minecraft", "Minecraft", "游戏"),
    ("miniflux", "Miniflux", "应用"),
    ("mjpeg", "MJPEG", "通用"),
    ("moonraker", "Moonraker (Klipper)", "智能家居"),
    ("mylar", "Mylar3", "媒体"),
    ("myspeed", "MySpeed", "监控"),
    ("navidrome", "Navidrome", "媒体"),
    ("netdata", "Netdata", "监控"),
    ("netalertx", "NetAlertX", "网络"),
    ("nextcloud", "Nextcloud", "应用"),
    ("nextdns", "NextDNS", "网络"),
    ("npm", "NGINX Proxy Manager", "网络"),
    ("ntfy", "ntfy", "应用"),
    ("nzbget", "NZBGet", "下载"),
    ("octoprint", "OctoPrint", "智能家居"),
    ("omada", "Omada", "网络"),
    ("ombi", "Ombi", "媒体"),
    ("opendtu", "OpenDTU", "智能家居"),
    ("openmediavault", "OpenMediaVault", "存储"),
    ("opnsense", "OPNsense", "网络"),
    ("openwrt", "OpenWRT / ImmortalWRT", "网络"),
    ("pangolin", "Pangolin", "网络"),
    ("paperlessngx", "Paperless-ngx", "应用"),
    ("peanut", "PeaNUT", "监控"),
    ("pfsense", "pfSense", "网络"),
    ("photoprism", "PhotoPrism", "媒体"),
    ("pihole", "Pi-hole", "网络"),
    ("plantit", "Plant-it", "应用"),
    ("tautulli", "Tautulli (Plex)", "媒体"),
    ("plex", "Plex", "媒体"),
    ("portainer", "Portainer", "基础设施"),
    ("prometheus", "Prometheus", "监控"),
    ("prometheusmetric", "Prometheus Metric", "监控"),
    ("prowlarr", "Prowlarr", "下载"),
    ("proxmox", "Proxmox VE", "基础设施"),
    ("proxmoxbackupserver", "Proxmox Backup Server", "存储"),
    ("pterodactyl", "Pterodactyl", "游戏"),
    ("pyload", "PyLoad", "下载"),
    ("qbittorrent", "qBittorrent", "下载"),
    ("qnap", "QNAP", "存储"),
    ("radarr", "Radarr", "媒体"),
    ("readarr", "Readarr", "媒体"),
    ("romm", "ROMM", "游戏"),
    ("rutorrent", "ruTorrent", "下载"),
    ("sabnzbd", "SABnzbd", "下载"),
    ("scrutiny", "Scrutiny", "存储"),
    ("seerr", "Seerr", "媒体"),
    ("slskd", "Slskd", "下载"),
    ("sonarr", "Sonarr", "媒体"),
    ("sparkyfitness", "SparkyFitness", "应用"),
    ("speedtest", "Speedtest Tracker", "监控"),
    ("spoolman", "Spoolman", "智能家居"),
    ("stash", "Stash", "媒体"),
    ("stocks", "Stocks", "通用"),
    ("suwayomi", "Suwayomi", "媒体"),
    ("swagdashboard", "SWAG Dashboard", "网络"),
    ("strelaysrv", "Syncthing Relay Server", "网络"),
    ("tailscale", "Tailscale", "网络"),
    ("tandoor", "Tandoor", "应用"),
    ("technitium", "Technitium DNS Server", "网络"),
    ("tdarr", "Tdarr", "媒体"),
    ("traefik", "Traefik", "网络"),
    ("tracearr", "Tracearr", "媒体"),
    ("transmission", "Transmission", "下载"),
    ("trilium", "Trilium", "应用"),
    ("truenas", "TrueNAS", "存储"),
    ("tubearchivist", "Tube Archivist", "媒体"),
    ("unifi", "UniFi Controller", "网络"),
    ("unifi_drive", "UniFi Drive", "存储"),
    ("unmanic", "Unmanic", "媒体"),
    ("unraid", "Unraid", "存储"),
    ("uptimekuma", "Uptime Kuma", "监控"),
    ("uptimerobot", "UptimeRobot", "监控"),
    ("urbackup", "UrBackup", "存储"),
    ("vikunja", "Vikunja", "应用"),
    ("wallos", "Wallos", "应用"),
    ("watchtower", "Watchtower", "基础设施"),
    ("wgeasy", "Wg-Easy", "网络"),
    ("whatsupdocker", "What's Up Docker", "基础设施"),
    ("xteve", "xTeVe", "媒体"),
    ("yourspotify", "Your Spotify", "媒体"),
    ("zabbix", "Zabbix", "监控"),
]

# For the full index, a generic card intentionally does not pretend that Homepage
# Admin knows every field.  The service editor still accepts the widget type and the
# user can place the official options in the "Widget 其他配置" YAML mapping.  Enhanced
# definitions below replace the generic metadata for the types we model deeply.
_GENERIC_DOCS = "https://gethomepage.dev/widgets/services/"


def _build_catalog() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for type_id, label, category in OFFICIAL_WIDGET_INDEX:
        result[type_id] = {
            "label": label,
            "category": category,
            "description": "Homepage 官方原生 Service Widget；可直接使用，详细字段请参考官方文档。",
            "docs": _GENERIC_DOCS,
            "icon": "mdi-puzzle-outline",
            "test": "config",
            "allowed_fields": [],
            "fields": [],
            "enhanced": False,
        }

    for type_id, schema in ENHANCED_WIDGET_CATALOG.items():
        merged = dict(result.get(type_id, {}))
        merged.update(schema)
        merged["enhanced"] = True
        result[type_id] = merged
    return result


BUILTIN_WIDGET_CATALOG: dict[str, dict[str, Any]] = _build_catalog()
WIDGET_CATALOG: dict[str, dict[str, Any]] = copy.deepcopy(BUILTIN_WIDGET_CATALOG)
_SCHEMA_LOCK = threading.RLock()
_SCHEMA_STATE: dict[str, Any] = {
    "source": "bundled",
    "ref": getattr(settings, "widget_schema_ref", "dev"),
    "synced_at": None,
    "document_count": 0,
    "widget_count": len(WIDGET_CATALOG),
    "registry_count": 0,
    "error_count": 0,
    "errors": [],
    "last_error": "",
}
_MANUAL_SYNC_LOCK = threading.RLock()
_MANUAL_SYNC_STATE: dict[str, Any] = {
    "running": False,
    "stage": "idle",
    "message": "尚未启动手动同步。",
    "current": 0,
    "total": 0,
    "percent": 0,
    "started_at": None,
    "finished_at": None,
    "error": "",
    "result": {},
}


def _merge_field_lists(auto_fields: list[dict[str, Any]], enhanced_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    overrides = {str(field.get("name")): field for field in enhanced_fields if field.get("name")}
    seen: set[str] = set()
    for field in auto_fields:
        name = str(field.get("name", ""))
        merged = dict(field)
        if name in overrides:
            merged.update(overrides[name])
        result.append(merged)
        seen.add(name)
    for name, field in overrides.items():
        if name not in seen:
            result.append(dict(field))
    return result


def _merge_synced_catalog(synced: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    # Synced official schemas are primary. Bundled entries are retained as an offline fallback
    # and deep Admin enhancements are layered on top without hiding newly-added official fields.
    # A successful official sync is authoritative: removed/deprecated official types should
    # disappear instead of being kept forever by the old hand-maintained index. Deep Admin
    # integrations are the only local entries retained when the upstream docs temporarily omit one.
    result: dict[str, dict[str, Any]] = copy.deepcopy(synced)

    # Official YAML examples demonstrate valid configuration, but Homepage docs do not
    # generally declare every uncommented example property as mandatory. Older v0.3.x
    # caches inferred required=True from example presence, which produced false positives
    # such as Home Assistant `custom`. Keep auto-generated fields optional unless the
    # parser has an explicit required source; curated Admin enhancements below can still
    # mark known connection/auth fields as required.
    for schema in result.values():
        normalized_fields = []
        for field in list(schema.get("fields") or []):
            normalized = copy.deepcopy(field)
            if not normalized.get("required_source"):
                normalized["required"] = False
            normalized_fields.append(normalized)
        schema["fields"] = normalized_fields

    for type_id, enhanced in ENHANCED_WIDGET_CATALOG.items():
        base = copy.deepcopy(result.get(type_id, {}))
        auto_fields = list(base.get("fields") or [])
        manual_fields = list(enhanced.get("fields") or [])
        base.update({k: copy.deepcopy(v) for k, v in enhanced.items() if k != "fields"})
        base["fields"] = _merge_field_lists(auto_fields, manual_fields)
        if not base.get("allowed_fields"):
            base["allowed_fields"] = copy.deepcopy(enhanced.get("allowed_fields") or [])
        base["enhanced"] = True
        base["auto_generated"] = bool(synced.get(type_id))
        base["source_mode"] = "admin-enhanced"
        result[type_id] = base

    for type_id, schema in result.items():
        schema.setdefault("enhanced", bool(schema.get("fields")))
        schema.setdefault("auto_generated", type_id in synced)
        schema.setdefault("source_mode", "official-auto" if type_id in synced else "bundled-fallback")
    return dict(sorted(result.items()))


def _apply_catalog(catalog: dict[str, dict[str, Any]], state: dict[str, Any] | None = None) -> None:
    with _SCHEMA_LOCK:
        WIDGET_CATALOG.clear()
        WIDGET_CATALOG.update(catalog)
        if state:
            _SCHEMA_STATE.update(state)
        _SCHEMA_STATE["widget_count"] = len(WIDGET_CATALOG)


def _cache_path():
    return settings.data_dir / "widget-schema-cache.json"


def load_widget_schema_cache() -> bool:
    path = _cache_path()
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        widgets = payload.get("widgets")
        meta = payload.get("meta") or {}
        if not isinstance(widgets, dict) or len(widgets) < 20:
            return False
        _apply_catalog(_merge_synced_catalog(widgets), dict(meta))
        return True
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


def _write_cache(widgets: dict[str, dict[str, Any]], meta: dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"schema_version": 1, "meta": meta, "widgets": widgets}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def sync_widget_schema(
    *,
    force: bool = True,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    with _SCHEMA_LOCK:
        # Keep concurrent manual/automatic syncs from hammering GitHub.
        if not force and not widget_schema_sync_due():
            return widget_schema_status()
        try:
            if progress_callback:
                progress_callback({
                    "stage": "waiting",
                    "message": "正在准备官方 Widget Schema 同步…",
                    "current": 0,
                    "total": 0,
                    "percent": 1,
                })
            widgets, meta = fetch_official_widget_schemas(
                ref=getattr(settings, "widget_schema_ref", "dev"),
                timeout=float(getattr(settings, "widget_schema_timeout", 8.0)),
                workers=int(getattr(settings, "widget_schema_workers", 10)),
                progress=progress_callback,
            )
            if len(widgets) < 50:
                raise RuntimeError(f"官方 Widget Schema 数量异常：只发现 {len(widgets)} 个，已拒绝覆盖现有缓存。")
            if progress_callback:
                progress_callback({
                    "stage": "cache",
                    "message": "正在写入 /data Schema 缓存并刷新 Widget 中心…",
                    "current": len(widgets),
                    "total": len(widgets),
                    "percent": 99,
                })
            _write_cache(widgets, meta)
            meta["last_error"] = ""
            _apply_catalog(_merge_synced_catalog(widgets), meta)
            status = widget_schema_status()
            if progress_callback:
                progress_callback({
                    "stage": "complete",
                    "message": f"同步完成：{status.get('widget_count', 0)} 个 Widget，自动字段 {status.get('generated_field_count', 0)} 个。",
                    "current": status.get("widget_count", 0),
                    "total": status.get("widget_count", 0),
                    "percent": 100,
                })
            return status
        except Exception as exc:
            _SCHEMA_STATE["last_error"] = str(exc)
            raise


def _manual_sync_progress(payload: dict[str, Any]) -> None:
    with _MANUAL_SYNC_LOCK:
        _MANUAL_SYNC_STATE.update({
            "stage": str(payload.get("stage") or _MANUAL_SYNC_STATE.get("stage") or "working"),
            "message": str(payload.get("message") or "正在同步…"),
            "current": int(payload.get("current") or 0),
            "total": int(payload.get("total") or 0),
            "percent": max(0, min(100, int(payload.get("percent") or 0))),
        })


def _run_manual_widget_schema_sync() -> None:
    try:
        result = sync_widget_schema(force=True, progress_callback=_manual_sync_progress)
        with _MANUAL_SYNC_LOCK:
            _MANUAL_SYNC_STATE.update({
                "running": False,
                "stage": "complete",
                "message": f"同步完成：{result.get('widget_count', 0)} 个 Widget，自动字段 {result.get('generated_field_count', 0)} 个。",
                "percent": 100,
                "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "error": "",
                "result": {
                    "widget_count": result.get("widget_count", 0),
                    "generated_field_count": result.get("generated_field_count", 0),
                },
            })
    except Exception as exc:
        with _MANUAL_SYNC_LOCK:
            _MANUAL_SYNC_STATE.update({
                "running": False,
                "stage": "error",
                "message": f"同步失败：{exc}",
                "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "error": str(exc),
            })


def start_widget_schema_sync_job() -> dict[str, Any]:
    with _MANUAL_SYNC_LOCK:
        if _MANUAL_SYNC_STATE.get("running"):
            return copy.deepcopy(_MANUAL_SYNC_STATE)
        _MANUAL_SYNC_STATE.update({
            "running": True,
            "stage": "queued",
            "message": "同步任务已启动，正在连接 Homepage 官方仓库…",
            "current": 0,
            "total": 0,
            "percent": 0,
            "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "finished_at": None,
            "error": "",
            "result": {},
        })
        thread = threading.Thread(target=_run_manual_widget_schema_sync, name="widget-schema-manual-sync", daemon=True)
        thread.start()
        return copy.deepcopy(_MANUAL_SYNC_STATE)


def widget_schema_sync_job_status() -> dict[str, Any]:
    with _MANUAL_SYNC_LOCK:
        return copy.deepcopy(_MANUAL_SYNC_STATE)


def _parse_synced_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sync_preferences() -> dict[str, Any]:
    try:
        return store.widget_schema_sync_preferences()
    except Exception:
        return {
            "auto_sync": bool(getattr(settings, "widget_schema_auto_sync", True)),
            "mode": str(getattr(settings, "widget_schema_sync_mode", "interval") or "interval"),
            "interval_hours": max(1, int(getattr(settings, "widget_schema_sync_interval_hours", 24))),
            "daily_time": str(getattr(settings, "widget_schema_sync_time", "03:00") or "03:00"),
            "timezone": str(getattr(settings, "widget_schema_timezone", "UTC") or "UTC"),
            "custom": False,
        }


def _schedule_zone(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _daily_schedule_for(now_utc: datetime, prefs: dict[str, Any]) -> tuple[datetime, datetime]:
    zone = _schedule_zone(str(prefs.get("timezone") or "UTC"))
    local_now = now_utc.astimezone(zone)
    try:
        hour, minute = [int(part) for part in str(prefs.get("daily_time") or "03:00").split(":", 1)]
    except (TypeError, ValueError):
        hour, minute = 3, 0
    scheduled_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local_now, scheduled_local


def widget_schema_sync_due(now: datetime | None = None) -> bool:
    prefs = _sync_preferences()
    if not prefs.get("auto_sync", True):
        return False
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    synced_at = _parse_synced_at(_SCHEMA_STATE.get("synced_at"))
    if str(prefs.get("mode") or "interval") == "daily":
        local_now, scheduled_local = _daily_schedule_for(now_utc, prefs)
        if local_now < scheduled_local:
            return False
        if not synced_at:
            return True
        last_local = synced_at.astimezone(scheduled_local.tzinfo)
        return last_local < scheduled_local
    if not synced_at:
        return True
    hours = max(1, int(prefs.get("interval_hours") or 24))
    age = now_utc - synced_at.astimezone(timezone.utc)
    return age.total_seconds() >= hours * 3600


def widget_schema_next_sync_at(now: datetime | None = None) -> str | None:
    prefs = _sync_preferences()
    if not prefs.get("auto_sync", True):
        return None
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    synced_at = _parse_synced_at(_SCHEMA_STATE.get("synced_at"))
    if str(prefs.get("mode") or "interval") == "daily":
        local_now, scheduled_local = _daily_schedule_for(now_utc, prefs)
        if local_now < scheduled_local:
            next_local = scheduled_local
        elif not synced_at or synced_at.astimezone(scheduled_local.tzinfo) < scheduled_local:
            next_local = local_now
        else:
            next_local = scheduled_local + timedelta(days=1)
        return next_local.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    hours = max(1, int(prefs.get("interval_hours") or 24))
    if not synced_at:
        next_utc = now_utc
    else:
        next_utc = synced_at.astimezone(timezone.utc) + timedelta(hours=hours)
        if next_utc < now_utc:
            next_utc = now_utc
    return next_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def widget_schema_schedule_label() -> str:
    prefs = _sync_preferences()
    if not prefs.get("auto_sync", True):
        return "已关闭"
    if str(prefs.get("mode") or "interval") == "daily":
        return f"每天 {prefs.get('daily_time', '03:00')} · {prefs.get('timezone', 'UTC')}"
    return f"每 {max(1, int(prefs.get('interval_hours') or 24))} 小时"

def sync_widget_schema_if_due() -> dict[str, Any]:
    if not widget_schema_sync_due():
        return widget_schema_status()
    return sync_widget_schema(force=False)


def import_widget_schema_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Schema JSON 无效：{exc}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("widgets"), dict):
        widgets = payload["widgets"]
        meta = dict(payload.get("meta") or {})
    elif isinstance(payload, dict):
        widgets = payload
        meta = {}
    else:
        raise ValueError("Schema JSON 必须是 widgets 映射或包含 widgets 的缓存对象。")
    if len(widgets) < 20 or not all(isinstance(key, str) and isinstance(value, dict) for key, value in widgets.items()):
        raise ValueError("Schema 数量或格式异常，至少需要 20 个 Widget 映射。")
    meta.update({
        "source": "manual-import",
        "ref": str(meta.get("ref") or getattr(settings, "widget_schema_ref", "dev")),
        "synced_at": str(meta.get("synced_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        "widget_count": len(widgets),
        "last_error": "",
    })
    _write_cache(widgets, meta)
    _apply_catalog(_merge_synced_catalog(widgets), meta)
    return widget_schema_status()


def reset_widget_schema_cache() -> dict[str, Any]:
    path = _cache_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

    # Prefer the official snapshot bundled into the image by GitHub Actions.
    # This keeps every auto-generated form available even when runtime GitHub
    # access is temporarily unavailable. Fall back to the hand-maintained
    # directory only for development/source archives that have no snapshot.
    if load_bundled_widget_schema():
        _SCHEMA_STATE["last_error"] = ""
        return widget_schema_status()

    state = {
        "source": "bundled-fallback",
        "ref": getattr(settings, "widget_schema_ref", "dev"),
        "synced_at": None,
        "document_count": 0,
        "registry_count": 0,
        "error_count": 0,
        "errors": [],
        "last_error": "",
    }
    _apply_catalog(copy.deepcopy(BUILTIN_WIDGET_CATALOG), state)
    return widget_schema_status()


def widget_schema_status() -> dict[str, Any]:
    with _SCHEMA_LOCK:
        counts = {"official_auto": 0, "admin_enhanced": 0, "bundled_fallback": 0}
        generated_fields = 0
        for schema in WIDGET_CATALOG.values():
            mode = str(schema.get("source_mode", ""))
            if mode == "official-auto":
                counts["official_auto"] += 1
            elif mode == "admin-enhanced":
                counts["admin_enhanced"] += 1
            else:
                counts["bundled_fallback"] += 1
            if schema.get("auto_generated"):
                generated_fields += len(schema.get("fields") or [])
        prefs = _sync_preferences()
        return {
            **copy.deepcopy(_SCHEMA_STATE),
            **counts,
            "generated_field_count": generated_fields,
            "auto_sync": bool(prefs.get("auto_sync", True)),
            "sync_mode": str(prefs.get("mode", "interval")),
            "sync_interval_hours": int(prefs.get("interval_hours", 24)),
            "sync_time": str(prefs.get("daily_time", "03:00")),
            "sync_timezone": str(prefs.get("timezone", "UTC")),
            "sync_settings_custom": bool(prefs.get("custom", False)),
            "sync_schedule_label": widget_schema_schedule_label(),
            "next_sync_at": widget_schema_next_sync_at(),
            "cache_path": str(_cache_path()),
        }


def load_bundled_widget_schema() -> bool:
    path = Path(__file__).resolve().with_name("bundled_widget_schema.json")
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        widgets = payload.get("widgets")
        meta = payload.get("meta") or {}
        if not isinstance(widgets, dict) or len(widgets) < 20:
            return False
        bundled_meta = dict(meta)
        bundled_meta["source"] = "bundled-official-schema"
        _apply_catalog(_merge_synced_catalog(widgets), bundled_meta)
        return True
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


# Prefer the schema snapshot generated by GitHub Actions, then overlay a newer /data cache.
# If neither exists, installations remain fully usable with the hand-maintained offline index.
load_bundled_widget_schema()
load_widget_schema_cache()


def catalog_field_names(widget_type: str) -> set[str]:
    schema = WIDGET_CATALOG.get(widget_type, {})
    return {str(field["name"]) for field in schema.get("fields", [])} | {"fields"}


def catalog_secret_names(widget_type: str) -> set[str]:
    schema = WIDGET_CATALOG.get(widget_type, {})
    return {
        str(field["name"])
        for field in schema.get("fields", [])
        if field.get("kind") == "secret"
    }


def catalog_categories() -> list[str]:
    preferred = ["基础设施", "智能家居", "存储", "网络", "安全", "媒体", "下载", "监控", "游戏", "开发", "应用", "通用", "其他"]
    present = {str(schema.get("category", "其他")) for schema in WIDGET_CATALOG.values()}
    return [name for name in preferred if name in present] + sorted(present - set(preferred))


def public_catalog() -> dict[str, dict[str, Any]]:
    """Browser-safe catalog metadata (contains schemas, never user secrets)."""
    return WIDGET_CATALOG
