# GitHub 网页上传 v0.5.2

1. 解压 `homepage-admin-v0.5.2-web-upload.zip`。
2. GitHub → `homepage-admin` → **Add file** → **Upload files**。
3. 上传解压后的普通项目文件进行覆盖，不要上传 ZIP 本身。
4. Web Upload 包不包含 `.github`，现有正常工作的 Workflow 不需要重复上传。
5. Commit message：

   ```text
   Release v0.5.2
   ```

6. 等待 Actions 绿色后，在 Portainer / Docker Compose 中重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.5.2 将默认 Docker 部署简化为单容器：不再要求共享 Docker Network，也不再把 Docker Socket Proxy 作为 Admin 的默认依赖。Docker 发现仍然可选支持，独立示例见 `docker-compose.docker-proxy.example.yml`。
