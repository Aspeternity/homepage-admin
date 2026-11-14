"""Read-only compatibility findings. Never include configuration values in reports."""
from __future__ import annotations

from typing import Any, Iterator

from .homepage_compat import compare_versions
from .widget_schema_sync import display_fields_for_config


def service_widgets(value: Any, path: str = "services.yaml") -> Iterator[tuple[str, dict]]:
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from service_widgets(child, f"{path}[{index}]")
    elif isinstance(value, dict):
        if isinstance(value.get("widget"), dict):
            yield path + ".widget", value["widget"]
        for index, widget in enumerate(value.get("widgets", []) if isinstance(value.get("widgets"), list) else []):
            if isinstance(widget, dict):
                yield f"{path}.widgets[{index}]", widget
        for key, child in value.items():
            if key not in {"widget", "widgets"}:
                yield from service_widgets(child, f"{path}.{key}")


def inspect_configuration(configs: dict, version: str, catalog: dict, schema: dict) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(title: str, detail: str, level: str, href: str, label: str = "查看配置") -> None:
        findings.append(dict(title=title, detail=detail, level=level, href=href, label=label))

    ref = str(schema.get("ref") or "")
    if ref in {"dev", "main"}:
        add("Schema 来自开发分支", f"当前来源为 {ref}；建议匹配运行版本的稳定标签。", "warning", "/widget-schema", "管理 Schema")
    elif version and compare_versions(ref, version) not in (None, 0):
        add("Schema 与运行版本不同", f"Schema {ref}，当前 Homepage v{version}。同步前请核对目标版本。", "warning", "/widget-schema", "同步 Schema")
    if schema.get("error_count") or schema.get("last_error"):
        add("Schema 同步不完整", "部分官方文档未成功同步，当前保留可用缓存。", "warning", "/widget-schema", "查看同步状态")

    minimums = {"netbird": "2.7.0", "bookorbit": "2.5.0", "qui": "2.5.0", "feed": "2.5.0"}
    widgets = list(service_widgets(configs.get("services.yaml", [])))
    for path, widget in widgets:
        widget_type = str(widget.get("type") or "")
        minimum = minimums.get(widget_type)
        if minimum and compare_versions(version, minimum) == -1:
            add(f"{widget_type} 需要更新的 Homepage", f"{path}：需要 Homepage v{minimum} 或更新版本。", "warning", "/yaml/services.yaml")
        definition = catalog.get(widget_type)
        if definition:
            allowed = display_fields_for_config(definition, widget)
            fields = widget.get("fields")
            invalid = [str(v) for v in fields if v not in allowed] if allowed and isinstance(fields, list) else []
            if invalid:
                add(f"{widget_type} 展示字段需要核对", f"{path}：有 {len(invalid)} 个字段不在当前版本或模式的文档列表中；配置保持原样。", "warning", "/yaml/services.yaml")
        elif widget_type:
            add("Widget 尚未收录", f"{path}：请同步官方 Schema 或使用高级编辑。", "info", "/widget-schema", "管理 Schema")
        if widget_type == "customapi" and widget.get("highlight"):
            add("Custom API 不支持 block highlighting", f"{path}：请核对 highlight 配置。", "warning", "/yaml/services.yaml")

    settings = configs.get("settings.yaml") or {}
    if isinstance(settings, dict):
        for name in ("cardStyle", "blockStyle", "font"):
            if name in settings and compare_versions(version, "2.5.0") == -1:
                add(f"{name} 需要 Homepage v2.5.0+", f"settings.yaml：当前运行版本尚未提供此选项。", "warning", "/settings")
        quicklaunch = settings.get("quicklaunch") or {}
        if isinstance(quicklaunch, dict) and "disabled" in quicklaunch and compare_versions(version, "2.8.0") == -1:
            add("关闭 Quick Launch 需要 Homepage v2.8.0+", "settings.yaml → quicklaunch.disabled：升级后生效。", "warning", "/settings#settings-quicklaunch")
    info_widgets = configs.get("widgets.yaml") or []
    if isinstance(info_widgets, list) and any(isinstance(item, dict) and "customapi" in item for item in info_widgets) and compare_versions(version, "2.5.0") == -1:
        add("顶部 Custom API 需要 Homepage v2.5.0+", "widgets.yaml：当前运行版本尚未提供此顶部组件。", "warning", "/widgets")
    if not version:
        add("运行版本尚未识别", "已检查配置结构；版本相关判断需要先识别或手动指定 Homepage 版本。", "info", "#compat-detection", "调整检测方式")
    if not findings:
        add("当前配置未命中已收录的兼容问题", f"已检查 {len(widgets)} 个 Service Widget、页面设置与顶部组件。第三方服务 API 的实际连通性请在编辑器中测试。", "success", "/services", "查看服务")
    return findings
