# Changelog

## v0.5.3 - 2026-08-12

- 新增首次运行初始化：未配置管理员账号时，第一次访问自动进入 `/setup` 创建用户名和密码。
- 管理员密码只保存 bcrypt 哈希到 `/data/auth.json`，不再要求在 Compose / `.env` 中保存明文凭据。
- Session Secret 自动生成并持久化到 `/data/auth.json`，默认 Compose 不再要求 `SESSION_SECRET`。
- 兼容旧版 `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_PASSWORD_HASH`：首次启动自动迁移到持久化认证文件，旧环境变量可随后删除。
- Docker Compose 再次精简为端口 + Homepage `/config` 挂载 + `/data` Named Volume；默认不再要求 `.env`、PUID/PGID 或安全选项堆叠。
- 新增首次初始化安全提示，并将 `/data` 明确为账号、Session、备份和 Admin 设置的持久化位置。

## v0.5.2 - 2026-08-12

- 将默认 Docker 部署简化为单个 `homepage-admin` 容器，只要求挂载 Homepage `/config` 与 Admin `/data`。
- 默认 Compose 不再创建或依赖 `homepage-tools` 等共享 Docker Network，也不再强制部署 `docker-socket-proxy`。
- Docker 发现明确改为可选集成：通过 `docker.yaml` / Docker 主机管理连接目标主机的 HTTP(S) API。
- 新增独立 `docker-compose.docker-proxy.example.yml`，仅供需要 Docker 发现时在目标 Docker 主机部署只读 Proxy。
- `docker-compose.ghcr.yml`、`docker-compose.portainer.yml`、源码 `docker-compose.yml` 与 `.env.example` 全部同步精简。
- README 重写快速部署章节，明确多 Docker 主机通过 IP / DNS 访问，不需要跨主机或共享 Docker Network。
- 保留旧 `DOCKER_DISCOVERY_URL` 等环境变量的运行时兼容逻辑，现有共享网络部署无需强制迁移。

## v0.5.1 - 2026-08-12

- 重构 GitHub 首页 README，改为面向新用户的项目介绍、架构、功能总览和快速开始，而不是在首页堆叠历史版本说明。
- 新增推荐 Docker Compose 部署示例：GHCR 镜像、共享网络、持久化目录与只读 Docker Socket Proxy。
- 新增无 Docker 发现的最小部署示例，以及多 Docker 主机只读代理部署示例。
- README 增加 Proxmox 多节点、备份、安全、升级、源码运行和常见配置说明。
- 新增 Homepage Admin 1:1 项目图标资源 `docs/assets/homepage-admin.png`，用于 GitHub 首页品牌展示。
- 本版本以文档与开源首页体验优化为主，不改变现有 Homepage 配置数据模型。

## v0.5.0 - 2026-08-10

- 将“备份回滚”升级为“备份中心”，增加统计概览、搜索与类型/文件筛选。
- 新增手动完整配置快照，一次备份全部 Homepage 配置文件；手动快照不受自动备份数量上限清理。
- 自动备份新增元数据清单，记录时间、来源操作、操作者、类型和备注；旧版备份继续兼容。
- 支持备份保护/取消保护；受保护备份不会被自动清理、批量清理或直接删除。
- 新增 ZIP 导出，可离线保存单个备份/快照。
- 新增恢复前 Diff，YAML 敏感字段继续掩码，不在浏览器中暴露 Token/Password。
- 多文件快照支持“恢复全部”，恢复前自动创建并锁定一个完整保护点。
- 自动保留上限现在只作用于普通自动备份，不会误删手动快照和恢复保护点。

## v0.4.9 - 2026-08-10

- Proxmox 发现筛选栏改为“搜索 / 类型 / 状态”三列同一行布局；中小屏幕仍按响应式规则自动堆叠。

## v0.4.8 - 2026-08-10

