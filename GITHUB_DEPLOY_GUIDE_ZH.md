# GitHub + GHCR 部署指南（v0.2.1）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.2.1-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.2.1`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 会自动更新。
8. Portainer 更新 Stack 并重新拉取镜像。

## GitHub Actions 做什么

项目中的 `.github/workflows/docker-publish.yml` 会：

- 安装 Python 依赖
- 执行 pytest
- 构建 `linux/amd64` 和 `linux/arm64`
- 登录 GHCR
- 推送 `latest`
- 创建 Git Tag 时额外推送语义版本标签

例如创建 Tag：

```text
v0.2.1
```

会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.2.1
ghcr.io/aspeternity/homepage-admin:0.2
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.2.1 特别注意

v0.2.1 的 Docker 结构与 v0.2.0 不同。不要只 Recreate `homepage-admin`；请使用项目中的：

```text
docker-compose.portainer.yml
```

并严格按照：

```text
UPGRADE_V0.2.1_ZH.md
```

完成 `homepage-tools` 共享网络和 Homepage 本体的 Proxy 迁移。
