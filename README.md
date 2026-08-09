# Homepage Admin v0.2.0

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

> 项目目标：保留 Homepage 的完整配置能力，同时把日常增删改、排序、Widget 配置、备份和 Docker 服务发现变成图形化操作。

## v0.2.0 重点

- 服务 / 书签卡片跨分组拖动
- 服务 / 书签分组拖动排序
- 顶部组件拖动排序
- Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox 专属 Widget 表单
- Widget API Key / Password 不回显，留空自动保留
- 高级 YAML 默认隐藏敏感字段，并能安全保存占位符
- Docker 容器发现与一键预填服务
- 专用 Docker 发现 sidecar，主后台不直接接触 Docker socket
- 自动备份、回滚、YAML 校验、原子写入、审计日志
- GitHub Actions 自动测试并发布 `amd64` / `arm64` GHCR 镜像

## 对应 Homepage 官方配置

Homepage Admin 仍以 Homepage 官方文件作为唯一数据源：

- `services.yaml`：服务、状态监控、Docker 关联、Service Widget
- `bookmarks.yaml`：书签
- `settings.yaml`：页面设置、背景和 layout
- `widgets.yaml`：顶部 Information Widgets
- `docker.yaml`：Homepage Docker server
- `proxmox.yaml`、`kubernetes.yaml`、`custom.css`、`custom.js`：高级编辑

官方文档：

- https://gethomepage.dev/configs/
- https://gethomepage.dev/configs/services/
- https://gethomepage.dev/configs/docker/
- https://gethomepage.dev/widgets/services/

## v0.2.0 Docker 发现架构

```text
Docker Engine
    │
    │ /var/run/docker.sock
    ▼
homepage-admin-docker-proxy
    │ 仅暴露 GET /api/containers
    ▼
homepage-admin
    │
    ├── /config -> Homepage 的真实配置目录
    └── /data   -> Admin 备份与审计数据
```

主 `homepage-admin` 容器不挂载 Docker socket。`docker-proxy` sidecar 只返回容器列表所需的有限元数据，并过滤常见敏感 Label。

注意：任何能访问 Docker socket 的进程都属于高权限组件。sidecar 通过最小接口缩小暴露面，但仍应只运行在可信主机上，并且不要给它映射宿主机端口。

## 你的 Portainer / Docker VM 部署

项目内的 `docker-compose.ghcr.yml` 已按当前环境预设：

```text
GHCR: ghcr.io/aspeternity/homepage-admin:latest
Homepage config: /opt/docker/HomePage/data/config
Admin data: /opt/docker/homepage-admin/data
Admin port: 3001
Docker public host: 10.10.1.11
UID:GID: 1000:1000
```

首次升级 v0.2.0 时，需要把原来只有一个 service 的 Stack 替换成 v0.2.0 的两 service Compose：

- `homepage-admin`
- `docker-proxy`

### 必填环境变量

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你的后台密码
SESSION_SECRET=至少32位随机字符串
HOMEPAGE_URL=http://10.10.1.11:3000
```

推荐后续把 `ADMIN_PASSWORD` 改成 `ADMIN_PASSWORD_HASH`。

## Docker 发现如何使用

1. 左侧打开“Docker 发现”。
2. 如果 `docker.yaml` 还是空的，可以点击“创建 local-docker”。
3. 确认 Homepage 本体已经挂载 `/var/run/docker.sock`。你的当前 Homepage 部署已满足这一点。
4. 找到容器，点击“添加到 Homepage”。
5. 后台会尝试预填容器名、图标、端口 URL、Homepage Labels 和可识别的 Widget 类型。
6. 检查域名 / URL 和凭据后保存。

Homepage Admin 不会自动猜测你的反向代理域名，因此发现出的 `http://10.10.1.11:端口` 只是建议值，可改成实际域名。

## Widget 专属表单

v0.2.0 首批覆盖：

- Jellyfin
- qBittorrent
- Transmission
- Minecraft
- Home Assistant
- Portainer
- Proxmox

未覆盖的 Widget 仍然可以填写 Widget 类型，并使用“Widget 其他配置（YAML 映射）”。已有未知字段会被保留。

## 敏感字段保护

普通 Widget 表单不会把已保存的 key/password/token 回显到 HTML。编辑时留空会保留原值。服务额外 YAML、顶部组件 YAML、settings.yaml 的额外字段（包括 `providers`）也会自动遮挡已识别的敏感值。

高级 YAML 编辑器默认把敏感值替换成每个值独立的不可逆占位符，例如：

```text
__HOMEPAGE_ADMIN_SECRET_1a2b3c4d5e6f7890__
```

保存时会从原文件恢复占位符对应的真实值。占位符可随条目排序一起移动，但不能被复制到普通非敏感字段；检测到异常位置或无法对应原值时会拒绝保存。需要真正修改凭据时，可点击“临时显示敏感值”，或者优先使用 Widget 专属表单。

## 备份与写入

每次写入前：

1. 获取文件锁
2. 备份旧文件
3. 校验 YAML
4. 写入临时文件
5. 原子替换正式文件
6. 写审计日志

备份目录：`/data/backups`

## 本地开发

```bash
cp .env.example .env
docker compose up -d --build
```

运行测试：

```bash
pip install -r requirements-dev.txt
pytest -q
```

## 更新

GitHub `main` 分支有新提交后，Actions 会自动测试并构建：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

Portainer 中重新拉取镜像并 Recreate / Update Stack 即可。

发布 Git Tag（例如 `v0.2.0`）后，工作流还会生成对应的语义版本镜像标签。
