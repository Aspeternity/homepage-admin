# GitHub 网页上传 v0.3.1

你已有 `Aspeternity/homepage-admin` 仓库，可继续网页覆盖上传。

1. 下载 `homepage-admin-v0.3.1-web-upload.zip`。
2. 在电脑上解压。
3. GitHub → `Aspeternity/homepage-admin` → **Add file** → **Upload files**。
4. 把解压目录里的全部内容拖进去。
5. 不要上传 ZIP 本身。
6. Commit message：

   ```text
   Release v0.3.1
   ```

7. 到 **Actions** 等待最新构建变绿。
8. Actions 变绿后，在 Portainer 只更新 `homepage-admin` Stack 并重新拉取 `latest`。

Web Upload 包故意排除 `.github`、`.gitignore`、`.dockerignore`、`.env.example` 等隐藏路径，仓库中已有的 GitHub Actions 工作流继续使用。

v0.3.1 不要求改 HomePage Stack、Docker Proxy、共享网络或 MySQL。
