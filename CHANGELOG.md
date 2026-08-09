# Changelog

## v0.2.1 - 2026-08-09

### 新功能

- 新增深色 / 浅色主题切换；登录页、桌面侧栏、移动端均可切换，并用浏览器 localStorage 记住偏好。
- Docker 发现页增加默认导入分组选择，避免无 Label 容器总是落到第一个 Widgets 分组。
- Docker 发现页增加共享只读代理状态、Socket 模式提示和一键迁移按钮。
- 已配置容器显示对应 Homepage 分组与服务名，并使用大小写不敏感的容器名匹配。
- Homepage 本体、Homepage Admin、Docker Proxy 增加角色标签；内部 Proxy 默认隐藏，可手动显示。

### 修复与体验

- 去重 Docker IPv4 / IPv6 导致的重复端口映射。
- 新增 Lsky-Pro / MkDocs 图标推断。
- 新建 docker.yaml 不再默认写入直接 socket，而是写入 `homepage-docker-proxy:2375`。

### 安全改进

- 新 Compose 改用 Homepage 官方文档推荐的 `ghcr.io/tecnativa/docker-socket-proxy:latest`。
- `CONTAINERS=1`、`PING=1`、`SERVICES=1`、`TASKS=1`、`POST=0`，不映射宿主机 2375 端口。
- Homepage 和 Homepage Admin 通过外部 `homepage-tools` 网络共享代理，Homepage 可移除直接 Docker Socket 挂载并恢复原 PGID。
- Admin 对原始 Docker API 返回的 Labels 继续进行敏感字段过滤后才进入页面数据。

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
