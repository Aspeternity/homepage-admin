# Homepage Admin v0.2.2

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

> v0.2.2 的重点：**Docker 导入向导、右上角主题菜单、可删除的备份回滚记录**。

## v0.2.2 新增 / 修复

### Docker 导入向导

Docker 发现页点击“添加到 Homepage”后，不再直接跳进完整服务表单，而是进入四步导入流程：

1. 识别容器：名称、镜像、运行状态、发布端口、Docker Server。
2. 调整建议：自动推荐服务名、访问地址、图标、说明、分组、Widget 类型和 Widget URL。
3. 实时预览：同时展示模拟 Homepage 卡片与非敏感 YAML 预览。
4. 完整编辑：把向导中修改过的值带入原来的服务编辑器，再填写 API Key、用户名、密码及高级 YAML。

推荐值会标注来源，例如：`Homepage Label`、`容器名称`、`发布端口`、`镜像识别`、`Docker 发现页选择`。

内置常见服务说明识别包括 Jellyfin、qBittorrent、Transmission、Home Assistant、Portainer、Proxmox、Vaultwarden、MoviePilot、MeTube、Lsky Pro、MkDocs、MySQL、phpMyAdmin、Komari、CookieCloud、RustDesk、1Panel 等。

### 右上角主题菜单

- 桌面端移除左下角大号主题按钮，改为页面右上角小图标。
- 点击图标弹出：**浅色模式 / 深色模式 / 跟随系统**。
- 继续使用浏览器 `localStorage` 保存主题偏好。
- 旧版已保存的 `light` / `dark` 偏好可直接沿用。
- 移动端与登录页保留紧凑图标切换。

### 备份回滚维护

- 每组备份新增“删除备份”按钮。
- 备份页新增“清空全部备份”。
- 删除操作均要求 CSRF 校验和二次确认。
- 页面显示当前备份组数量、每组文件数和占用空间。
- 自动保留上限 `BACKUP_LIMIT` 仍然生效；默认最多 50 组。
- 删除备份动作写入审计日志。

## Docker 安全架构

延续 v0.2.1 的共享只读代理结构：

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

## 仍然支持的核心功能

- 服务 / 书签 / 分组拖拽排序
- 顶部组件拖拽排序
- Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox 专属 Widget 表单
- API Key / Token / Password 遮挡与保留
- 高级 YAML 敏感值安全占位符
- Docker 容器发现、已添加识别、内部容器隐藏、端口去重
- 自动备份、回滚、删除、YAML 校验、原子写入、审计日志
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

从 v0.2.1 升级请阅读：

```text
UPGRADE_V0.2.2_ZH.md
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
