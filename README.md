<p align="center">
  <img src="docs/assets/homepage-admin.png" width="160" alt="Homepage Admin Logo">
</p>

<h1 align="center">Homepage Admin</h1>

<p align="center">
  一个面向 <a href="https://gethomepage.dev/">Homepage</a> 的可视化配置后台。<br>
  直接管理官方 YAML 配置，不修改 Homepage 本体，不引入额外配置数据库。
</p>

<p align="center">
  <a href="https://github.com/Aspeternity/homepage-admin/actions/workflows/docker-publish.yml"><img src="https://github.com/Aspeternity/homepage-admin/actions/workflows/docker-publish.yml/badge.svg?branch=main" alt="Build"></a>
  <a href="https://github.com/Aspeternity/homepage-admin/releases"><img src="https://img.shields.io/github/v/release/Aspeternity/homepage-admin?display_name=tag&sort=semver" alt="Release"></a>
  <a href="https://github.com/Aspeternity/homepage-admin/pkgs/container/homepage-admin"><img src="https://img.shields.io/badge/GHCR-homepage--admin-2496ED?logo=docker&logoColor=white" alt="GHCR"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Aspeternity/homepage-admin" alt="License"></a>
</p>

> [!NOTE]
> Homepage Admin 是社区项目，不是 Homepage 官方项目，与 `gethomepage/homepage` 没有隶属关系。

## 项目简介

Homepage Admin 与 Homepage **共享同一个配置目录**，直接读取和写入 Homepage 官方 YAML。Homepage 配置始终是唯一事实来源，因此可以随时在可视化后台和手工 YAML 编辑之间切换。

它适合已经使用 Homepage、但希望更方便地管理服务、Widget、书签、页面设置、Docker / Proxmox 发现和备份恢复的用户。

## 主要功能

| 模块 | 能力 |
| --- | --- |
| 服务管理 | 可视化管理 `services.yaml`，分组、排序、多 Widget、连接测试、保存前 Diff |
| Widget 中心 | 同步 Homepage 官方 Service Widget Schema，动态生成表单 |
| 书签管理 | 可视化管理 `bookmarks.yaml`，支持分组与拖拽排序 |
| 页面设置 | 管理 `settings.yaml` 的主题、背景、Quick Launch、布局等 |
| 顶部组件 | 管理 `widgets.yaml`，提供 Information Widget 专属表单 |
| Docker 发现 | 多 Docker 主机、容器发现、导入向导、`server + container` 绑定 |
| Proxmox 发现 | 多节点聚合、QEMU/LXC 发现、已有服务关联、节点管理 |
| 高级编辑 | 直接编辑 YAML / CSS / JS，并在保存前校验与预览 Diff |
| 备份中心 | 自动备份、完整快照、保护、ZIP 导出、单文件/整组恢复 |
| 安全 | Session、CSRF、登录限流、Secret 掩码、原子写入、文件锁、审计日志 |

## 工作方式

```text
Homepage Admin
      │
      ├── /config ──────> Homepage 配置目录
      │                   ├── services.yaml
      │                   ├── bookmarks.yaml
      │                   ├── settings.yaml
      │                   ├── widgets.yaml
      │                   ├── docker.yaml
      │                   ├── proxmox.yaml
      │                   └── ...
      │
      ├── /data ────────> Admin 数据
      │                   ├── 备份
      │                   ├── 审计日志
      │                   └── 管理偏好
      │
      └── 可选网络 API ─> Docker / Proxmox 发现
```

**Homepage Admin 的核心依赖只有 Homepage 配置目录。** 运行 Admin 不要求 Docker Socket、不要求 Docker Socket Proxy，也不要求与 Homepage 或 Proxy 创建共享 Docker Network。

---

# 快速部署

## Docker Compose（推荐）

### 1. 创建目录

把下面的 Homepage 配置目录替换成你的实际路径：

```bash
mkdir -p /opt/docker/homepage-admin/data
mkdir -p /opt/docker/homepage-admin
cd /opt/docker/homepage-admin
```

### 2. 创建 `.env`

生成 Session Secret：

```bash
openssl rand -hex 32
```

创建 `.env`：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=请替换为强密码
SESSION_SECRET=请粘贴上一步生成的随机字符串

PUID=1000
PGID=1000
TZ=Asia/Shanghai

