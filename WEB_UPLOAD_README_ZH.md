# GitHub 网页上传 v0.4.5

1. 解压 `homepage-admin-v0.4.5-web-upload.zip`。
2. 将解压后的普通文件 / 目录覆盖上传到 `Aspeternity/homepage-admin` 仓库根目录。
3. 本包故意不包含隐藏的 `.github` 目录；当前已经成功的 `docker-publish.yml` 无需修改。
4. Commit message 建议：

```text
Release v0.4.5
```

5. 等待 `Test and publish Docker image` 全部变绿后，再在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.4.5 不要求修改 HomePage、Docker Socket Proxy、共享网络或 MySQL。首次启动会自动把 v0.4.0-v0.4.2 的重复 Docker 发现配置迁移成 metadata-only 模型：`docker.yaml` 保留唯一连接配置，`admin-settings.json` 只保留显示名称、Public Host 和必要的 Discovery Override。
