# Homepage Admin v0.4.2 升级说明

v0.4.2 统一 Docker 主机管理体验。

## 本次变化

1. **Docker 发现主页更简洁**
   - 删除顶部重复的 Docker 主机状态卡。
   - 保留主机选择、搜索、状态筛选、Homepage 筛选与容器卡片。
   - 只有连接失败时才显示简洁的错误提示。

2. **所有 Docker 主机使用同一套管理方式**
   - 不再区分 `docker.yaml` 原生 Server 和 Admin 自定义连接的编辑页面。
   - `local-docker`、`game-server` 等全部进入相同的“编辑 Docker 主机”表单。
   - 表单统一包含：显示名称、Homepage Docker Server、Discovery URL、Public Host。
   - 编辑已有主机时锁定 Homepage Server 名称，防止现有 `services.yaml` 引用断开。

3. **保存时自动维护 docker.yaml**
   - 新增主机时固定同时创建同名 `docker.yaml` Server。
   - 编辑主机时固定同步更新对应 `docker.yaml` Server。
   - 因此移除了“若 docker.yaml 没有同名 Server，则同时创建”的复选框，也不存在复选框对齐问题。
   - 已有 TLS、Header 和未知扩展字段仍原样保留。

4. **删除体验同步统一**
   - 删除页面默认完整移除主机发现设置与 `docker.yaml` Server。
   - 若 Server 正被服务引用，仍要求 `DELETE` 确认，并可选择同时清除服务的 `server` / `container` 关联。

## 升级

解压 `homepage-admin-v0.4.2-web-upload.zip` 后覆盖 GitHub 仓库普通文件。Web Upload 包不包含 `.github`。

Commit message 建议：

```text
Release v0.4.2
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.4.2`。