HOMEPAGE_URL=https://homepage.example.com
HOMEPAGE_HOST_CONFIG_DIR=/opt/docker/HomePage/data/config
HOMEPAGE_ADMIN_DATA_DIR=/opt/docker/homepage-admin/data

ADMIN_COOKIE_SECURE=false
ADMIN_ALLOWED_HOSTS=*
```

> `PUID/PGID` 对应的用户必须对 Homepage 配置目录与 Admin 数据目录具有读写权限。通过 HTTPS 反向代理访问时，建议将 `ADMIN_COOKIE_SECURE` 改为 `true`。

### 3. 创建 `compose.yml`

```yaml
services:
  homepage-admin:
    image: ghcr.io/aspeternity/homepage-admin:latest
    pull_policy: always
    container_name: homepage-admin
    restart: unless-stopped
    user: "${PUID:-1000}:${PGID:-1000}"

    ports:
      - "3001:3001"

    environment:
      ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      SESSION_SECRET: ${SESSION_SECRET}
      ADMIN_COOKIE_SECURE: ${ADMIN_COOKIE_SECURE:-false}
      ADMIN_ALLOWED_HOSTS: ${ADMIN_ALLOWED_HOSTS:-*}
      HOMEPAGE_URL: ${HOMEPAGE_URL}
      HOMEPAGE_CONFIG_DIR: /config
      ADMIN_DATA_DIR: /data
      TZ: ${TZ:-UTC}

    volumes:
      - ${HOMEPAGE_HOST_CONFIG_DIR}:/config
      - ${HOMEPAGE_ADMIN_DATA_DIR}:/data

    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
```

这里没有 `networks:`、没有 `depends_on:`、没有 Docker Socket，也没有 Docker Socket Proxy。

### 4. 启动

```bash
docker compose pull
docker compose up -d
```

检查：

```bash
docker ps --filter name=homepage-admin
curl -s http://127.0.0.1:3001/healthz ; echo
```

正常会返回类似：

```json
{"status":"ok","version":"0.5.2"}
```

浏览器访问：

```text
http://<服务器地址>:3001
```

使用 `.env` 中的管理员账号登录。

## Portainer Stack

也可以直接把仓库中的 `docker-compose.portainer.yml` 粘贴到 Portainer Stack，并设置必要环境变量与两个宿主机目录。它同样只部署 **一个 `homepage-admin` 容器**。

---

# Docker 发现（可选）

Docker 发现不是 Homepage Admin 的安装依赖。如果不需要发现容器，到这里已经部署完成。

如果要使用 Docker 发现，推荐在**每一台需要被发现的 Docker 主机**上运行一个只读 Docker Socket Proxy。Homepage Admin 通过主机 IP / DNS 访问它，不需要与 Proxy 位于同一个 Docker Network。

项目提供了独立示例：

```text
docker-compose.docker-proxy.example.yml
```

示例内容：

```yaml
services:
  docker-socket-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    container_name: docker-socket-proxy
    restart: unless-stopped

    environment:
      CONTAINERS: "1"
      PING: "1"
      SERVICES: "1"
      TASKS: "1"
      POST: "0"

    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

    ports:
      - "192.0.2.20:2375:2375"
```

`192.0.2.20` 是文档示例地址，请替换成 Docker 主机自己的可信内网地址，并使用防火墙限制 2375 的访问来源。不要把未加密的 Docker API 暴露到公网。

部署 Proxy 后进入：

```text
Homepage Admin
→ Docker 发现
→ Docker 主机管理
→ 添加 Docker 主机
```

例如：

```text
Homepage Docker Server: docker-node
Docker API URL:          http://192.0.2.20:2375
Public Host:             192.0.2.20
```

保存后连接信息写入 Homepage 的 `docker.yaml`，例如：

```yaml
docker-node:
  host: 192.0.2.20
  port: 2375
```

从该主机导入服务时会自动使用：

```yaml
server: docker-node
container: example-service
```

## 多 Docker 主机

多主机不需要跨主机 Docker Network。每台 Docker 主机各自提供一个可达的只读 API 即可：

```text
Homepage Admin
      │
      ├── http://192.0.2.20:2375 → Docker Host A
      ├── http://192.0.2.21:2375 → Docker Host B
      └── http://192.0.2.22:2375 → Docker Host C
