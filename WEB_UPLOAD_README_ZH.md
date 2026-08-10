# GitHub 网页上传 v0.4.8

1. 解压 `homepage-admin-v0.4.8-web-upload.zip`。
2. GitHub → `homepage-admin` → **Add file** → **Upload files**。
3. 把解压后的普通项目文件拖进去覆盖；不要上传 ZIP 本身。
4. Web Upload 包不包含 `.github`，现有已正常工作的 Workflow 不需要重复上传。
5. Commit message：

   ```text
   Release v0.4.8
   ```

6. 等待 Actions 绿色后，在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.4.8 不要求修改 Homepage、Docker Proxy、共享网络、Proxmox 或 MySQL 配置。
