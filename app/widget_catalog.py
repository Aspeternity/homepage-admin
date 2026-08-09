from __future__ import annotations

from typing import Any

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
            {"name": "custom", "label": "自定义状态 / 模板", "kind": "yaml", "rows": 7, "placeholder": "- state: sensor.total_power\n- template: '{{ states.light|selectattr(\"state\",\"equalto\",\"on\")|list|length }}'"},
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
            {"name": "url", "label": "服务器地址", "kind": "text", "placeholder": "udp://10.10.1.254:25565", "required": True},
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
# integrations than we can reasonably give a bespoke form on day one.  v0.3.1 keeps
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


WIDGET_CATALOG: dict[str, dict[str, Any]] = _build_catalog()


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
