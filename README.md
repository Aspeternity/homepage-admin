# Homepage Admin v0.3.3

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是与 Homepage 共享配置目录，以官方 YAML 文件为唯一配置源。

> v0.3.2 的主题是：**Homepage 官方 Widget Schema 自动同步 + 全量动态表单 + Schema 管理 + 全局回到顶部**。

## v0.3.2 新功能

### Widget 中心：从人工目录升级为官方 Schema 驱动

v0.3.2 不再把“15 个增强表单 + 其余通用 YAML”作为长期方案。Admin 会自动同步 Homepage 官方：

- `docs/widgets/services/*.md`：读取 Widget YAML 配置示例、Allowed fields。
- `src/widgets/widgets.js`：读取真实 Widget 注册表和兼容别名。

同步器会把官方配置示例转换为动态表单：文本、布尔、数字、YAML、Secret 等字段自动识别；`Allowed fields` 自动变成展示字段复选框。官方以后新增 Service Widget 时，Admin 会在后台同步后自动出现，不必等待 Homepage Admin 发版。

现有 Jellyfin、Portainer、Proxmox、Home Assistant、qBittorrent 等深度增强会叠加在官方自动 Schema 上，继续提供更友好的标签和深度连接测试，同时不会挡住官方新增字段。

### Widget Schema 管理与缓存

新增 **Widget 中心 → Schema 管理**：

- 查看来源、Ref、最后同步时间和 Widget / 字段数量。
- 手动立即同步。
- 查看部分解析警告。
- 清除 `/data/widget-schema-cache.json` 并恢复内置离线目录。
- 无法访问 GitHub 时可离线导入 Widget Schema JSON。

默认每 24 小时后台检查一次官方 Schema；同步失败不会影响现有管理功能。GitHub Actions 发布 GHCR 镜像前也会生成一份近期官方 Schema 快照。

### 通用文案与长页面体验

- 书签管理不再默认提到 PT 站点，统一描述为“网站书签、快捷链接和分类”。
- 全站长页面滚动超过约 520px 后显示“回到顶部”，Widget 中心、Docker 发现、Proxmox 发现、高级编辑等页面均可使用。

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

v0.3.2 **不要求 MySQL**。当前项目的数据模型仍然适合保持文件原生：

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
UPGRADE_V0.3.2_ZH.md
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
