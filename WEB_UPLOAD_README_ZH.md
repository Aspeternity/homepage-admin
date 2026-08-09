# GitHub 网页上传 v0.3.2

你已有 `Aspeternity/homepage-admin` 仓库，可继续网页覆盖上传。

1. 下载 `homepage-admin-v0.3.2-web-upload.zip`。
2. 在电脑上解压。
3. GitHub → `Aspeternity/homepage-admin` → **Add file** → **Upload files**。
4. 把解压目录里的全部内容拖进去覆盖。
5. 不要上传 ZIP 本身。
6. **本次请确认 `.github/workflows/docker-publish.yml` 也被覆盖**，v0.3.2 的发布流程新增官方 Widget Schema 快照生成步骤。
7. Commit message：

   ```text
   Release v0.3.2
   ```

8. 到 **Actions** 等待最新构建变绿。
9. Actions 变绿后，在 Portainer 只更新 `homepage-admin` Stack 并重新拉取 `latest`。

v0.3.2 不要求改 HomePage Stack、Docker Proxy、共享网络或 MySQL。