- Proxmox 发现升级为多节点聚合视图，支持“全部节点”与单节点切换，并按物理节点 + VMID + 类型去重。
- 新增 Proxmox 节点管理：新增、编辑、测试、删除连接，`proxmox.yaml` 保持唯一连接配置源。
- 节点名无服务引用时可安全重命名；有引用时锁定，并在删除前扫描 `services.yaml` 依赖。
- 删除节点可选择同时清除服务中的 `proxmoxNode` / `proxmoxVMID` / `proxmoxType`，服务和 Widget 本身保留。
- 新增“补齐集群节点”：从任一可用连接读取 PVE `/nodes`，为同一 Cluster 缺失的物理节点自动复制 URL / Token / Secret。
- Proxmox 发现增加名称/VMID/节点搜索、QEMU/LXC 类型筛选与运行状态筛选。
- 多个 `proxmox.yaml` 节点共享同一 Cluster URL 时，Admin 聚合发现只请求一次该 URL，避免重复 API 请求；独立 Cluster 仍并行读取。

## v0.4.7 - 2026-08-10

- 顶部组件升级为完整 Information Widget 可视化工作区。
- 新增 12 个当前官方 Info Widget 的目录、搜索、分类、官方文档与专属表单。
- 支持 Search 多 Provider/Custom、Resources/Glances 多磁盘、DateTime 常用 Intl 格式、天气、Stocks、UniFi、Kubernetes 与 Longhorn 专属配置。
- 增加 providers / kubernetes 前置条件提示，同时保持高级 YAML 与未来字段兼容。
- 未知 Info Widget 继续支持完整 YAML，并保留旧版 POST 字段兼容。

## v0.4.6 - 2026-08-10

- 重构页面设置为分区式可视化工作区，并加入页内导航与官方文档入口。
- 补齐常用 settings.yaml 字段与官方枚举，包括 boxedWidgets、完整色板、页面行为及 Quick Launch 选项。
- 背景 blur 改为显式状态选择，保留 Homepage 有意义的 `blur: ""`，并增加 cardBlur 冲突提示与背景预览。
- 分组布局支持拖动重排；未配置但自动发现的分组保持“建议态”，无操作保存不会写入空 layout。
- 新增 `/api/settings/preview` 保存前 Diff，Providers 等敏感值只显示掩码。
- 保留未知顶层、quicklaunch、background 与 layout 扩展字段，避免可视化保存破坏未来 Homepage 配置。

## v0.4.5 - 2026-08-10

- 新增服务页的 Docker 与 Proxmox 运行状态集成改为发现驱动的选择器。
- 未配置 Docker/Proxmox 发现时禁用相应集成并提示配置入口。
- 增加 Docker 容器与 Proxmox VM/LXC 的只读动态选项 API。
- 清理用户相关节点名、私网 IP 与自定义分组示例，改用通用开源示例。
- Compose 示例默认通过 `HomePage:3000` 访问同网络 Homepage，`DOCKER_PUBLIC_HOST` 默认留空等待部署者显式配置。

## v0.4.4 - 2026-08-10

- Docker 主机“先测试连接”改为“测试连接”，并美化编辑态取消按钮。
- 无服务引用的 Docker Server 支持安全改名；有引用时继续锁定。
- Docker 发现页为已配置容器增加可逆的“编辑服务 / 移除配置”。
- 移除配置仅清理 `server` / `container`，保留服务及其 Widget/URL。

## v0.4.3 - 2026-08-10

- Docker 主机连接改为 Single Source of Truth：`docker.yaml` 唯一保存 Server / Host / Port / Protocol / Socket / TLS / Header。
- `admin-settings.json` 的 Docker 数据缩减为显示名称、Public Host 和可选 Discovery Override，不再复制连接 URL / Server。
- 自动迁移 v0.4.0-v0.4.2 的 `docker_discovery_hosts`；与 `docker.yaml` 相同的旧 URL 会去重，仅不同地址保留为 Override。
- Docker 发现默认直接读取 `docker.yaml`；新增 / 编辑主机只更新该文件的连接字段，并单独保存 Admin 元数据。
- 删除 Docker Server 时自动清理孤立 Admin 元数据，同时继续提供服务引用检查与可选清理。
- Docker 主机编辑器增加可折叠的 Admin Discovery Override 高级项。

