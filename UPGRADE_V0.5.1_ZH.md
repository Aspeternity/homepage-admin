# Homepage Admin v0.5.1 升级说明

v0.5.1 主要优化 GitHub 项目首页和公开部署文档，不改变现有 Homepage YAML 数据模型。

## 主要变化

- README 重构为面向新用户的项目首页：项目简介、主要功能、架构、Docker 快速部署、安全、升级和源码运行。
- 新增 GHCR + Docker Compose + 只读 Docker Socket Proxy 推荐部署示例。
- 新增不启用 Docker 发现的最小部署示例。
- 新增多 Docker 主机远程只读 Proxy 示例。
- 新增项目 1:1 Logo：`docs/assets/homepage-admin.png`。
- 历史版本细节继续保留在 `CHANGELOG.md` 与各版本升级说明中，不再大量占用 README 首页。

## 升级

本版本没有新的 Homepage 配置迁移要求。升级前仍建议在备份中心创建完整快照。

GitHub 网页覆盖上传后建议 Commit：

```text
Release v0.5.1
```

等待 Actions 绿色后重新拉取：

```text
ghcr.io/aspeternity/homepage-admin:latest
```
