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

Homepage Admin 与 Homepage **共享同一个配置目录**，直接读取和写入 Homepage 官方配置文件。Homepage 的 YAML 仍然是唯一事实来源，因此你可以随时回到手工编辑，也可以继续使用 Homepage 官方支持的全部配置能力。

适合以下场景：

- 已经运行 Homepage，希望减少手工维护 YAML 的工作量。
- 服务、书签、Widget 较多，需要更直观的增删改、排序和连接测试。
- 有多个 Docker 主机或多个 Proxmox 节点，希望集中发现并导入到 Homepage。
- 希望修改配置前有 Diff、自动备份、完整快照和一键回滚。
- 希望跟随 Homepage 官方 Service Widget 变化，而不是手工维护一套固定 Widget 列表。

## 主要功能

| 模块 | 能力 |
| --- | --- |
| 服务管理 | 可视化管理 `services.yaml`，分组、排序、多 Widget、字段选择、保存前 Diff |
| Widget 中心 | 同步 Homepage 官方 Service Widget Schema，自动生成动态表单 |
| 书签管理 | 可视化管理 `bookmarks.yaml`，支持分组与拖拽排序 |
| 页面设置 | 可视化管理常用 `settings.yaml`，背景、主题、Quick Launch、布局等 |
| 顶部组件 | 管理 `widgets.yaml`，支持 Homepage Information Widgets 专属表单 |
| Docker 发现 | 多 Docker 主机、容器发现、导入向导、`server + container` 绑定 |
| Proxmox 发现 | 多节点聚合、QEMU/LXC 发现、已有服务关联、节点管理 |
| 高级编辑 | 直接编辑 YAML / CSS / JS，并在保存前校验与预览 Diff |
| 备份中心 | 自动备份、完整快照、备注、保护、ZIP 导出、单文件/整组恢复 |
| 安全 | Session、CSRF、登录限流、Secret 掩码、原子写入、文件锁、审计日志 |

## 工作方式

```text
Homepage Admin
      │
      ├── 读取 / 写入 ──> Homepage 配置目录
      │                   ├── services.yaml
      │                   ├── bookmarks.yaml
      │                   ├── settings.yaml
      │                   ├── widgets.yaml
      │                   ├── docker.yaml
      │                   ├── proxmox.yaml
      │                   └── ...
      │
      ├── /data ────────> Admin 自己的状态
      │                   ├── 备份
      │                   ├── 审计日志
      │                   └── 管理偏好
      │
      └── 可选只读 API ─> Docker / Proxmox 发现
```

Homepage Admin 不会把 Homepage 配置迁移到 MySQL，也不会维护第二份服务配置。

---

# Docker 部署

## 推荐方案：GHCR + Docker Compose + 只读 Docker Proxy

这是推荐部署方式，既能管理 Homepage 配置，也能使用 Docker 发现功能。

### 1. 准备目录与共享网络

下面路径只是示例，请替换为你自己的 Homepage 配置目录：

```bash
mkdir -p /opt/docker/homepage-admin/data

docker network inspect homepage-tools >/dev/null 2>&1 \
  || docker network create homepage-tools
```

Homepage、Homepage Admin 和 `docker-socket-proxy` 如果需要通过容器名称互相访问，应加入同一个 Docker 网络。

如果 Homepage 已经运行，但还没有加入 `homepage-tools`：

```bash
docker network connect homepage-tools <你的 Homepage 容器名>
```

> 如果提示已经连接，可以忽略。

### 2. 创建 `.env`

先生成一个随机 Session Secret：

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

# Homepage 容器在共享网络中的地址。
# 如果容器名不是 HomePage，请改成实际容器名或 Admin 可访问的 URL。
HOMEPAGE_URL=http://HomePage:3000

# 宿主机上的 Homepage 配置目录。
HOMEPAGE_HOST_CONFIG_DIR=/opt/docker/HomePage/data/config

# Homepage Admin 自己的数据目录。
HOMEPAGE_ADMIN_DATA_DIR=/opt/docker/homepage-admin/data

