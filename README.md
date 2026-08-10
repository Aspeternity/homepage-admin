# Homepage Admin v0.4.7

一个独立的 Homepage 可视化配置后台。它不修改 Homepage 本体，而是与 Homepage 共享配置目录，以官方 YAML 文件为唯一配置源。



## v0.4.3：Docker 主机 Single Source of Truth

- `docker.yaml` 现在是 Docker 主机连接的唯一事实来源：Server、Host、Port、Protocol、Socket、TLS、Header 只维护一份。
- `/data/admin-settings.json` 不再复制 Docker 连接，只保留 Admin 专属元数据：显示名称、Public Host，以及必要时的 Discovery Override。
- v0.4.0-v0.4.2 的 `docker_discovery_hosts` 旧数据启动时自动迁移；若旧 Discovery URL 与 `docker.yaml` 一致，会直接丢弃重复 URL；只有地址确实不同时才保留为显式 Override。
- 新增/编辑 Docker 主机时，连接地址只写入 `docker.yaml`，Admin 元数据独立保存；默认发现直接使用 `docker.yaml`。
- Docker 主机删除时直接删除 `docker.yaml` Server，并自动清理该 Server 的 Admin 元数据；服务引用保护继续保留。
- 主机编辑页新增“Admin Discovery Override（可选）”，仅用于 Socket / 容器 DNS 等 Admin 无法直接访问 `docker.yaml` 地址的特殊部署。

详细说明见 `UPGRADE_V0.4.3_ZH.md`。

## v0.4.2 Docker 主机管理统一化

- Docker 发现主页移除重复的主机状态卡，只保留主机选择、容器筛选和必要的连接错误提示。
- `docker.yaml` 已有 Server 与后来添加的远程主机统一使用同一个“编辑 Docker 主机”表单。
- 新增 Docker 主机时固定同时保存 Admin 发现信息并创建/更新同名 `docker.yaml` Server，不再区分“原生 Server / Admin 自定义”的配置流程。
- 编辑已有主机时保留 TLS、Header 和未知扩展字段；Homepage Server 名称继续锁定，避免打断已有服务引用。
- 删除页默认完整删除该主机的管理信息与 `docker.yaml` Server，并继续提供服务引用保护。

## v0.4.1：Docker 主机统一 CRUD 与依赖保护

- `docker.yaml` 自动发现的 Server 现在也有“编辑 / 删除”，不再只能通过高级 YAML 调整。
- `docker.yaml` 可视化编辑支持 Remote / Socket、Host、Port、Protocol、Socket 路径，并保留未回显的 TLS、Header 与未来扩展字段。
- Docker 主机列表显示每个 Server 被多少 Homepage 服务引用，并给出引用预览。
- 删除改为安全向导：可分别删除 Admin 自定义发现层、`docker.yaml` Server，并可选择同时清除相关服务的 `server` / `container`。
- 被服务引用的 `docker.yaml` Server 删除前必须输入 `DELETE`，避免误操作导致大量 Docker 状态失效。
- 已映射到 `docker.yaml` 的 Admin 自定义连接在编辑时锁定 Homepage Server 键名，避免无意断开已有服务引用。

详细说明见 `UPGRADE_V0.4.1_ZH.md`。

## v0.4.0：多 Docker 主机发现

- Docker 发现不再绑定单一 `DOCKER_DISCOVERY_URL`；会自动读取 `docker.yaml` 中的多个远程 Docker Server。
- 新增“Docker 主机管理”，可添加 Game-Server VM 等额外只读代理地址，并映射到 Homepage 的 `server`。
- 支持“全部 Docker 主机”聚合视图，每张容器卡片显示来源主机和 `server`。
- 同名容器按 `(server, container)` 匹配，避免跨主机误判。
- 导入容器时自动写入来源主机对应的 `server`，并使用该主机的 Public Host 推断发布端口访问地址。
- 自定义发现连接保存在 `/data/admin-settings.json`；可选同步创建 `docker.yaml` Server，但不会覆盖地址不同的既有 Server。
- 连接测试、搜索、状态筛选、已添加/未添加筛选均支持多主机。

详细升级和 Game-Server VM 只读代理示例见 `UPGRADE_V0.4.0_ZH.md`。


## v0.3.9 修复

- Proxmox 发现页已关联卡片中的“编辑服务 / 取消关联”统一为相同高度、宽度与拉伸规则，避免 `<a>` 与 `<form><button>` 在 CSS Grid 中因默认拉伸方式不同而视觉尺寸不一致。


## v0.3.8 修复

- Proxmox VM / LXC 集成三列字段统一行高，帮助文字不再导致输入框错位。
- Proxmox 发现页已关联卡片同时提供“编辑服务”和“取消关联”。
- 取消关联只移除 `proxmoxNode` / `proxmoxVMID` / `proxmoxType`，不会删除服务、Widget 或其他配置，并在写入前校验当前关联未发生变化。

## v0.3.7 修复

- Proxmox 发现会检测 `proxmox.yaml` URL 末尾 `/`，并提供一键去除，避免 Homepage 拼接 `/api2/json` 时形成双斜杠。
- 从 Proxmox Service Widget 导入连接时自动规范化 URL。
- VM/LXC 绑定改为使用 PVE 返回的真实物理节点名；若 `proxmox.yaml` 缺少同名节点连接，会显示兼容性警告并阻止错误绑定。
- 检测服务同时配置 Docker 与 Proxmox 的情况。Homepage 会同时渲染两套状态/资源，因此绑定时可选择清除 Docker 集成；已绑定服务也可在 Proxmox 发现页一键清除错误/过期 Docker 映射。
- 服务编辑页在 Docker + Proxmox 同时存在时显示明确警告，并把字段文案改为“Proxmox 节点名”。

## v0.3.6 修复

