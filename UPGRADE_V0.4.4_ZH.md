# Homepage Admin v0.4.4 升级说明

v0.4.4 继续完善 v0.4.x 的多 Docker 主机统一管理。

## 本次优化

1. Docker 主机表单中的“先测试连接”改为“测试连接”。
2. 编辑态右上角“取消编辑”改为更轻量的胶囊按钮。
3. **安全重命名 Docker Server**：
   - 当前没有任何 `services.yaml` 服务引用该 Server 时，`Homepage Docker Server` 输入框可以修改。
   - 保存后同步重命名 `docker.yaml` 键名，并迁移对应的 Admin 显示元数据。
   - 如果当前仍被服务引用，输入框保持只读，并明确显示引用数量；后端也会再次校验，防止旧页面误改名。
4. **Docker 发现支持移除配置**：
   - 已加入 Homepage 的容器不再只有“已在 services.yaml”。
   - 每个匹配服务显示“编辑服务 / 移除配置”。
   - “移除配置”只删除该服务的 `server` 和 `container`，不会删除服务、Widget、href、图标或描述。
   - 如果同一容器被多个服务引用，会逐条显示，每一条都可以独立移除。

## 升级

解压 `homepage-admin-v0.4.4-web-upload.zip`，覆盖上传 GitHub 仓库普通文件即可。Web Upload 包不包含 `.github`。

Commit message 建议：

```text
Release v0.4.4
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.4.4`。
