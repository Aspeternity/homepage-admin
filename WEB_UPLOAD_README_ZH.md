# GitHub 网页上传 v0.5.4

1. 解压 `homepage-admin-v0.5.4-web-upload.zip`。
2. GitHub → `homepage-admin` → **Add file** → **Upload files**。
3. 上传解压后的普通项目文件覆盖仓库。
4. Web Upload 包不包含 `.github`，现有成功的 Workflow 不需要修改。
5. Commit message：

   ```text
   Release v0.5.4
   ```

6. 等 Actions 变绿后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.5.4 默认 Compose 使用宿主机 `./data:/data`、`network_mode: bridge`，且不再要求管理员用户名、密码或 Session Secret。第一次打开网页时创建管理员账号；Docker Proxy 示例端口使用 `2375:2375`，不在 Compose 中写死宿主机 IP。