```

把它们分别加入 **Docker 主机管理** 后，Docker 发现页面可以聚合浏览和导入所有主机的容器。

> [!IMPORTANT]
> 如果希望 Homepage 自己在服务卡片上显示 Docker 状态，**Homepage 容器本身也必须能够访问 `docker.yaml` 中对应的 host/port**。使用宿主机 LAN IP / DNS 时通常不需要额外共享网络。

---

# Proxmox 多节点发现

`proxmox.yaml` 是 Proxmox 连接的配置源。Homepage Admin 支持聚合多个 PVE 节点 / Cluster，发现 QEMU VM 与 LXC，并绑定到已有 Homepage 服务。

```yaml
pve-node1:
  url: https://pve.example.com:8006
  token: homepage@pve!homepage
  secret: your-token-secret

pve-node2:
  url: https://pve.example.com:8006
  token: homepage@pve!homepage
  secret: your-token-secret
```

也可以直接在：

```text
Homepage Admin
→ Proxmox 发现
→ Proxmox 节点管理
```

添加、测试、编辑和删除连接。建议使用只读 API Token，并只授予发现 VM/LXC 与读取资源状态所需权限。

---

# 管理的 Homepage 文件

```text
services.yaml
bookmarks.yaml
settings.yaml
widgets.yaml
docker.yaml
proxmox.yaml
kubernetes.yaml
custom.css
custom.js
```

所有保存操作都会先校验，再进行原子写入；支持的操作同时生成备份和审计记录。

## Widget Schema

Service Widget 表单不是固定维护一份旧列表。Homepage Admin 可以同步 Homepage 官方 Service Widget 文档与注册表，动态生成 Schema，并把缓存保存到 `/data`。

外网不可用时可以继续使用镜像内置 Schema，或导入离线 Schema JSON。

---

# 备份与恢复

备份中心支持自动文件备份、完整配置快照、备注、保护、ZIP 导出、恢复前 Diff、单文件恢复与整组恢复。

完整恢复前还会自动创建一个受保护的“恢复前保护点”。

Admin 数据默认保存在 `/data`，请务必持久化这个目录。

---

# 安全建议

- 不要把 `/var/run/docker.sock` 直接挂载到 Homepage Admin。
- 使用 Docker 发现时推荐只读 Docker Socket Proxy，并保持 `POST=0`。
- 对外提供 2375 时只允许可信内网访问，并使用防火墙限制来源。
- 公网访问 Homepage Admin 时建议放在 HTTPS 反向代理后，并设置 `ADMIN_COOKIE_SECURE=true`。
- 使用强管理员密码与长随机 `SESSION_SECRET`。
- 可以使用 `ADMIN_PASSWORD_HASH` 代替明文管理员密码。
- 不要把 `.env`、API Token、密码或真实 `proxmox.yaml` 上传到公开仓库。

生成 bcrypt 密码哈希：

```bash
docker run --rm -it ghcr.io/aspeternity/homepage-admin:latest \
  python -m app.hash_password
```

---

# 升级

使用 `latest`：

```bash
docker compose pull
docker compose up -d
```

建议升级前在 **备份中心 → 立即创建完整快照**。

也可以固定版本：

```yaml
image: ghcr.io/aspeternity/homepage-admin:0.5.2
```

版本变化请查看 [`CHANGELOG.md`](CHANGELOG.md)。

---

# 从源码运行

```bash
git clone https://github.com/Aspeternity/homepage-admin.git
cd homepage-admin
cp .env.example .env

docker compose up -d --build
```

运行测试：

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions 会在发布 GHCR 镜像前执行测试，并构建 `linux/amd64` 与 `linux/arm64` 镜像。

---

# 项目原则

- **Homepage YAML 是唯一事实来源**：不把服务配置迁移到额外数据库。
- **不修改 Homepage 本体**：通过挂载 Homepage 配置目录工作。
- **部署保持独立**：Homepage Admin 不要求与 Homepage / Docker Proxy 共享 Docker Network。
- **Docker / Proxmox 发现是可选能力**：不影响基础配置管理功能。
- **优先可逆操作**：保存前 Diff、自动备份、完整快照、恢复保护点。
- **Secret 不回显**：Token、API Key、Password 默认掩码。
- **兼容未来字段**：可视化表单无法识别的 YAML 字段尽量原样保留。
- **发现默认只读**：不提供停止、删除、重启容器或 VM 的接口。

## License

[MIT](LICENSE)
