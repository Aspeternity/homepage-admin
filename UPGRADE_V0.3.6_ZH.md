# Homepage Admin v0.3.6 升级说明

v0.3.6 是 v0.3.5 的 UI 对齐与 Schema 同步体验修复版本。

## 主要变化

1. 自动生成 Widget 字段统一使用“字段标题 / 输入控件 / 帮助说明”布局；没有帮助说明的字段也保留不可见占位，因此 Backrest 等 Widget 同一行输入框保持水平对齐。
2. “立即同步官方 Schema”改为后台任务。页面会实时显示同步阶段、百分比和已解析文档数，不再只表现为浏览器长时间转圈。
3. 同步成功后自动刷新页面；失败时直接在进度区域显示错误，并可立即重试。

## 升级

解压 `homepage-admin-v0.3.6-web-upload.zip` 后覆盖上传 GitHub 仓库即可。Web Upload 包不包含 `.github`，现有 Workflow 无需修改。

Commit message 可使用：

```text
Release v0.3.6
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。升级后 `/healthz` 应显示 `0.3.6`。
