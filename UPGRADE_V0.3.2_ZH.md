# Homepage Admin v0.3.2 升级说明

v0.3.2 把 Widget 中心从“人工维护的索引 / 少量专属表单”升级为 **Homepage 官方 Schema 驱动**。同时调整书签文案，并为长页面加入全局“回到顶部”。

## 1. 官方 Widget Schema 自动同步

v0.3.2 会从 Homepage 官方仓库读取：

- `docs/widgets/services/*.md`：Service Widget 官方文档、YAML 配置示例、Allowed fields。
- `src/widgets/widgets.js`：实际 Widget 注册表与兼容别名。

同步后，Admin 会把官方 YAML 示例自动转换为表单字段：

- 字符串 → 文本框
- true / false → 布尔下拉
- 数字 → 数字输入
- List / Mapping → YAML 编辑框
- password / token / secret / api key 等 → 密码输入框
- `Allowed fields` → 最多 4 项的显示字段复选框

已有 Jellyfin、Portainer、Proxmox、Home Assistant 等深度增强不会丢失，而是叠加在自动 Schema 上，继续提供更好的字段标签和深度连接测试。

## 2. 自动跟随 Homepage 新 Widget

默认设置：

```env
WIDGET_SCHEMA_AUTO_SYNC=true
WIDGET_SCHEMA_SYNC_INTERVAL_HOURS=24
WIDGET_SCHEMA_REF=master
WIDGET_SCHEMA_TIMEOUT=8
WIDGET_SCHEMA_WORKERS=10
```

Admin 启动后会在后台检查 Schema；成功同步后写入：

```text
/data/widget-schema-cache.json
```

以后 Homepage 官方增加、删除或调整 Service Widget，Admin 不需要发新版也可以在下次同步后更新目录和自动表单。

同步失败不会影响现有管理功能：Admin 会继续使用上一次成功缓存；如果从未成功同步，则使用内置离线目录。

## 3. Widget Schema 管理页

Widget 中心新增 **Schema 管理**：

- 查看来源仓库、Ref、最后同步时间。
- 查看官方文档数量、注册表数量、Widget 数量、自动字段数量。
- 查看同步解析警告。
- 手动“立即同步官方 Schema”。
- 清除 `/data` 缓存并恢复内置离线目录。
- 无法联网时可粘贴 Widget Schema JSON 进行离线导入。

GitHub Actions 在发布镜像前也会生成一次官方 Schema 快照并打进镜像，因此正常的 GHCR 发布版在首次启动时就有一份近期官方 Schema；运行中仍会继续自动同步。

## 4. 书签文案调整

系统默认描述从：

```text
管理 bookmarks.yaml 中的轻量链接和 PT 站点。
```

改为：

```text
管理 bookmarks.yaml 中的网站书签、快捷链接和分类。
```

新增 / 编辑书签页也不再把 PT 站点作为默认使用场景。

## 5. 全局“回到顶部”

滚动超过约 520px 后，右下角显示“↑ 回到顶部”。适用于 Widget 中心、Docker 发现、Proxmox 发现、服务管理、高级编辑等所有长页面；移动端显示为紧凑圆形按钮。

## 6. 升级方式

使用：

```text
homepage-admin-v0.3.2-web-upload.zip
```

覆盖 GitHub 仓库内容，Commit message：

```text
Release v0.3.2
```

**注意：v0.3.2 的 Web Upload 包包含 `.github/workflows/docker-publish.yml`。** 因为发布工作流新增“生成官方 Widget Schema 快照”步骤，所以这次请一起覆盖 `.github` 工作流。

等待 Actions 绿色后，在 Portainer 中重新拉取：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

不需要修改 HomePage Stack、`homepage-tools`、`homepage-docker-proxy`、PGID、`docker.yaml`，也不需要 MySQL。

## 7. 验证

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应包含：

```json
{"status":"ok","version":"0.3.2"}
```

进入 **Widget 中心 → Schema 管理**，确认：

1. Schema 已在线同步，或显示“bundled-official-schema”。
2. Widget 数量正常。
3. “自动生成字段”不为 0。
4. 搜索 Sonarr / Pi-hole / TrueNAS 等非原 15 个增强类型，进入“使用此 Widget”后应出现自动字段表单，而不是只让填写通用 YAML。
5. 滚到页面底部，右下角应出现“回到顶部”。
6. 书签管理页不再出现 PT 专用描述。
