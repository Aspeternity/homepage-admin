# GitHub + GHCR 部署指南（v0.5.1）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 推荐部署

GitHub 首页 `README.md` 已提供完整的 GHCR + Docker Compose + 只读 Docker Socket Proxy 部署示例，建议新用户直接按 README 的“Docker 部署”章节操作。

项目仓库同时保留：

```text
docker-compose.ghcr.yml
docker-compose.portainer.yml
.env.example
```

用于快速部署或 Portainer Stack。

## 日常升级流程

1. 解压 `homepage-admin-v0.5.1-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的项目内容拖进去覆盖。
4. Commit message：`Release v0.5.1`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 自动更新。
8. Portainer / Docker Compose 重新拉取 `homepage-admin` 镜像。

## GitHub Actions

`.github/workflows/docker-publish.yml` 会：

- 安装 Python 依赖；
- 执行 pytest；
- 从 Homepage 官方仓库生成 Widget Schema 快照；
- 构建 `linux/amd64` 和 `linux/arm64`；
- 推送 GHCR `latest` / 版本 / sha 标签。

创建 Tag `v0.5.1` 时，会生成类似：

```text
ghcr.io/aspeternity/homepage-admin:0.5.1
ghcr.io/aspeternity/homepage-admin:0.5
ghcr.io/aspeternity/homepage-admin:latest
```
