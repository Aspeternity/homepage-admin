# GitHub + GHCR 部署指南（v0.5.0）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.5.0-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.5.0`。
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

例如创建 Tag `v0.5.0` 会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.5.0
ghcr.io/aspeternity/homepage-admin:0.4
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.5.0 特别注意

升级不要求修改现有 Homepage YAML、Docker、Proxmox 或网络配置。`/data/backups` 里的旧版备份会继续兼容读取。

升级后建议重点验收：

- 备份中心能读取旧备份并显示为兼容模式
- “立即创建完整快照”能一次保存当前全部 Homepage 配置
- “对比当前”不会显示真实 Token、Password 或 API Key
- 多文件快照执行“恢复全部”前会自动创建受保护的恢复前保护点
- 自动备份保留上限不会删除手动快照和受保护备份
