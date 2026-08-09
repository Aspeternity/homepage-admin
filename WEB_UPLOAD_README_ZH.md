# GitHub 网页上传 v0.2.2

你已经有 `Aspeternity/homepage-admin` 仓库，所以继续用网页覆盖上传即可。

1. 下载 `homepage-admin-v0.2.2-web-upload.zip`。
2. 在电脑上解压。
3. GitHub → `Aspeternity/homepage-admin` → **Add file** → **Upload files**。
4. 把解压目录里的全部内容拖进去。
5. 不要上传 ZIP 本身。
6. Commit message 填：

   ```text
   Release v0.2.2
   ```

7. 提交后到 **Actions** 等待最新构建变绿。

Web Upload 包继续故意排除 `.github`、`.gitignore`、`.dockerignore`、`.env.example` 等隐藏路径。仓库里现有的 GitHub Actions 工作流可以直接构建 v0.2.2。

Actions 变绿后按 `UPGRADE_V0.2.2_ZH.md` 更新 Portainer。v0.2.1 已完成共享 Docker Proxy 迁移的话，本次不需要再改网络或 Homepage Stack。
