# Homepage Admin v0.2.1

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

> v0.2.1 的重点是：**黑/白主题切换、Docker 发现体验优化，以及把 Homepage 和 Admin 统一到一个只读 Docker Socket Proxy**。

## v0.2.1 新增 / 修复

- 新增 **深色 / 浅色主题切换**，主题偏好保存在浏览器 `localStorage`，刷新后保持。
- 登录页、桌面侧栏、移动端顶部都可以切换主题。
- Docker 端口映射去重：IPv4 / IPv6 返回的相同 `hostPort -> containerPort` 只显示一次。
- Docker 发现使用容器名大小写不敏感匹配，已经写入 `services.yaml` 的容器会明确显示“已添加”。
- 已添加容器会显示对应的 Homepage 分组 / 服务名。
- 默认隐藏 `homepage-docker-proxy` 等内部基础设施容器，可手动显示。
- `homepage-admin` 和 Homepage 本体会显示角色标签。
- Docker 导入页增加“默认导入分组”选择，并在当前浏览器记住选择，避免总是落到第一个 `Widgets` 分组。
- Docker 页显示只读代理健康状态。
- `docker.yaml` 为空时，新建的 `local-docker` 默认使用只读代理：

  ```yaml
  local-docker:
    host: homepage-docker-proxy
    port: 2375
  ```

- 如果当前仍是 `socket: /var/run/docker.sock`，Docker 页提供“一键切换为只读代理”。
- v0.2.1 的 Compose 改用 Homepage 官方文档推荐的 `ghcr.io/tecnativa/docker-socket-proxy:latest`，`POST=0`，不向宿主机 / 局域网暴露 2375。
- 保留 v0.2.0 自定义发现代理代码作为兼容路径，但新部署不再使用它。

## Docker 安全架构

v0.2.1 推荐结构：

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
        │           docker.yaml -> host: homepage-docker-proxy / port: 2375
        │
        └─────────> Homepage Admin
                    Docker 发现
```

`homepage-docker-proxy` 不映射宿主机端口，只加入共享的 `homepage-tools` Docker 网络。

Homepage 官方文档同样推荐 Docker Socket Proxy，而不是直接把 `/var/run/docker.sock` 交给 Homepage。

## 仍然支持的核心功能

- 服务 / 书签 / 分组拖拽排序
- 顶部组件拖拽排序
- Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox 专属 Widget 表单
- API Key / Token / Password 遮挡与保留
- 高级 YAML 敏感值安全占位符
- Docker 容器发现与一键预填
- 自动备份、回滚、YAML 校验、原子写入、审计日志
- GitHub Actions 自动测试并发布 `amd64` / `arm64` GHCR 镜像

## 你的当前部署参数

项目中的 `docker-compose.ghcr.yml` / `docker-compose.portainer.yml` 已按当前环境预设：

```text
镜像: ghcr.io/aspeternity/homepage-admin:latest
Homepage 配置: /opt/docker/HomePage/data/config
Admin 数据: /opt/docker/homepage-admin/data
Admin 端口: 3001
Docker VM: 10.10.1.11
Admin UID:GID: 1000:1000
共享 Docker 网络: homepage-tools
```

从 v0.2.0 升级到 v0.2.1 请优先阅读：

```text
UPGRADE_V0.2.1_ZH.md
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

官方文档：

- https://gethomepage.dev/configs/
- https://gethomepage.dev/configs/docker/
- https://gethomepage.dev/widgets/services/

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
