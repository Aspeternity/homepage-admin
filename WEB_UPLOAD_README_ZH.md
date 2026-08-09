# GitHub 网页上传 v0.2.0（适合当前仓库）

你已经有 `Aspeternity/homepage-admin` 仓库和可用的 v0.1.1 GitHub Actions，因此升级 v0.2.0 时不必重新创建仓库。

## 最省事的方式

1. 使用随发布包提供的 `homepage-admin-v0.2.0-web-upload.zip`。
2. 在电脑上解压。
3. 打开 GitHub 仓库 `Aspeternity/homepage-admin`。
4. 选择 **Add file → Upload files**。
5. 把解压目录“里面”的所有文件和文件夹拖进去，不要上传 ZIP 本身。
6. 等待文件上传完成，提交说明填写：`Release v0.2.0`。
7. 点击 **Commit changes**。
8. 打开 **Actions**，等待最新的 `Test and publish Docker image` 变成绿色。

这个 Web Upload 包故意不包含 `.github`、`.gitignore`、`.dockerignore`、`.env.example` 等隐藏路径，避免浏览器/系统隐藏文件导致上传困难。你仓库里现有的 v0.1.1 GitHub Actions 工作流仍然可以测试和构建 v0.2.0。

完整发布包中仍包含新版 `.github/workflows/docker-publish.yml`。新版工作流只是额外加入了 concurrency（连续提交时取消同分支旧构建），不是 v0.2.0 功能运行的必要条件。以后需要时可以在 GitHub 网页编辑器里单独覆盖。

## Actions 成功后

GHCR 的 `latest` 会更新：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

然后按 `UPGRADE_V0.2.0_ZH.md` 修改 Portainer Stack。v0.2.0 的 Docker 发现需要新增第二个容器：

```text
homepage-admin-docker-proxy
```

原来的 Homepage YAML 配置和 `/opt/docker/homepage-admin/data` 备份目录不用迁移。
