# Homepage Admin v0.3.1

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是与 Homepage 共享配置目录，以官方 YAML 文件为唯一配置源。

> v0.3.1 的主题是：**Widget 中心 + 元数据驱动表单 + 连接测试 + Proxmox 发现 + 多 Widget + 保存前 Diff**。

## v0.3.1 新功能

### Widget 中心

新增独立的 **Widget 中心**，按分类浏览和搜索常用 Homepage Service Widget。当前内置家庭实验室常用模板：

- Jellyfin
- Portainer
- Proxmox VE
- Home Assistant
- qBittorrent
- Transmission
- Synology DiskStation
- OpenWRT / ImmortalWRT
- Minecraft
- GameDig
- Glances
- Uptime Kuma
- NGINX Proxy Manager
- Grafana
- Custom API

Widget 表单不再为每个类型单独写页面，而是由 `app/widget_catalog.py` 元数据动态生成。后续增加 Widget 支持主要扩展目录元数据即可。

### 保存前“测试连接”

每个 Widget 编辑块提供 **测试连接**：

- Jellyfin / Portainer / Proxmox / Home Assistant / qBittorrent / Transmission / Glances / Custom API：API 深度测试。
- DiskStation / OpenWRT / Uptime Kuma / NGINX Proxy Manager / Grafana：基础 HTTP 连通测试。
- Minecraft / GameDig：配置完整性校验，不主动扫描非 HTTP 端口。

编辑已有服务时，后台可直接复用已经保存的 API Key / Token / Password 进行测试，真实 Secret 不回传浏览器。

> 测试请求从 Homepage Admin 容器发起。如果目标只在 Homepage 自己的独立 Docker 网络中可解析，而 Admin 不在该网络，测试结果可能与 Homepage 本体不同。

### 一个服务支持多个 Widget

服务编辑器支持：

- `+ 添加 Widget`
- 上移 / 下移 / 删除 Widget
- 单个 Widget 时兼容写回 `widget:`
- 多个 Widget 时写回 Homepage 的 `widgets:` 列表
- 每个 Widget 独立连接测试
- 每个 Widget 独立高级 YAML 映射
- 原有敏感字段留空时继续保留旧值

### Widget fields 可视化

对支持 `fields` 的 Widget 显示复选框，最多选择 4 个展示字段。例如：

- Proxmox：VM / LXC / CPU / Memory
- Portainer：Running / Stopped / Total
- qBittorrent / Transmission：Leech / Download / Seed / Upload
- Home Assistant：People Home / Lights On / Switches On

### Proxmox 发现与 VM/LXC 绑定

新增 **Proxmox 发现** 页面：

- 读取 `proxmox.yaml` 中的只读 API Token 连接。
- 自动列出 QEMU VM / LXC、VMID、运行状态、CPU、内存。
- 可把 VM/LXC 直接关联到已有 Homepage 服务。
- 可从 VM/LXC 一键预填新服务。
- 如果 `proxmox.yaml` 为空，但已有 Proxmox Service Widget，可在服务端直接把现有 Token 配置复制到 `proxmox.yaml`，不需要再次在浏览器输入 Secret。

绑定会写入服务的 `proxmoxNode`、`proxmoxVMID`，LXC 额外写入 `proxmoxType: lxc`。

### 保存前 Diff

服务编辑器和高级 YAML 编辑器增加 **保存前变更预览**：

- 展示当前配置与保存后配置的统一 Diff。
- API Key / Password / Token / Secret 在 Diff 中始终掩码。
- 没有实际变化时不会写配置，也不会生成备份。

## 数据存储与 MySQL

v0.3.1 **不要求 MySQL**。当前项目的数据模型仍然适合保持文件原生：

- Homepage 配置继续以官方 YAML 为唯一事实来源。
- 管理后台偏好继续保存在 `/data/admin-settings.json`。
- 自动备份、审计日志继续保存在 `/data`。

这样升级不需要新增数据库账号、Schema、迁移和数据库可用性依赖。未来如果加入多用户权限、跨实例管理、历史版本索引或大量运行指标，再考虑可选 MySQL 后端更合适。

## Docker 安全架构

延续 v0.2.1 之后的共享只读代理：

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

## 其他现有功能

- 服务 / 书签 / 分组拖拽排序
- 顶部组件拖拽排序
- Docker 容器发现与导入向导
- Docker 已添加识别、系统组件隐藏、端口去重
- 智能服务类型识别与分组推荐
- 页面设置、背景、Layout、Quick Launch 可视化编辑
- 深色 / 浅色 / 跟随系统主题
- API Key / Token / Password 默认遮挡并安全保留
- 高级 YAML / CSS / JS 编辑
- 自动备份、可配置保留数量、单个删除、全部清理、回滚
- YAML 校验、原子写入、文件锁、审计日志
- GitHub Actions 测试并发布 amd64 / arm64 GHCR 镜像

## 当前部署参数

```text
镜像: ghcr.io/aspeternity/homepage-admin:latest
Homepage 配置: /opt/docker/HomePage/data/config
Admin 数据: /opt/docker/homepage-admin/data
Admin 端口: 3001
共享 Docker 网络: homepage-tools
```

从 v0.2.4 升级请阅读：

```text
UPGRADE_V0.3.1_ZH.md
```

## Homepage 配置文件

Homepage Admin 继续直接管理：

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
