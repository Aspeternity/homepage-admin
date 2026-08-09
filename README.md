# Homepage Admin v0.1.1

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

## 第一版包含的功能

- 登录、Session、CSRF 校验和简单登录限流
- `services.yaml`：服务/分组新增、编辑、删除、复制、跨分组拖动排序
- 服务常用字段：图标、链接、说明、`siteMonitor`、`ping`、Docker 集成、单个 Widget
- API Key 在普通表单中不回显；留空会保留原值
- `bookmarks.yaml`：分组与书签管理、拖动排序
- `settings.yaml`：标题、主题、背景滤镜、快速启动、布局配置
- `widgets.yaml`：顶部组件增删改和排序
- `docker.yaml`、`proxmox.yaml`、`kubernetes.yaml`、`custom.css`、`custom.js` 高级编辑
- YAML 保存前校验、文件锁、临时文件原子替换
- 每次保存前自动备份、可视化恢复、审计日志
- 保留未知字段和大部分原有注释/顺序（使用 `ruamel.yaml`）

## 与 Homepage 官方配置模型的对应关系

- 服务和分组来自 `services.yaml`，服务可配置 Widget、状态监控和 Docker 容器关联。
- 书签来自 `bookmarks.yaml`，结构比服务简单。
- 顶部信息组件来自 `widgets.yaml`，顺序由文件中的顺序决定。
- 页面级选项来自 `settings.yaml`。官方说明该文件保存后，需要在 Homepage 页面右下角点击刷新图标重新生成静态 HTML。
- 第一版不读取 Docker Socket。后续做“扫描 Docker 容器”时，应使用只读 Docker Socket Proxy，而不是把完整 Socket 直接给后台。

官方文档：

- https://gethomepage.dev/configs/services/
- https://gethomepage.dev/configs/bookmarks/
- https://gethomepage.dev/configs/settings/
- https://gethomepage.dev/configs/info-widgets/
- https://gethomepage.dev/configs/docker/

## 目录结构

```text
homepage-admin-v0.1.1/
├── app/
│   ├── main.py
│   ├── store.py
│   ├── security.py
│   ├── settings.py
│   ├── templates/
│   └── static/
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── requirements.txt
```


## 推荐部署方式：GitHub + GHCR + Portainer

从 v0.1.1 开始，项目自带 GitHub Actions，可在代码提交到 GitHub 后自动测试、构建并发布多架构 Docker 镜像到 GHCR。

关键文件：

- `.github/workflows/docker-publish.yml`：自动测试、构建、发布。
- `docker-compose.ghcr.yml`：Portainer / Docker Compose 直接拉 GHCR 镜像。
- `GITHUB_DEPLOY_GUIDE_ZH.md`：面向第一次使用 GitHub 的完整中文操作指南。

最终部署镜像形式：

```text
ghcr.io/你的GitHub用户名/homepage-admin:latest
```

如果使用 GHCR 方案，就不需要在 Docker VM 本地执行 `docker build`。

## 在你的 Docker VM 上部署

下面假定：

- Homepage 配置目录：`/opt/docker/homepage/config`
- 后台项目目录：`/opt/docker/homepage-admin`
- 后台备份目录：`/opt/docker/homepage-admin/data`
- 后台端口：`3001`

### 1. 解压项目

```bash
mkdir -p /opt/docker/homepage-admin
cd /opt/docker/homepage-admin
unzip homepage-admin-v0.1.1.zip
cd homepage-admin-v0.1.1
```

如果解压后多了一层目录，保证当前目录能看到 `docker-compose.yml`。

### 2. 确认 Homepage 配置目录

```bash
ls -la /opt/docker/homepage/config
```

应当能看到：

```text
services.yaml
bookmarks.yaml
settings.yaml
widgets.yaml
```

如果你的实际路径不同，修改 `docker-compose.yml` 中这一行：

```yaml
- /opt/docker/homepage/config:/config
```

### 3. 创建环境文件

```bash
cp .env.example .env
```

先生成 Session 密钥：

```bash
openssl rand -hex 32
```

将结果填写到 `.env` 的 `SESSION_SECRET`。