## v0.4.2 - 2026-08-10

- Docker 发现主页移除重复的 Docker 主机状态卡。
- Docker 主机管理统一新增/编辑流程，不再按 docker.yaml 原生 Server 与 Admin 自定义连接使用两套表单。
- 添加主机时始终同步创建或更新 docker.yaml Server，移除“若 docker.yaml 没有同名 Server，则同时创建”复选框。
- 统一表单保存时保留现有 TLS、Header 与未知 docker.yaml 扩展键。
- 删除向导默认完整移除发现设置与 docker.yaml Server，并保留服务引用保护。

## v0.4.1 - 2026-08-10

- Docker 主机管理统一 CRUD：`docker.yaml` 原生 Server 也可可视化编辑与进入删除向导。
- 可视化编辑基础连接字段并原样保留 TLS、Header 与未知扩展键，敏感 Header 不回显浏览器。
- 主机卡片显示 Server 的服务引用数量与预览。
- 新增安全删除向导，可独立删除 Admin 自定义发现连接、`docker.yaml` Server，并可选择清除引用服务的 Docker 关联。
- 删除被引用的 `docker.yaml` Server 必须输入 `DELETE`；仅删除 Admin 自定义层不要求确认词。
- 已映射 `docker.yaml` 的自定义主机编辑时锁定 Homepage Server 名称，降低误断引用风险。

## v0.4.0 - 2026-08-10

- Docker 发现升级为多主机：支持全部主机/单主机切换，并自动读取 `docker.yaml` 中多个远程 Server。
- 新增 Docker 主机管理：Admin 自定义发现 URL、映射 Homepage Server、连接测试、编辑、删除和安全同步到 `docker.yaml`。
- 同名容器改为按 `(server, container)` 判断是否已添加，避免多主机误匹配。
- Docker 导入向导携带来源主机并写入正确的 `server`，每个主机可独立配置 Public Host 用于发布端口 URL 推断。
- Docker 发现页新增主机来源标签、搜索、运行状态筛选、已添加/未添加筛选与独立主机错误状态。
- 保留 `DOCKER_DISCOVERY_URL` 作为兼容/回退连接；`docker.yaml` Socket 模式可通过 Admin 自定义只读代理覆盖发现。

## v0.3.9 - 2026-08-10

- 修复 Proxmox 发现页已关联卡片中“编辑服务”和“取消关联”按钮尺寸不一致。
- 统一两个操作项的 Grid 拉伸、表单 Flex 布局与 44px 最小高度，桌面端与移动端保持一致。

## v0.3.8 - 2026-08-10

- 修复服务编辑器 Proxmox VM/LXC 三列字段因帮助文字导致的纵向错位。
- Proxmox 发现页的已关联服务新增“取消关联”，与“编辑服务”并排显示。
- 新增 `/proxmox/unbind` 安全解绑：仅移除 Proxmox 映射，保留服务与 Widget，并校验绑定状态避免误解绑。

## v0.3.7 - 2026-08-10

- 修复 Proxmox 发现可成功但 Homepage per-VM 状态失败的配置差异：检测并一键移除 Proxmox URL 末尾 `/`。
- Proxmox Widget 导入连接时自动规范化 URL。
- VM/LXC 绑定使用 PVE 返回的真实节点名，并对缺少同名 `proxmox.yaml` 连接的节点显示警告、阻止错误绑定。
- 检测同一服务同时配置 Docker 与 Proxmox；绑定时可清除 Docker 集成，已绑定服务也支持一键清理。
- 服务编辑页增加 Docker + Proxmox 双重集成警告。

## v0.3.6 - 2026-08-10

- 修复自动生成 Widget 字段因帮助文字有无不一致导致的视觉错位。
- 手动 Schema 同步新增后台任务、真实阶段进度、百分比与文档计数。
- 同步期间按钮禁用并显示“同步中…”，成功后自动刷新，失败时原地显示错误。

