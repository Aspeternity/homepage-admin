# GitHub + GHCR 部署指南（v0.4.1）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.4.1-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.4.1`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 会自动更新。
8. Portainer 更新 `homepage-admin` Stack 并重新拉取镜像。

## GitHub Actions 做什么

`.github/workflows/docker-publish.yml` 会：

- 安装 Python 依赖
- 执行 pytest
- 从 Homepage 官方仓库生成 Widget Schema 快照
- 构建 `linux/amd64` 和 `linux/arm64`
- 登录 GHCR
- 推送 `latest`
- 创建 Git Tag 时额外推送语义版本标签

例如创建 Tag `v0.4.1` 会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.4.1
ghcr.io/aspeternity/homepage-admin:0.4
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.4.1 特别注意

升级本身无需修改现有 Homepage Stack、`homepage-tools`、主 Docker VM 的 `homepage-docker-proxy`、PGID 或 MySQL。只有在新增 Game-Server VM 等额外 Docker 主机时，才需要为目标 VM 提供只读 Docker API，并可由 Admin 创建对应的 `docker.yaml` Server。

升级后建议重点验收：

- Docker 发现 → “全部 Docker 主机”
- Docker 主机管理 → 连接测试
- 同名容器跨主机的“已添加”识别
- 从不同 Docker 主机导入服务时 `server` 是否正确
- 原有 Widget / Proxmox / Diff 功能回归
