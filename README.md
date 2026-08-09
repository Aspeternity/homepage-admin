# Homepage Admin v0.2.4

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

> v0.2.4 的重点：**修复页面设置“无修改保存”破坏背景滤镜、修正无效 Docker 图标推荐，并继续强化导入向导与备份策略。**

## v0.2.4 新增 / 修复

### 页面设置改为更安全的无损保存

- 修复 `settings.yaml` 中 `background.blur: ""` 被网页表单误当成“空值并删除”的问题。
- Homepage 官方将 `blur: ""` 作为有效背景滤镜值；v0.2.4 会在未修改时保留这个显式空字符串。
- 如果页面设置没有任何实际变化，点击“保存设置”将不再重写 `settings.yaml`，也不会生成无意义的新备份。
- `saturate: 0`、`brightness: 0`、`opacity: 0` 等合法数值不会再因为 Python/Jinja 的假值判断而显示为空或被删除。
- 背景、快速启动等对象中的未知/额外字段继续保留。

### Docker 导入图标推荐修正

- 不再为 Lsky Pro 推荐不存在的 `sh-lskypro`。
- Lsky Pro 改用已验证存在的 `mdi-image-multiple`。
- Komari 改用 `mdi-server-network`。
- MoviePilot 改用 `mdi-movie-open`。
- 向导卡片预览新增 `mdi-*` 图标预览支持；URL / `sh-*` / `mdi-*` 都可预览，加载失败会回退到文字占位。

### 延续 v0.2.3 的体验优化

- Docker 导入向导字段保持严格纵向对齐。
- 自动识别服务类型与置信度，并按类型智能推荐现有 Homepage 分组。
- 备份回滚页可配置自动保留数量（1–500 组），设置持久化到 `/data/admin-settings.json`。
- 仍支持单个删除、清空全部、回滚、自动清理旧备份。

## Docker 安全架构

延续 v0.2.1 以来的共享只读代理结构：

```text
/var/run/docker.sock
        │
        ▼
homepage-docker-proxy
  CONTAINERS=1
  PING=1
  SERVICES=1
  TASKS=1
  POST=0
        │
        ├─────────> Homepage
        │           docker.yaml -> homepage-docker-proxy:2375
        │
        └─────────> Homepage Admin
                    Docker 发现 / 导入向导
```

`homepage-docker-proxy` 不映射宿主机端口，只加入共享 `homepage-tools` 网络。

## 核心功能

- 服务 / 书签 / 分组拖拽排序
- 顶部组件拖拽排序
- Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox 专属 Widget 表单
- API Key / Token / Password 遮挡与保留
- 高级 YAML 敏感值安全占位符
- Docker 容器发现、导入向导、已添加识别、系统组件隐藏、端口去重
- 智能服务类型识别、分组推荐、卡片 / YAML 实时预览
- 自动备份、可配置保留数量、回滚、删除、YAML 校验、原子写入、审计日志
- 右上角浅色 / 深色 / 跟随系统主题菜单
- GitHub Actions 自动测试并发布 `amd64` / `arm64` GHCR 镜像

## 当前部署参数

```text
镜像: ghcr.io/aspeternity/homepage-admin:latest
Homepage 配置: /opt/docker/HomePage/data/config
Admin 数据: /opt/docker/homepage-admin/data
Admin 端口: 3001
Docker VM: 10.10.1.11
Admin UID:GID: 1000:1000
共享 Docker 网络: homepage-tools
```

从 v0.2.3 升级请阅读：

```text
UPGRADE_V0.2.4_ZH.md
```

## 官方 Homepage 对应配置

Homepage Admin 仍以官方 YAML 作为唯一数据源：

- `services.yaml`
- `bookmarks.yaml`
- `settings.yaml`
- `widgets.yaml`
- `docker.yaml`
- `proxmox.yaml`
- `kubernetes.yaml`
- `custom.css`
- `custom.js`

## 本地开发

```bash
cp .env.example .env
docker compose up -d --build
```

测试：

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