## v0.3.5 - 2026-08-10

- 修复 Widget Schema 自动同步计划中“计划时区”输入框与同排控件垂直不齐的问题。
- 修复 Home Assistant `custom`（自定义状态 / 模板）被错误标记为必填，导致连接测试误报。
- Schema Parser 改为保守判定必填：官方 YAML 示例中的字段不再仅因“出现在示例里”就视为必填；只有官方注释明确标记 required / mandatory / 必填时才自动标记。
- 对旧版 Schema 缓存做兼容归一化：清除历史自动推断的 required 标记，再叠加 Admin 已知的专属必填规则。
- Home Assistant `custom` 增加“可选”说明，并提示最多 4 项以及设置 `fields` 时 `custom` 不生效。

## v0.3.4 - 2026-08-10

- Schema 时间在浏览器按本地时区显示，同时保留 UTC 作为内部标准。
- 自动同步支持后台开关、固定间隔、每天固定时间和 IANA 时区。
- 自动同步设置持久化到 `/data/admin-settings.json`，无需重启生效。
- Schema / Service 页面删除固定旧版本号文案。
- Docker 镜像加入 `tzdata`。

## v0.3.3 - 2026-08-10

- Fix Widget Schema runtime synchronization default ref from obsolete `master` to Homepage upstream `dev`.
- Align runtime, CLI sync script, `.env.example`, fallback metadata, and GitHub Actions on the same `dev` ref.
- Keep build-time cross-repository sync unauthenticated instead of sending this repository's scoped `GITHUB_TOKEN`.
- Add regression coverage so manual / automatic Schema sync cannot silently fall back to `master`.

## v0.3.2 - 2026-08-10

- 新增 Homepage 官方 Widget Schema 同步引擎：解析官方 Service Widget 文档 YAML 示例、Allowed fields 与 `src/widgets/widgets.js` 注册表。
- 官方同步成功后，所有可解析 Service Widget 自动生成增强表单，不再只有 15 个手工增强类型。
- 自动识别文本、布尔、数字、YAML、Secret 字段，并把官方 Allowed fields 转换为可视化选择。
- 同一官方文档存在多个 YAML 示例时会合并字段，避免遗漏版本或可选配置。
- 现有 15 个深度增强 Widget 改为叠加层：保留深度测试和专属标签，同时自动继承官方新增字段。
- 新增 `/data/widget-schema-cache.json` 持久缓存，默认每 24 小时后台同步；失败时继续使用上次缓存 / 内置目录。
- 新增 Widget Schema 管理页，可查看同步状态、立即同步、查看解析警告、清除缓存，并支持离线导入 Schema JSON。
- GitHub Actions 发布镜像前生成官方 Schema 快照，GHCR 镜像自带近期官方 Schema。
- 成功同步后以上游注册表为权威，官方删除 / 废弃的 Widget 不会被旧手工索引永久保留。
- 书签管理默认文案去除 PT 专用描述，改为通用的网站书签、快捷链接和分类。
- 新增全局“回到顶部”按钮，长页面滚动后自动出现，并支持平滑回顶。
- Widget 自动字段显示官方示例中的 inline comment 帮助文本。

## v0.3.1 - 2026-08-09

- 修复 Widget 中心未筛选时仍显示“没有符合当前筛选条件的 Widget”的空状态问题。
- Widget 中心从 15 个增强模板扩展为完整官方 Service Widget 索引；未做专属表单的类型可搜索、可选择，并使用通用 YAML 配置。
- 保留 15 个常用 Widget 的增强专属表单、字段选择和连接测试能力。
- 修正 NGINX Proxy Manager 的 Widget type：`npm`。
- 通用官方 Widget 在编辑器中显示明确的“官方索引 / 通用 YAML”提示，避免出现空白字段区。

## v0.3.0 - 2026-08-09

### Widget 与服务编辑

