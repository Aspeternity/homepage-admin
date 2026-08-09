# Homepage Admin v0.3.1 升级说明

v0.3.1 是 v0.3.0 的 Widget 中心修复版，不要求修改 HomePage、Docker Proxy、共享网络或 MySQL。

## 修复内容

1. 修复 Widget 中心底部空状态始终可见。
2. Widget 中心扩展为 Homepage 当前官方 Service Widget 全索引，而不是只有 15 个预置模板。
3. 15 个常用 Widget 继续使用增强专属表单；其他官方 Widget 可搜索并通过“Widget 其他配置（YAML 映射）”配置。
4. 修正 NGINX Proxy Manager 的 Widget type 为 `npm`。

## 升级

使用 `homepage-admin-v0.3.1-web-upload.zip` 覆盖 GitHub 仓库内容，Commit message 可用：

```text
Release v0.3.1
```

等待 GitHub Actions 发布 `ghcr.io/aspeternity/homepage-admin:latest` 后，在 Portainer 中重新拉取并更新 Homepage Admin 容器即可。

## 验证

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应包含：

```json
{"status":"ok","version":"0.3.1"}
```

进入 Widget 中心后：

- 未搜索时不应出现空状态提示。
- 应显示 150+ 个官方索引项。
- 搜索 `sonarr`、`truenas`、`adguard`、`zabbix`、`seerr` 均应有结果。
- NGINX Proxy Manager 的 type 应显示为 `npm`。
