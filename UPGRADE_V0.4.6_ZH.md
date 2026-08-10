# Homepage Admin v0.4.6 升级说明

v0.4.6 集中优化“页面设置”，目标是让日常 `settings.yaml` 配置尽量不再依赖手写 YAML，同时继续保留官方未来字段的兼容能力。

## 页面设置新版结构

页面现在按以下分区组织：

1. 基础信息：标题、语言、说明、Favicon、Start URL、Base URL。
2. 外观与背景：主题、官方色板、Header Style、Icon Style、Card Blur、Bookmark Style、背景图片与滤镜。
3. 页面行为：链接目标、状态样式、全宽、等高、折叠、统计、错误显示、版本/更新检查、禁止索引及最大列数。
4. Quick Launch：官方 provider、搜索描述、联网搜索、建议、URL 检测、移动按钮和 Custom Provider。
5. 分组布局：自动读取 services.yaml 与 bookmarks.yaml 分组，支持拖动调整 layout 顺序。
6. 高级 YAML：Providers、PWA、blockHighlights、instanceName、logpath 以及未来字段继续在此保留。

## 重要兼容行为

- `background.blur: ""` 仍视为明确有效配置，可在表单中直接选择“无模糊”。
- 未配置到 `layout:` 的服务/书签分组只作为发现结果展示；保持默认直接保存不会自动写入空布局。
- 现有 `quicklaunch`、`background`、布局中的未知字段继续原样保留。
- Providers/API Key 等敏感值在页面与 Diff 中继续掩码，保存时恢复原值。
- 保存前新增 Diff 预览；真正确认后才写入 `settings.yaml` 并创建备份。

## 升级

解压 `homepage-admin-v0.4.6-web-upload.zip`，覆盖上传仓库普通文件。Web Upload 包不包含 `.github`。

Commit 建议：

```text
Release v0.4.6
```

Actions 绿色后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.4.6`。