第一种登录密码配置方式，最简单：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你的强密码
ADMIN_PASSWORD_HASH=
```

第二种方式更推荐，使用 bcrypt 哈希：

先临时构建镜像：

```bash
docker compose build
```

生成哈希：

```bash
docker compose run --rm homepage-admin python -m app.hash_password '你的强密码'
```

将输出用单引号包住写进 `.env`：

```env
ADMIN_PASSWORD=
ADMIN_PASSWORD_HASH='$2b$12$......'
```

### 4. 设置文件权限

镜像默认使用 UID/GID `1000:1000`。先检查配置目录所有者：

```bash
stat -c '%u:%g %n' /opt/docker/homepage/config
```

最简单的设置：

```bash
mkdir -p /opt/docker/homepage-admin/data
chown -R 1000:1000 /opt/docker/homepage/config /opt/docker/homepage-admin/data
```

如果你的 Homepage 已经使用其他 PUID/PGID，将 `.env` 中的 `PUID`、`PGID` 改成相同值，再按该 UID/GID 设置权限。

### 5. 启动

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f homepage-admin
```

访问：

```text
http://10.10.1.11:3001
```

## 在 Portainer 中部署

推荐使用 GHCR 镜像部署，不再需要本地构建。完整步骤见：

```text
GITHUB_DEPLOY_GUIDE_ZH.md
```

发布 GHCR 镜像后，在 `docker-compose.ghcr.yml` 中把：

```text
ghcr.io/YOUR_GITHUB_USERNAME/homepage-admin:latest
```

替换成你的真实 GitHub 用户名，然后粘贴到 Portainer Stack。

`docker-compose.portainer.yml` 仍保留用于本地镜像模式，但新用户建议直接使用 `docker-compose.ghcr.yml`。

## Nginx Proxy Manager 反代

建议第一阶段只允许内网访问。如果需要域名访问：

1. NPM 转发到 `10.10.1.11:3001`
2. 启用 HTTPS
3. `.env` 设置：

```env
ADMIN_COOKIE_SECURE=true
ADMIN_ALLOWED_HOSTS=homepage-admin.aspandre.cn,10.10.1.11,localhost
```

4. 重建容器：

```bash
docker compose up -d --force-recreate
```

不要将后台无保护地暴露到公网。后台能够修改链接、API Key 和其他敏感配置。

## 使用说明

### 服务管理

普通表单覆盖最常用的 Homepage 字段。没有做成表单的字段放在：

- `Widget 其他配置`
- `额外服务配置`

例如：

```yaml
enableBlocks: true
enableNowPlaying: true
```

或者：

```yaml
showStats: true
```

### 多 Widgets

官方支持一个服务使用 `widgets:` 数组。第一版普通表单只直接编辑单个 `widget:`，但现有 `widgets:` 会保存在“额外服务配置”中，不会主动删除。复杂配置可使用高级编辑器。

### 嵌套分组

官方支持嵌套服务分组。第一版能够保留和显示嵌套分组，但不提供递归可视化编辑；请使用高级 YAML 编辑器。

### settings.yaml 刷新

保存页面设置后，打开 Homepage，在右下角点击刷新图标。普通服务和书签修改通常刷新浏览器即可看到。

### 背景滤镜

Homepage 官方说明 `cardBlur` 与背景的 `blur`、`saturate`、`brightness` 滤镜不兼容。设置页会提示这一点，但不会强制删除你的配置。

## 数据安全

保存流程：

```text
YAML 解析校验
→ 文件锁
→ 备份原文件
→ 写入同目录临时文件
→ fsync
→ os.replace 原子替换
→ 写入审计日志
```

备份目录：

```text
/opt/docker/homepage-admin/data/backups
```

审计日志：

```text
/opt/docker/homepage-admin/data/audit.jsonl
```

## 第一版已知限制

- 不扫描 Docker 容器，也不连接 Docker Socket
- 不自动读取 Homepage 所有 Widget 的专属字段定义
- 多 Widgets 和嵌套分组主要通过高级 YAML 编辑器管理
- 没有实时 iframe 预览，避免受 Homepage CSP 和反代策略影响
- 当前仅单管理员账户
- 配置写入是逐文件事务；创建/重命名分组时，`services.yaml`/`bookmarks.yaml` 与 `settings.yaml` 会分别备份和写入

## 第二版建议

- Docker Socket Proxy 只读容器扫描
- 官方 Widget 模板库与动态表单
- 图标搜索与本地图标上传
- 分组拖动和设置页布局拖动
- 修改前后 YAML Diff
- Homepage 刷新/重载联动
- 多用户和只读账户