- 新增 Widget 中心，可搜索、按分类过滤并从模板直接创建服务。
- Widget 编辑器改为元数据驱动，新增 Widget 类型通常只需扩展 `widget_catalog.py`。
- 一个服务支持多个 Service Widget；单个 Widget 保持 `widget:` 兼容，多 Widget 使用 `widgets:`。
- 对常用 Widget 提供可视化 `fields` 选择，最多选择 4 个展示字段。
- 编辑已有服务时敏感字段继续不回显；留空保存会复用旧值。

### 连接测试

- 服务 Widget 新增“测试连接”。
- Jellyfin、Portainer、Proxmox、Home Assistant、qBittorrent、Transmission、Glances、Custom API 提供 API 深度测试与可读错误信息。
- 其他已收录 HTTP Widget 提供基础连通测试；Minecraft / GameDig 提供配置校验。
- 已保存 Secret 可由服务端直接用于连接测试，不会重新发送到浏览器。

### Proxmox 发现

- 新增 Proxmox 发现页面，从 `proxmox.yaml` 读取连接并列出 QEMU / LXC、VMID、状态、CPU 与内存。
- 可把 VM/LXC 绑定到已有 Homepage 服务，或以资源信息预填新服务。
- 可从已有 Proxmox Service Widget 在服务端导入 `proxmox.yaml` 连接，无需再次暴露 Token Secret。

### 保存安全

- 服务编辑器新增保存前统一 Diff。
- 高级 YAML 编辑器新增保存前 Diff。
- Diff 中敏感字段始终掩码。
- 服务 / 高级 YAML 没有实际变化时不写文件、不创建备份。

### 架构

- v0.3.0 不引入 MySQL 依赖，Homepage YAML 继续作为唯一配置源；管理偏好使用现有 `/data` 持久化。
- 保持 v0.2.1 以来的共享只读 Docker Proxy 架构，无需重新迁移 HomePage Stack。

## v0.2.4 - 2026-08-09

### 修复

- 修复“页面设置”在没有任何修改时点击保存会删除 `background.blur: ""`，导致 Homepage 背景从模糊变为清晰的问题。
- 页面设置真正无变化时不再重写 `settings.yaml`，也不再生成无意义备份；原 YAML 注释、显式空值和格式因此不会被无故改写。
- 修复背景滤镜数值为 `0` 时在表单中被当成空值的问题，`saturate: 0` / `brightness: 0` / `opacity: 0` 可正确显示与保存。
- 修复 Docker 导入向导推荐不存在的 `sh-lskypro` / `sh-komari` / `sh-moviepilot` 图标别名；分别改用 `mdi-image-multiple`、`mdi-server-network`、`mdi-movie-open`。

### 体验改进

- Docker 导入向导卡片预览新增 `mdi-*` 图标预览支持，并保留 URL / `sh-*` 图标预览和失败回退。
- 保留 v0.2.3 的字段对齐、智能分组、服务识别置信度和可配置备份保留数量。

## v0.2.3 - 2026-08-09

### 新功能与体验

- Docker 导入向导字段统一纵向网格，修复“图标”和“访问地址”等输入框不在同一水平线的问题。
- 备份回滚页新增自动保留数量设置，可在 1–500 组之间调整并持久化到 `/data/admin-settings.json`。
- Docker 导入默认策略升级为按服务类型智能推荐现有分组，也可固定到指定分组。
- 导入向导显示“识别类型 + 置信度”，并增强卡片图标预览。

## v0.2.2 - 2026-08-09

### 新功能

- Docker 发现升级为导入向导：容器识别 → 建议调整 → 卡片/YAML 实时预览 → 完整编辑。
- 自动推荐常见容器的服务说明，并继续复用图标、Widget、发布端口、Homepage Labels 和默认分组推断。
- 桌面端主题切换从左下角大按钮移动到右上角紧凑图标，并新增浅色 / 深色 / 跟随系统三种模式。
- 备份回滚页面支持删除单个备份以及清空全部备份。
- 备份列表显示文件数量和占用空间，删除动作记录审计日志。

### 兼容性与安全