- 动态 Widget 表单为每个字段保留统一的“标题 / 输入控件 / 帮助说明”三段布局；像 Backrest 这种只有部分字段带官方说明的表单也能保持同一行输入框对齐。
- “立即同步官方 Schema”改为后台任务，不再让浏览器长时间等待整页 POST；页面实时显示读取目录、解析文档、读取注册表、合并、写缓存等阶段及百分比/文档计数。
- 同步失败时直接在进度面板显示错误并恢复按钮；同步成功后自动刷新 Schema 状态。


## v0.3.5 修复

- 自动同步计划中的“计划时区”与同步方式 / 每天同步时间顶部对齐，辅助说明不再把输入框顶高。
- Home Assistant `custom`（自定义状态 / 模板）明确改为可选；连接测试只验证实际需要的 URL 与长期访问令牌。
- 官方 Schema 自动表单采用保守的必填判定：仅当官方 inline comment 明确标记 required / mandatory / 必填时才自动标为必填。
- 旧版 Schema 缓存会在加载时清除历史错误 required 推断，再叠加 Admin 已知的深度增强必填规则，无需手工清缓存。
- Home Assistant 表单提示 `custom` 最多 4 项，并说明设置 `fields` 后 Homepage 会忽略 `custom`。


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

主 Docker VM 继续沿用 v0.2.1 之后的共享只读代理；v0.4.0 只是把发现层扩展为多个主机：

```text
Docker VM socket                    Game-Server VM socket
      │                                      │
      ▼                                      ▼
homepage-docker-proxy                  game-docker-proxy
POST=0 / read-only                      POST=0 / read-only
      │                                      │
      ├──────── Homepage Admin ──────────────┤
      │              │                       │
      │              └─ 多主机发现 / 导入 ──┘
      │
      └──────── Homepage
               docker.yaml:
                 local-docker: ...
                 game-server: ...
```

主 Docker VM 的 `homepage-docker-proxy` 仍可只加入共享 `homepage-tools` 网络而不暴露宿主机端口。跨 VM 的代理如果必须通过局域网端口访问，应使用 VM 防火墙限制来源，只允许 Homepage / Admin 所在主机访问，并保持 `POST=0`。

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


## v0.4.7 顶部组件工作区

- “顶部组件”从通用 YAML 列表升级为 Homepage Information Widget 工作区。
- 按当前官方文档内置 12 类 Info Widget：Greeting、Date & Time、Logo、Search、Resources、Glances、Open-Meteo、OpenWeatherMap、Stocks、UniFi Controller、Kubernetes、Longhorn。
- 新增官方组件目录、搜索/分类、已添加数量、官方文档入口和 Homepage 靠右布局提示。
- 官方类型使用专属可视化表单；未知/未来类型继续通过完整 YAML 兼容。
- Search 支持单 Provider、多 Provider 和 Custom；Resources/Glances 支持多磁盘；DateTime 暴露常用 Intl.DateTimeFormat；天气、Stocks、UniFi、Kubernetes、Longhorn 均提供对应字段与依赖提示。
- API Key、Password、Key 等敏感字段继续遮挡并在编辑保存时恢复原值。
- 未覆盖字段保存在“其他配置 YAML”，避免未来 Homepage 新增字段被可视化编辑器丢弃。

## v0.4.6 页面设置工作区

- 页面设置按“基础 / 外观 / 行为 / Quick Launch / 分组布局 / 高级”重新组织，并提供页内导航。
- 补齐 Homepage 官方常用 `settings.yaml` 表单：`startUrl`、`base`、`boxedWidgets`、完整色板、`bookmarksStyle`、全局等高、折叠、统计、错误隐藏、更新检查、禁止索引、最大分组列数等。
- Quick Launch 从单一 provider 输入框升级为完整表单，支持搜索描述、联网搜索、搜索建议、URL 访问、移动按钮位置和 Custom Provider。
- 背景 blur 使用明确的“未配置 / `blur: ""` / xs...3xl”选择，不再让空字符串语义依赖文本框；同时提示 `cardBlur` 与背景滤镜冲突。
- 分组布局自动汇总服务与书签分组，未配置组不会在无操作保存时被强制写入；支持拖动手柄调整 `layout:` 顺序。
- 页面设置新增保存前 Diff 预览，敏感字段继续掩码，确认后才写入并创建备份。
- 高级字段继续保留 YAML 入口，Providers、PWA、blockHighlights 及未来 Homepage 新字段不会被表单覆盖。

## v0.4.5 优化

- 服务新增/编辑页的 Docker 集成改为基于 Docker 发现的“主机 + 容器”选择器。
- Proxmox VM/LXC 集成改为基于 Proxmox 发现的“连接 + VM/LXC”选择器。
- 未配置对应发现连接时，集成区域会禁用并给出配置入口；编辑已有服务时会保留原配置。
- 新增只读 API 为表单动态加载 Docker 容器与 Proxmox 资源，不向浏览器暴露 Header、Token 或 Secret。
- 对用户可见的占位符、示例 IP、节点名和分组提示做开源友好化，改用通用名称与 TEST-NET 示例地址。
- Docker/Proxmox 下拉控件使用统一行高与帮助文字区域。

## v0.4.4 优化

- Docker 主机表单按钮文案统一为“测试连接”，右上角“取消编辑”改为轻量胶囊按钮。
- Docker Server 当前没有任何服务引用时允许安全重命名；有引用时继续锁定并说明引用数量。
- 重命名会同步迁移 `docker.yaml` 键名与 Admin-only 元数据，连接配置仍只有 `docker.yaml` 一份。
- Docker 发现页对已加入 Homepage 的容器提供“编辑服务 / 移除配置”；移除仅删除服务的 `server` / `container`，不会删除服务、Widget 或链接。
