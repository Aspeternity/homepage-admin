# Homepage Admin v0.2.3

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是和 Homepage 挂载同一个配置目录，直接读写官方 YAML 文件。

> v0.2.3 的重点：**修复 Docker 导入向导字段错位、增强智能推荐与卡片预览、备份保留数量可在后台配置**。

## v0.2.3 新增 / 修复

### Docker 导入向导体验优化

- 修复“访问地址”和“图标”等输入框因为来源提示数量不同而上下错位的问题。
- 向导顶部新增服务识别信息：`识别为` + `置信度`。
- Docker 发现页默认分组策略改为 `智能推荐（按服务类型）`；仍可手动固定到指定分组。
- `homepage.group` Label 继续拥有最高优先级。
- 常见服务按类型推荐现有分组，例如服务器监控 / 管理面板优先匹配 `内网Tools`，影音 / 下载类优先匹配 `群晖NAS` 等已有分组。
- 扩展常见服务图标建议，并保留原有说明、发布端口、Widget 类型与 Widget URL 推断。
- 卡片预览支持直接预览 HTTP(S) 图标与 `sh-*` 图标；图片失败时自动回退为文字图标。
- YAML 预览继续只展示非敏感字段；API Key / Token / Password 仍在完整编辑器中填写。

### 备份保留数量可配置

- `备份回滚` 页面新增 `自动保留策略`。
- 可在 UI 中设置保留 `1–500` 组备份，不再只能依赖固定的 `BACKUP_LIMIT=50`。
- 设置保存在 `/data/admin-settings.json`，因此容器重建后仍保留。
- 如果降低上限，保存后立即删除最旧的超额备份。
- 支持一键 `恢复默认`，回到环境变量 `BACKUP_LIMIT`（默认 50）。
- 单个删除、清空全部、恢复备份与审计日志功能继续保留。

### 延续 v0.2.2 的主题体验

- 右上角紧凑主题图标。
- 浅色 / 深色 / 跟随系统。
- 浏览器记住主题偏好。

## Docker 安全架构

延续 v0.2.1+ 的共享只读代理结构：

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
- Docker 容器发现、已添加识别、系统组件隐藏、端口去重
- Docker 四步导入向导、服务类型识别、智能分组、卡片与 YAML 预览
- 自动备份、回滚、删除、可配置保留数量、YAML 校验、原子写入、审计日志
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

从 v0.2.2 升级请阅读：

```text
UPGRADE_V0.2.3_ZH.md
```

## Homepage 配置文件

Homepage Admin 仍以 YAML / CSS / JS 文件作为数据源：

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