# HTTP 部署保持 false；如果通过 HTTPS 反向代理访问，建议改成 true。
ADMIN_COOKIE_SECURE=false

# 可选：限制 Host。测试阶段可使用 *，公网部署建议填写实际域名。
ADMIN_ALLOWED_HOSTS=*
```

> `PUID/PGID` 对应的用户必须对 Homepage 配置目录和 Admin 数据目录具有读写权限。

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

      HOMEPAGE_URL: ${HOMEPAGE_URL:-http://HomePage:3000}
      HOMEPAGE_CONFIG_DIR: /config
      ADMIN_DATA_DIR: /data
      BACKUP_LIMIT: ${BACKUP_LIMIT:-50}
      TZ: ${TZ:-UTC}

      # Docker 发现使用共享只读代理。
      DOCKER_DISCOVERY_URL: http://homepage-docker-proxy:2375
      HOMEPAGE_DOCKER_PROXY_HOST: homepage-docker-proxy
      HOMEPAGE_DOCKER_PROXY_PORT: "2375"
      DOCKER_HIDE_INTERNAL: "true"

    volumes:
      - ${HOMEPAGE_HOST_CONFIG_DIR}:/config
      - ${HOMEPAGE_ADMIN_DATA_DIR}:/data

    depends_on:
      - docker-proxy

    networks:
      - homepage-tools

    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777

  docker-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    pull_policy: always
    container_name: homepage-docker-proxy
    restart: unless-stopped

    environment:
      CONTAINERS: "1"
      PING: "1"
      SERVICES: "1"
      TASKS: "1"
      POST: "0"

    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

    networks:
      homepage-tools:
        aliases:
          - homepage-docker-proxy

networks:
  homepage-tools:
    external: true
```

这个例子中 `docker-proxy` **没有映射宿主机端口**，只允许共享 Docker 网络内的容器访问；同时 `POST=0`，用于只读发现。

### 4. 启动

```bash
docker compose pull
docker compose up -d
```

检查状态：

```bash
docker ps --filter name=homepage-admin
curl -s http://127.0.0.1:3001/healthz ; echo
```

正常情况下健康检查会返回类似：

```json
{"status":"ok","version":"0.5.1"}
```

然后访问：

```text
http://<Docker 主机地址>:3001
```

使用 `.env` 中的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。

### 5. 让 Homepage 使用只读 Docker Proxy

如果希望 Homepage 自己也显示 Docker 容器状态，可以在 Homepage 的 `docker.yaml` 中配置：

```yaml
local-docker:
  host: homepage-docker-proxy
  port: 2375
```

然后在服务中使用：

```yaml
- Example Service:
    href: https://service.example.com
    server: local-docker
    container: example-service
```

也可以直接在 **Homepage Admin → Docker 发现 → Docker 主机管理** 中完成主机配置和服务导入。

---

## 最小部署：不使用 Docker 发现

如果你只需要可视化编辑 Homepage 配置，可以完全不挂 Docker Socket，也不启动 `docker-socket-proxy`：

```yaml
services:
  homepage-admin:
    image: ghcr.io/aspeternity/homepage-admin:latest
    container_name: homepage-admin
    restart: unless-stopped
    user: "1000:1000"

    ports:
      - "3001:3001"

    environment:
      ADMIN_USERNAME: admin
      ADMIN_PASSWORD: change-me-now
      SESSION_SECRET: replace-with-a-long-random-string
      HOMEPAGE_CONFIG_DIR: /config
      ADMIN_DATA_DIR: /data
      HOMEPAGE_URL: http://HomePage:3000
      TZ: UTC

    volumes:
      - /path/to/homepage/config:/config
      - /path/to/homepage-admin/data:/data
```

这种模式下服务、书签、页面设置、Widget、备份和高级编辑都可以正常使用；Docker 发现功能会提示尚未配置 Docker 主机。

---

## 多 Docker 主机

Homepage Admin 支持从多台 Docker 主机发现容器。

推荐在每台远程 Docker 主机上部署一个只读 `docker-socket-proxy`。例如远程主机：

