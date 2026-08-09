# GitHub 网页上传 v0.3.3

你已有 `Aspeternity/homepage-admin` 仓库，可继续网页覆盖上传。

这次 v0.3.3 是 **运行时 Widget Schema ref 热修复**。你当前仓库的 Workflow #15 已经使用 `dev` 并成功构建，所以 **不需要再次通过网页上传隐藏的 `.github` 目录**。

1. 下载 `homepage-admin-v0.3.3-web-upload.zip`。
2. 在电脑上解压。
3. GitHub → `Aspeternity/homepage-admin` → **Add file** → **Upload files**。
4. 把解压目录里的普通项目文件拖进去覆盖。
5. 不要上传 ZIP 本身。
6. Commit message：

   ```text
   Release v0.3.3
   ```

7. 到 **Actions** 等待构建变绿。
8. 在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

如果是从一个尚未修复 Workflow 的旧仓库升级，请单独把 `docker-publish-v0.3.3.yml` 的内容覆盖到 `.github/workflows/docker-publish.yml`。完整源码包里也包含正确的 `.github` 工作流。

v0.3.3 不要求修改 HomePage Stack、Docker Proxy、共享网络或 MySQL。