- 保持 v0.2.1 的 `homepage-tools` + `homepage-docker-proxy` 架构，不需要重新迁移 Docker 网络。
- Docker 导入向导只预览非敏感字段；Widget API Key / Password / Token 仍只在完整编辑器中录入。
- 备份删除接口继续要求登录、CSRF 校验与前端确认。
- `BACKUP_LIMIT` 自动清理机制继续保留。

## v0.2.1 - 2026-08-09

### 新功能

- 新增深色 / 浅色主题切换；登录页、桌面侧栏、移动端均可切换，并用浏览器 localStorage 记住偏好。
- Docker 发现页增加默认导入分组选择，避免无 Label 容器总是落到第一个 Widgets 分组。
- Docker 发现页增加共享只读代理状态、Socket 模式提示和一键迁移按钮。
- 已配置容器显示对应 Homepage 分组与服务名，并使用大小写不敏感的容器名匹配。
- Homepage 本体、Homepage Admin、Docker Proxy 增加角色标签；内部 Proxy 默认隐藏，可手动显示。

### 修复与体验

- 去重 Docker IPv4 / IPv6 导致的重复端口映射。
- 新增 Lsky-Pro / MkDocs 图标推断。
- 新建 docker.yaml 不再默认写入直接 socket，而是写入 `homepage-docker-proxy:2375`。

### 安全改进

- 新 Compose 改用 Homepage 官方文档推荐的 `ghcr.io/tecnativa/docker-socket-proxy:latest`。
- `CONTAINERS=1`、`PING=1`、`SERVICES=1`、`TASKS=1`、`POST=0`，不映射宿主机 2375 端口。
- Homepage 和 Homepage Admin 通过外部 `homepage-tools` 网络共享代理，Homepage 可移除直接 Docker Socket 挂载并恢复原 PGID。
- Admin 对原始 Docker API 返回的 Labels 继续进行敏感字段过滤后才进入页面数据。

## v0.2.0 - 2026-08-09

### 新功能

- 服务卡片、书签卡片继续支持跨分组拖动，并修正同组拖到末尾的排序逻辑。
- 服务分组、书签分组支持使用 `⋮⋮` 手柄直接拖动排序，并同步 `settings.yaml` 中的 layout 顺序。
- 顶部组件支持拖动排序。
- 新增常用 Homepage Service Widget 专属表单：Jellyfin、qBittorrent、Transmission、Minecraft、Home Assistant、Portainer、Proxmox。
- Widget 密钥/密码留空会保留旧值，不会在普通编辑表单中回显。
- 高级 YAML 编辑器默认遮挡 `key`、`password`、`token`、`secret` 等敏感字段；保存遮挡后的 YAML 时自动恢复原值。
- 高级编辑器提供显式的“临时显示敏感值”入口，并在显示前进行确认提示。
- 新增 Docker 容器发现页面，可读取容器名称、镜像、运行状态、发布端口及非敏感 Homepage Labels，并一键预填服务表单。
- 新增专用 Docker 发现 sidecar。主后台不直接挂载 Docker socket；sidecar 只暴露容器列表读取接口。
- Docker 发现页可在空 `docker.yaml` 中一键创建 `local-docker` socket 配置。
- GHCR 工作流增加 concurrency，同一分支的新构建会取消旧构建，避免旧任务晚完成覆盖 `latest`。

### 安全改进

- Docker 发现代理过滤 password / secret / token / authorization / `.key` 类标签，避免敏感 Label 进入主后台。
- Docker 代理不提供容器启动、停止、删除、exec 或任意 Docker API 转发接口。
- 高级编辑器默认不再把 Jellyfin API Key 等凭据直接显示在页面源代码中。
- 服务额外 YAML、顶部组件 YAML、settings.yaml 的 `providers` 等敏感值也默认遮挡；占位符使用独立签名令牌，并阻止被移动到普通字段。

### 兼容性

- 保持 v0.1.x 的 YAML、备份和审计目录格式。
- 不要求迁移现有 Homepage 配置。
- 不启用 Docker sidecar 时，除“Docker 发现”外的管理功能仍可继续使用。
