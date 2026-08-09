# Homepage Admin v0.3.3 升级说明

v0.3.3 是 Widget Schema 同步热修复。v0.3.2 的构建工作流已经改为从 Homepage 官方 `dev` 分支生成内置 Schema，但运行时默认 `WIDGET_SCHEMA_REF` 仍误写为 `master`，因此“立即同步官方 Schema”和后台自动同步会请求不存在的 `?ref=master` 并返回 HTTP 404。

## 修复内容

- 运行时默认 `WIDGET_SCHEMA_REF=dev`。
- `app/widget_catalog.py` 所有 fallback ref 统一为 `dev`。
- `scripts/sync_widget_schema.py` 默认 `--ref dev`。
- GitHub Actions 构建内置 Schema 使用 `--ref dev`，且不向外部 Homepage 仓库发送当前仓库作用域的 `GITHUB_TOKEN`。
- `.env.example` 与升级文档同步改为 `dev`。
- 新增回归测试。

## 升级

如果你的 Portainer Stack 曾手工设置 `WIDGET_SCHEMA_REF=master`，请删除该变量或改成：

```text
WIDGET_SCHEMA_REF=dev
```

如果没有设置过该变量，升级 v0.3.3 后无需新增任何环境变量。

更新镜像后验证：

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应显示版本 `0.3.3`。随后进入 **Widget 中心 → Schema 管理 → 立即同步官方 Schema**，错误 URL 中不应再出现 `ref=master`。