```yaml
services:
  docker-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    container_name: homepage-docker-proxy
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

`192.0.2.20` 是文档示例地址。实际部署时请换成远程 Docker 主机的内网 IP，并使用防火墙**只允许 Homepage / Homepage Admin 所在主机访问 2375**，不要把未加密的 Docker API 暴露到公网。

之后进入：

```text
Homepage Admin
→ Docker 发现
→ Docker 主机管理
→ 添加 Docker 主机
```

例如：

```text
Homepage Docker Server: game-server
Docker API URL:          http://192.0.2.20:2375
Public Host:             192.0.2.20
```

保存后，容器导入会自动使用对应的：

```yaml
server: game-server
container: <容器名>
```

---

# Proxmox 多节点发现

`proxmox.yaml` 是 Proxmox 节点连接的唯一配置源。Homepage Admin 支持聚合多个 PVE 节点 / Cluster，发现 QEMU VM 与 LXC，并绑定到已有 Homepage 服务。

示例：

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

也可以直接通过：

```text
Homepage Admin
→ Proxmox 发现
→ Proxmox 节点管理
```

添加、测试、编辑、删除节点连接。

> 建议创建只读 API Token，只授予发现 VM/LXC 和读取资源状态所需权限。

---

# 管理的 Homepage 文件

Homepage Admin 当前直接管理：

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

所有保存操作都会先校验，再使用原子写入；支持的操作还会生成备份和审计记录。

## Widget Schema

Service Widget 表单不是固定维护一份旧列表。Homepage Admin 可以同步 Homepage 官方 Service Widget 文档和注册表，生成动态 Schema，并将缓存保存到 `/data`。

如果外网不可用，也可以继续使用镜像内置 Schema 或导入离线 Schema JSON。

---

# 备份与恢复

备份中心支持：

- 配置保存前自动文件级备份。
- 手动创建完整 Homepage 配置快照。
- 备份备注、筛选、保护和 ZIP 导出。
- 恢复前 Diff，敏感字段掩码。
- 单文件恢复与完整快照恢复。
- 完整恢复前自动创建受保护的恢复点。

Admin 自己的数据默认保存在：

```text
/data
```

请为该目录配置持久化卷。

---

# 安全建议

- 不要直接把 `/var/run/docker.sock` 挂进 Homepage Admin；推荐使用只读 Docker Socket Proxy。
- Docker Proxy 保持 `POST=0`。
- 跨主机的 `2375` 只允许可信内网访问，并使用防火墙限制来源。
- 公网访问 Homepage Admin 时建议放在 HTTPS 反向代理后，并设置 `ADMIN_COOKIE_SECURE=true`。
- 使用长随机 `SESSION_SECRET`。
- 使用强管理员密码；也可以配置 `ADMIN_PASSWORD_HASH` 代替明文密码。
- 不要把 `.env`、API Token、Password 或真实 `proxmox.yaml` 上传到公开仓库。

生成 bcrypt 密码哈希：

```bash
docker run --rm -it ghcr.io/aspeternity/homepage-admin:latest \
  python -m app.hash_password
```

然后把结果写入：

```env
ADMIN_PASSWORD_HASH=$2b$...
```

此时可以不设置 `ADMIN_PASSWORD`。

---

# 升级

如果使用 `latest`：

```bash
docker compose pull homepage-admin
docker compose up -d homepage-admin
```

建议升级前先在 **备份中心 → 立即创建完整快照**。

使用固定版本标签可以降低意外升级风险，例如：

```yaml
image: ghcr.io/aspeternity/homepage-admin:0.5.1
```

版本变更请查看：

- [`CHANGELOG.md`](CHANGELOG.md)
- 仓库内各版本 `UPGRADE_V*.md`

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
- **不修改 Homepage 本体**：通过共享配置目录工作。
- **优先可逆操作**：保存前 Diff、自动备份、完整快照、恢复保护点。
- **Secret 不回显**：Token、API Key、Password 在浏览器中默认掩码。
- **兼容未来字段**：可视化表单无法识别的 YAML 字段尽量原样保留。
- **发现默认只读**：Docker / Proxmox 发现不提供停止、删除、重启容器或 VM 的接口。

## License

[MIT](LICENSE)
