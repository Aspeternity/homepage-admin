# GitHub 网页上传 v0.3.4

1. 解压 `homepage-admin-v0.3.4-web-upload.zip`。
2. 将解压后的普通文件 / 目录覆盖上传到 `Aspeternity/homepage-admin` 仓库根目录。
3. 本包故意不包含隐藏的 `.github` 目录；当前已经成功的 `docker-publish.yml` 无需修改。
4. Commit message 建议：

```text
Release v0.3.4
```

5. 等待 `Test and publish Docker image` 全部变绿后，再在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.3.4 不要求修改 HomePage、Docker Proxy、共享网络或 MySQL。
