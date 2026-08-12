# GitHub + GHCR 部署指南（v0.5.3）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 部署模型

v0.5.3 起默认部署只需要一个 `homepage-admin` 容器：

```text
homepage-admin
├── /config -> Homepage 配置目录
└── /data   -> Admin 持久化数据
```

不要求：

```text
共享 Docker Network
Docker Socket
Docker Socket Proxy
与 Homepage 容器互联
```

Docker 发现属于可选功能。如需使用，在目标 Docker 主机单独部署只读 Socket Proxy，再通过 IP / DNS 从“Docker 主机管理”添加即可。

仓库提供：

```text
docker-compose.ghcr.yml
docker-compose.portainer.yml
docker-compose.docker-proxy.example.yml
.env.example
```

详细说明见 `README.md`。

## 日常升级流程

1. 解压 `homepage-admin-v0.5.3-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 上传解压后的普通项目文件进行覆盖。
4. Commit message：`Release v0.5.3`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 自动更新。
8. Portainer / Docker Compose 重新拉取 `homepage-admin` 镜像。

## GitHub Actions

`.github/workflows/docker-publish.yml` 会执行测试、生成 Widget Schema 快照、构建 `linux/amd64` 与 `linux/arm64` 并推送 GHCR。

创建 Tag `v0.5.3` 时，会生成类似：

```text
ghcr.io/aspeternity/homepage-admin:0.5.3
ghcr.io/aspeternity/homepage-admin:0.5
ghcr.io/aspeternity/homepage-admin:latest
```
