# Homepage Admin v0.4.0 升级说明

v0.4.0 将 Docker 发现从“单一 Docker API 端点”升级为“多 Docker 主机发现与导入”。Homepage 官方本身允许 `docker.yaml` 配置多个 Docker 实例，并在服务中通过 `server` + `container` 指向对应实例；本版本让 Admin 的发现流程与这套模型对齐。

## 主要变化

- Docker 发现支持“全部 Docker 主机”与单主机切换。
- 自动读取 `docker.yaml` 中所有 `host + port` Server 并作为发现源；`protocol: https`、`headers`、TLS 文件连接也会由服务端读取，不向浏览器暴露 Header 内容。
- 新增 **Docker 主机管理**：添加 / 编辑 / 删除 Admin 自定义发现连接、测试连通性、映射 Homepage Docker Server。
- Admin 自定义主机保存在 `/data/admin-settings.json`；Homepage YAML 继续是 Homepage 配置的唯一事实来源。
- 添加自定义主机时可勾选“若 docker.yaml 没有同名 Server，则同时创建”。如果已存在同名但地址不同，Admin 会拒绝覆盖，避免破坏 TLS / Header 配置。
- 容器卡片显示来源 Docker 主机与 Homepage `server`。
- 同名容器现在按 `(server, container)` 匹配，不会因为另一台 Docker 主机也有同名容器而误判“已添加”。
- 导入向导把来源主机带到完整流程，并强制使用该主机映射的正确 `server`。
- 支持容器搜索、运行状态筛选、“已添加 / 未添加”筛选。
- 旧版 `/docker/import/<container>` 链接保留兼容，会转到第一个可用 Docker 主机。

## 你的当前主 Docker VM

如果现有 `docker.yaml` 已经是：

```yaml
local-docker:
  host: homepage-docker-proxy
  port: 2375
```

v0.4.0 会自动把它识别为一个 Docker 主机，不需要重新配置，也不需要修改当前 `homepage-tools` 网络。

## 给 Game-Server VM 增加只读 Docker Proxy

在 Game-Server VM 上推荐继续使用只读 Socket Proxy：

```yaml
services:
  docker-proxy:
    image: ghcr.io/tecnativa/docker-socket-proxy:latest
    container_name: game-docker-proxy
    restart: unless-stopped
    environment:
      CONTAINERS: "1"
      PING: "1"
      SERVICES: "1"
      TASKS: "1"
      POST: "0"
    ports:
      - "2375:2375"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

如果 2375 必须暴露到局域网，请在 Game-Server VM 防火墙中只允许 Homepage Admin 所在 Docker VM 的 IP 访问，不要把未加密的 Docker API 暴露到互联网。

然后进入：

```text
Homepage Admin
→ Docker 发现
→ Docker 主机管理
→ 添加 Docker 主机
```

示例：

```text
连接 ID: game-server
显示名称: Game-Server VM
Discovery URL: http://<GAME-VM-IP>:2375
Homepage Docker Server: game-server
Public Host: <GAME-VM-IP>
```

勾选“若 docker.yaml 没有同名 Server，则同时创建”，保存后 `docker.yaml` 会新增：

```yaml
game-server:
  host: <GAME-VM-IP>
  port: 2375
```

之后从 Game-Server VM 导入的容器会自动写：

```yaml
server: game-server
container: <容器名称>
```

而 Docker VM 上的容器仍使用：

```yaml
server: local-docker
```

## 升级

解压 `homepage-admin-v0.4.0-web-upload.zip`，覆盖上传 GitHub 仓库普通文件即可。Web Upload 包继续不包含 `.github`，现有成功 Workflow 不需要修改。

Commit message 建议：

```text
Release v0.4.0
```

Actions 绿色后，在 Portainer 重新拉取：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

更新后 `/healthz` 应返回版本 `0.4.0`。

## 数据与兼容性

- 不需要 MySQL。
- 不迁移或删除现有服务。
- 不会自动删除 `docker.yaml` Server。
- 删除 Admin 自定义 Docker 主机时，只删除 `/data/admin-settings.json` 中的发现连接，不删除 Homepage 的 `docker.yaml`。
