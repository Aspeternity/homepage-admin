# Homepage Admin v0.3.5 升级说明

v0.3.5 是 v0.3.4 的小型 UI / Schema 校验修复版本。

## 修复内容

1. **自动同步计划对齐**：计划时区输入框不再因为下方 IANA 时区说明文字而被向上顶起，与同步方式、每天同步时间保持同一水平。
2. **Home Assistant custom 改为可选**：Homepage 官方文档说明 `custom` 用于最多 4 个自定义 state/template，并未要求必须配置；未填写时连接测试不再报“缺少必填字段”。
3. **更安全的必填推断**：自动 Schema 不再把官方示例中的每个未注释字段都当成必填。只有官方 inline comment 明确出现 `required`、`mandatory` 或“必填”时才自动标记；已有人工作为深度增强的 Widget 仍由 Admin 的专属规则验证 URL、Token 等确实需要的字段。
4. **旧缓存兼容**：升级后即使 `/data/widget-schema-cache.json` 还是 v0.3.4 生成的，也会在加载时清除旧的错误 required 推断，再叠加专属规则，不要求手动清缓存。

## Home Assistant 官方行为

Home Assistant Widget 的核心配置仍是 `url` 与长期访问令牌 `key`。`custom` 仅在需要自定义实体状态或模板时填写，最多 4 项；当 `fields` 被设置时，Homepage 会忽略 `custom`。

## 升级

解压 `homepage-admin-v0.3.5-web-upload.zip` 后覆盖上传 GitHub 仓库即可。Web Upload 包不包含 `.github`，现有已通过的 Workflow 无需修改。Commit message 可使用：

```text
Release v0.3.5
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest` 并更新 Stack。HomePage、Docker Proxy、共享网络、MySQL 均无需改动。

升级后 `/healthz` 应显示 `0.3.5`。
