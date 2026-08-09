# Changelog

## v0.2.0 - 2026-08-09

### 新功能

- 服务卡片、书签卡片继续支持跨分组拖动，并修正同组拖到末尾的排序逻辑。
- 服务分组、书签分组支持使用 `⋮⋮` 手柄直接拖动排序，并同步 `settings.yaml` 中的 layout 顺序。
- 顶部组件支持拖动排序。
- 新增常用 Homepage Service Widget 专属表单：Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox。
- Widget 密钥/密码留空会保留旧值，不会在普通编辑表单中回显。
- 高级 YAML 编辑器默认遮挡 `key`、`password`、`token`、`secret` 等敏感字段；保存遮挡后的 YAML 时自动恢复原值。
- 高级编辑器提供显式的“临时显示敏感值”入口，并在显示前进行确认提示。
- 新增 Docker 容器发现页面，可读取容器名称、镜像、运行状态、发布端口及非敏感 Homepage Labels，并一键预填服务表单。
- 新增专用 Docker 发现 sidecar。主后台不直接挂载 Docker socket；sidecar 只暴露容器列表读取接口。
- Docker 发现页可在空 `docker.yaml` 中一键创建 `local-docker` socket 配置。
- GHCR 工作流增加 concurrency，同一分支的新构建会取消旧构建，避免旧任务晚完成覆盖 `latest`。

### 安全改进

- Docker 发现代理过滤 password / secret / token / authorization / `.key` 类标签，避免敏感 Label 进入主后台。
- Docker 代理不提供容器启动、停止、删除、exec 或任意 Docker API 转发接口。
- 高级编辑器默认不再把 Jellyfin API Key 等凭据直接显示在页面源代码中。
- 服务额外 YAML、顶部组件 YAML、settings.yaml 的 `providers` 等敏感值也默认遮挡；占位符使用独立签名令牌，并阻止被移动到普通字段。

### 兼容性

- 保持 v0.1.x 的 YAML、备份和审计目录格式。
- 不要求迁移现有 Homepage 配置。
- 不启用 Docker sidecar 时，除“Docker 发现”外的管理功能仍可继续使用。
