# GitHub 网页上传 v0.5.3

1. 解压 `homepage-admin-v0.5.3-web-upload.zip`。
2. GitHub → `homepage-admin` → **Add file** → **Upload files**。
3. 上传解压后的普通项目文件覆盖仓库。
4. Web Upload 包不包含 `.github`，现有成功的 Workflow 不需要修改。
5. Commit message：

   ```text
   Release v0.5.3
   ```

6. 等 Actions 变绿后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

v0.5.3 新安装不再要求在 Compose 中设置管理员用户名、密码或 Session Secret；第一次打开网页时创建管理员账号。旧版认证环境变量会自动迁移到 `/data/auth.json`，确认登录正常后即可从 Compose 删除。
