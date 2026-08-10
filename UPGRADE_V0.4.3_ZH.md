# Homepage Admin v0.4.3 升级说明

v0.4.3 重构 Docker 多主机配置模型，目标是避免同一台 Docker 主机同时在 `/config/docker.yaml` 与 `/data/admin-settings.json` 保存两份连接信息。

## 新模型

### `/config/docker.yaml`：唯一 Docker 连接源

这里保存 Homepage 和 Homepage Admin 都需要的真实连接信息：

```yaml
local-docker:
  host: homepage-docker-proxy
  port: 2375
  protocol: http

game-server:
  host: 192.0.2.20
  port: 2375
  protocol: http
```

Server 名称、Host、Port、Protocol、Socket、TLS、Header 都只在这里维护。

### `/data/admin-settings.json`：Admin 专属元数据

例如：

```json
{
  "docker_host_metadata": {
    "game-server": {
      "display_name": "Game-Server VM",
      "public_host": "192.0.2.20"
    }
  }
}
```

这里不再复制 `homepage_server`、Docker API URL、Host、Port 或协议。

只有在 Admin 无法直接访问 `docker.yaml` 中的地址时，才额外保存：

```json
{
  "discovery_override": "http://192.0.2.10:2375"
}
```

## 自动迁移

首次启动 v0.4.3 时会读取旧版 `docker_discovery_hosts`：

- 如果旧 URL 与 `docker.yaml` 完全一致：删除重复 URL，只迁移显示名称 / Public Host。
- 如果旧 URL 与 `docker.yaml` 不同：把旧 URL 迁移为 `discovery_override`，保持特殊发现链路可用。
- 旧的 `docker_discovery_hosts` 键随后从 `admin-settings.json` 移除。

该迁移不会修改 `services.yaml`，也不会删除现有 Docker Server。

## 新增 / 编辑主机

普通情况下只填写：

- 显示名称
- Homepage Docker Server
- Docker API URL
- Public Host

保存后：

- Docker API 连接 → `docker.yaml`
- 显示名称 / Public Host → `admin-settings.json`

“Admin Discovery Override”默认留空。

## 删除主机

删除操作现在以 `docker.yaml` Server 为主体，并自动删除该 Server 的 Admin 元数据。若有服务引用，仍需输入 `DELETE`，并可选择同时清理服务中的 `server` / `container`。

## 升级步骤

1. 解压 `homepage-admin-v0.4.3-web-upload.zip`。
2. 覆盖上传 GitHub 仓库普通文件。
3. Commit：`Release v0.4.3`。
4. 等待 Actions 变绿。
5. Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。
6. `/healthz` 应显示 `0.4.3`。

Web Upload 包仍不包含 `.github`，现有成功的 Workflow 无需修改。
