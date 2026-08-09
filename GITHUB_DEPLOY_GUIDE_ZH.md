# GitHub + GHCR 部署指南（v0.2.4）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.2.4-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.2.4`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 会自动更新。
8. Portainer 更新 `homepage-admin` Stack 并重新拉取镜像。

## GitHub Actions 做什么

项目中的 `.github/workflows/docker-publish.yml` 会：

- 安装 Python 依赖
- 执行 pytest
- 构建 `linux/amd64` 和 `linux/arm64`
- 登录 GHCR
- 推送 `latest`
- 创建 Git Tag 时额外推送语义版本标签

例如创建 Tag `v0.2.4` 会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.2.4
ghcr.io/aspeternity/homepage-admin:0.2
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.2.4 特别注意

本次无需再次修改 Homepage Stack、`homepage-tools`、`homepage-docker-proxy`、PGID 或 `docker.yaml`。

如果 v0.2.3 已经因为保存页面设置导致背景滤镜变化，请先按照 `UPGRADE_V0.2.4_ZH.md` 从备份恢复 `settings.yaml`，再验收 v0.2.4 的无损保存。
