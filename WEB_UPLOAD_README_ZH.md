# GitHub 网页上传 v0.5.1

1. 解压 `homepage-admin-v0.5.1-web-upload.zip`。
2. GitHub → `homepage-admin` → **Add file** → **Upload files**。
3. 把解压后的普通项目文件拖进去覆盖；不要上传 ZIP 本身。
4. Web Upload 包不包含 `.github`，现有已经正常工作的 Workflow 不需要重复上传。
5. 本版本新增 `docs/assets/homepage-admin.png`，上传时请保留 `docs/assets` 目录。
6. Commit message：

   ```text
   Release v0.5.1
   ```

7. 等待 Actions 绿色后，在 Portainer / Docker Compose 中重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.5.1 主要是 GitHub README 与部署文档优化，不要求修改现有 Homepage、Docker Proxy、Proxmox 或网络配置。
