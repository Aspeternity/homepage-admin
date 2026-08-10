from __future__ import annotations

from typing import Any

INFO_WIDGET_CATALOG: list[dict[str, Any]] = [
    {
        "id": "greeting",
        "title": "Greeting",
        "title_zh": "问候文字",
        "category": "基础",
        "description": "在页头显示一段简单文字。",
        "doc": "https://gethomepage.dev/widgets/info/greeting/",
        "right_aligned": False,
    },
    {
        "id": "datetime",
        "title": "Date & Time",
        "title_zh": "日期与时间",
        "category": "基础",
        "description": "显示本地化日期和时间，并支持 Intl.DateTimeFormat。",
        "doc": "https://gethomepage.dev/widgets/info/datetime/",
        "right_aligned": True,
    },
    {
        "id": "logo",
        "title": "Logo",
        "title_zh": "Logo",
        "category": "基础",
        "description": "显示 Homepage Logo 或自定义图标，可附加链接。",
        "doc": "https://gethomepage.dev/widgets/info/logo/",
        "right_aligned": False,
    },
    {
        "id": "search",
        "title": "Search",
        "title_zh": "搜索",
        "category": "工具",
        "description": "页头搜索框，支持常见搜索引擎、多个 Provider 和自定义搜索。",
        "doc": "https://gethomepage.dev/widgets/info/search/",
        "right_aligned": True,
    },
    {
        "id": "resources",
        "title": "Resources",
        "title_zh": "系统资源",
        "category": "监控",
        "description": "显示 Homepage 容器自身的 CPU、内存、磁盘、网络和温度信息。",
        "doc": "https://gethomepage.dev/widgets/info/resources/",
        "right_aligned": False,
    },
    {
        "id": "glances",
        "title": "Glances",
        "title_zh": "Glances 资源",
        "category": "监控",
        "description": "通过 Glances Web API 显示主机或远程机器资源。",
        "doc": "https://gethomepage.dev/widgets/info/glances/",
        "right_aligned": False,
    },
    {
        "id": "openmeteo",
        "title": "Open-Meteo",
        "title_zh": "Open-Meteo 天气",
        "category": "天气",
        "description": "无需注册的天气组件；可使用坐标或浏览器当前位置。",
        "doc": "https://gethomepage.dev/widgets/info/openmeteo/",
        "right_aligned": True,
    },
    {
        "id": "openweathermap",
        "title": "OpenWeatherMap",
        "title_zh": "OpenWeatherMap 天气",
        "category": "天气",
        "description": "使用 OpenWeatherMap One Call API 显示天气。",
        "doc": "https://gethomepage.dev/widgets/info/openweathermap/",
        "right_aligned": True,
    },
    {
        "id": "stocks",
        "title": "Stocks",
        "title_zh": "股票",
        "category": "数据",
        "description": "通过 Finnhub 显示最多 8 个股票代码的价格与日内变化。",
        "doc": "https://gethomepage.dev/widgets/info/stocks/",
        "right_aligned": False,
    },
    {
        "id": "unifi_console",
        "title": "UniFi Controller",
        "title_zh": "UniFi 控制器",
        "category": "网络",
        "description": "显示 UniFi Network Controller 的总体连接状态。",
        "doc": "https://gethomepage.dev/widgets/info/unifi_controller/",
        "right_aligned": False,
    },
    {
        "id": "kubernetes",
        "title": "Kubernetes",
        "title_zh": "Kubernetes 资源",
        "category": "集群",
        "description": "显示 Kubernetes 集群及各节点的 CPU / 内存资源。",
        "doc": "https://gethomepage.dev/widgets/info/kubernetes/",
        "right_aligned": False,
    },
    {
        "id": "longhorn",
        "title": "Longhorn",
        "title_zh": "Longhorn 存储",
        "category": "集群",
        "description": "显示 Longhorn 集群存储利用率及节点指标。",
        "doc": "https://gethomepage.dev/widgets/info/longhorn/",
        "right_aligned": False,
    },
]

INFO_WIDGET_BY_ID = {item["id"]: item for item in INFO_WIDGET_CATALOG}
INFO_WIDGET_TYPES = tuple(INFO_WIDGET_BY_ID)
TEXT_SIZES = ("4xl", "3xl", "2xl", "xl", "md", "sm", "xs")
SEARCH_PROVIDERS = ("google", "duckduckgo", "bing", "baidu", "brave")
TARGETS = ("_blank", "_self", "_parent", "_top")

KNOWN_FIELDS: dict[str, set[str]] = {
    "greeting": {"text", "text_size", "href", "target"},
    "datetime": {"text_size", "locale", "format", "href", "target"},
    "logo": {"icon", "href", "target"},
    "search": {"provider", "focus", "showSearchSuggestions", "target", "url", "suggestionUrl"},
    "resources": {
        "label", "cpu", "memory", "disk", "cputemp", "tempmin", "tempmax", "uptime", "units",
        "refresh", "diskUnits", "network", "expanded",
    },
    "glances": {
        "url", "username", "password", "version", "cpu", "mem", "cputemp", "cpuSensorLabel", "unit",
        "uptime", "disk", "diskUnits", "expanded", "label",
    },
    "openmeteo": {"label", "latitude", "longitude", "timezone", "units", "cache", "format"},
    "openweathermap": {"label", "latitude", "longitude", "units", "provider", "apiKey", "cache", "format"},
    "stocks": {"provider", "color", "cache", "watchlist"},
    "unifi_console": {"url", "site", "username", "password", "key"},
    "kubernetes": {"cluster", "nodes"},
    "longhorn": {"expanded", "total", "labels", "nodes", "include"},
}


def catalog_categories() -> list[str]:
    return sorted({str(item["category"]) for item in INFO_WIDGET_CATALOG})


def public_catalog(existing_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    counts = existing_counts or {}
    return [{**item, "count": int(counts.get(str(item["id"]), 0))} for item in INFO_WIDGET_CATALOG]
