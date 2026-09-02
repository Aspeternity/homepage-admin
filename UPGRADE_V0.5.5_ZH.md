# Homepage Admin v0.5.5 升级说明

v0.5.5 是面向 Homepage 2.x 的兼容性更新，当前按 Homepage v2.2.0 官方行为适配。

## 主要变化

- 新增「Homepage 兼容性」页面：Docker 只读自动识别 + 手动版本覆盖、官方最新 Release 检查、v2.1.1 YAML 解析问题警告。
- 新增 Homepage Password Auth / OIDC Compose 配置生成器。
- 新增 Homepage MCP Compose 配置生成器，默认只读，可选择允许写入。
- Widget Schema 同步后新增 Schema Diff：新增/移除 Widget、配置字段、Allowed fields 变化一目了然。
- 新 Widget 分类优化：Maintainerr / Sportarr → 媒体，Syncthing / Duplicati → 存储，Pulse → 监控。
- Jellyfin 增加 `albums` 显示字段；qBittorrent 增加 API Key 表单字段。
- Pulse、Dockhand、Authentik、Arcane 增加 Homepage 2.x 相关帮助提示。
- 编辑 `custom.css` 时增加安全提醒：Homepage 2.x 启用认证后 `custom.css` 仍可被未登录访问。
- Custom API Widget 检测到 `highlight:` 时给出兼容性警告。

## 升级方式

继续使用原有 `/config` 与 `/data` 挂载即可，无需迁移数据：

```bash
docker compose pull
docker compose up -d
```

v0.5.5 不要求增加任何 Docker 权限，也不要求修改现有只读 Docker Socket Proxy。

## Homepage 版本说明

- Homepage v2.0.0 起支持内置密码认证、OIDC 与 MCP。
- Homepage v2.1.1 存在官方已知 YAML 解析问题，建议升级到 v2.1.2 或更高版本。
- v0.5.5 当前兼容基线为 Homepage v2.2.0；若检测到更高版本，Admin 会建议先同步官方 Widget Schema 并检查 Release Notes。
