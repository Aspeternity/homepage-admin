# GitHub + GHCR 部署指南（v0.2.3）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.2.3-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.2.3`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 会自动更新。
8. Portainer 更新 `homepage-admin` Stack 并重新拉取镜像。

## GitHub Actions 做什么

项目中的 `.github/workflows/docker-publish.yml` 会安装依赖、执行 pytest、构建 `linux/amd64` 和 `linux/arm64`，并推送 GHCR。

例如创建 Tag：

```text
v0.2.3
```

会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.2.3
ghcr.io/aspeternity/homepage-admin:0.2
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.2.3 特别注意

如果 v0.2.2 已经正常使用共享只读 Docker Proxy，本次 **无需再次修改 Homepage Stack**。

升级完成后按 `UPGRADE_V0.2.3_ZH.md` 验证：

- Docker 导入向导字段对齐
- 服务类型 / 置信度识别
- 智能分组推荐
- 图标预览
- 备份保留数量可配置
