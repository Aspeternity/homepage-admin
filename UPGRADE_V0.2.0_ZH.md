# 从 v0.1.1 升级到 v0.2.0

## 1. 更新 GitHub 仓库源码

把 v0.2.0 项目文件覆盖上传到现有 `Aspeternity/homepage-admin` 仓库的 `main` 分支。

必须确认以下文件存在：

```text
.github/workflows/docker-publish.yml
app/docker_client.py
app/docker_proxy.py
app/secrets.py
app/widget_catalog.py
docker-compose.ghcr.yml
```

提交后进入 **Actions**，等待最新的 **Test and publish Docker image** 变成绿色。

## 2. 确认 GHCR 更新

Actions 成功后，`ghcr.io/aspeternity/homepage-admin:latest` 会指向新镜像。

Docker VM 可以验证：

```bash
docker pull ghcr.io/aspeternity/homepage-admin:latest
```

## 3. Portainer 更新 Stack

v0.2.0 为 Docker 容器发现增加了第二个 sidecar，因此不能只 Recreate 原来的单容器 Stack。

进入：

```text
Portainer → Stacks → homepage-admin → Editor
```

把 Stack 内容替换为项目中的 `docker-compose.ghcr.yml`。

保留你现有的 `ADMIN_PASSWORD`、`SESSION_SECRET` 和正确的 `HOMEPAGE_URL`。

然后点击 **Update the stack**，并选择重新拉取镜像（Re-pull image）后部署。

## 4. 验证

应该出现两个容器：

```text
homepage-admin
homepage-admin-docker-proxy
```

检查：

```bash
docker ps --filter name=homepage-admin
```

打开：

```text
http://192.0.2.10:3001
```

左侧应新增“Docker 发现”。

## 5. 配置 Homepage 的 Docker server

你的 Homepage 容器已经挂载：

```text
/var/run/docker.sock -> /var/run/docker.sock
```

如果 `docker.yaml` 仍为空，在 Homepage Admin → Docker 发现 中点击：

```text
创建 local-docker
```

后台会生成：

```yaml
---
local-docker:
  socket: /var/run/docker.sock
```

以后从 Docker 发现导入的服务可以自动使用 `server: local-docker` 和 `container: 容器名`。
