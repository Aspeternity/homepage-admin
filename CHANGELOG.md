# Changelog

## v0.2.4 - 2026-08-09

### 修复

- 修复“页面设置”在没有任何修改时点击保存会删除 `background.blur: ""`，导致 Homepage 背景从模糊变为清晰的问题。
- 页面设置真正无变化时不再重写 `settings.yaml`，也不再生成无意义备份；原 YAML 注释、显式空值和格式因此不会被无故改写。
- 修复背景滤镜数值为 `0` 时在表单中被当成空值的问题，`saturate: 0` / `brightness: 0` / `opacity: 0` 可正确显示与保存。
- 修复 Docker 导入向导推荐不存在的 `sh-lskypro` / `sh-komari` / `sh-moviepilot` 图标别名；分别改用 `mdi-image-multiple`、`mdi-server-network`、`mdi-movie-open`。

### 体验改进

- Docker 导入向导卡片预览新增 `mdi-*` 图标预览支持，并保留 URL / `sh-*` 图标预览和失败回退。
- 保留 v0.2.3 的字段对齐、智能分组、服务识别置信度和可配置备份保留数量。

## v0.2.3 - 2026-08-09

### 新功能与体验

- Docker 导入向导字段统一纵向网格，修复“图标”和“访问地址”等输入框不在同一水平线的问题。
- 备份回滚页新增自动保留数量设置，可在 1–500 组之间调整并持久化到 `/data/admin-settings.json`。
- Docker 导入默认策略升级为按服务类型智能推荐现有分组，也可固定到指定分组。
- 导入向导显示“识别类型 + 置信度”，并增强卡片图标预览。

## v0.2.2 - 2026-08-09

### 新功能

- Docker 发现升级为导入向导：容器识别 → 建议调整 → 卡片/YAML 实时预览 → 完整编辑。
- 自动推荐常见容器的服务说明，并继续复用图标、Widget、发布端口、Homepage Labels 和默认分组推断。
- 桌面端主题切换从左下角大按钮移动到右上角紧凑图标，并新增浅色 / 深色 / 跟随系统三种模式。
- 备份回滚页面支持删除单个备份以及清空全部备份。
- 备份列表显示文件数量和占用空间，删除动作记录审计日志。

### 兼容性与安全

- 保持 v0.2.1 的 `homepage-tools` + `homepage-docker-proxy` 架构，不需要重新迁移 Docker 网络。
- Docker 导入向导只预览非敏感字段；Widget API Key / Password / Token 仍只在完整编辑器中录入。
- 备份删除接口继续要求登录、CSRF 校验与前端确认。
- `BACKUP_LIMIT` 自动清理机制继续保留。

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
