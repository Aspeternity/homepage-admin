# GitHub 网页上传 v0.4.0

1. 解压 `homepage-admin-v0.4.0-web-upload.zip`。
2. 将解压后的普通文件 / 目录覆盖上传到 `Aspeternity/homepage-admin` 仓库根目录。
3. 本包故意不包含隐藏的 `.github` 目录；当前已经成功的 `docker-publish.yml` 无需修改。
4. Commit message 建议：

```text
Release v0.4.0
```

5. 等待 `Test and publish Docker image` 全部变绿后，再在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.4.0 不要求修改现有 HomePage、主 Docker VM 的 `homepage-docker-proxy`、共享网络或 MySQL。若要发现 Game-Server VM 等其他 Docker 主机，需要在目标 VM 提供 Admin 可达的只读 Docker API（推荐 Docker Socket Proxy + `POST=0`）。
