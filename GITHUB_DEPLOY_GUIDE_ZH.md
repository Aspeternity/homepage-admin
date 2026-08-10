# GitHub + GHCR 部署指南（v0.4.9）

当前仓库：

```text
Aspeternity/homepage-admin
```

当前镜像：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

## 日常升级流程

1. 解压 `homepage-admin-v0.4.9-web-upload.zip`。
2. GitHub 仓库 → **Add file** → **Upload files**。
3. 把解压后的文件内容拖进去覆盖。
4. Commit message：`Release v0.4.9`。
5. 打开 **Actions**。
6. 等待 `Test and publish Docker image` 全部绿色。
7. GHCR 的 `latest` 会自动更新。
8. Portainer 更新 `homepage-admin` Stack 并重新拉取镜像。

## GitHub Actions 做什么

`.github/workflows/docker-publish.yml` 会：

- 安装 Python 依赖
- 执行 pytest
- 从 Homepage 官方仓库生成 Widget Schema 快照
- 构建 `linux/amd64` 和 `linux/arm64`
- 登录 GHCR
- 推送 `latest`
- 创建 Git Tag 时额外推送语义版本标签

例如创建 Tag `v0.4.9` 会得到：

```text
ghcr.io/aspeternity/homepage-admin:0.4.9
ghcr.io/aspeternity/homepage-admin:0.4
ghcr.io/aspeternity/homepage-admin:latest
```

## v0.4.9 特别注意

升级不要求修改现有 Homepage YAML 数据。服务新增/编辑页现在直接从 Docker 发现和 Proxmox 发现加载运行状态集成选项；如果没有对应连接，区域会禁用并提供配置入口。

升级后建议重点验收：

- 新增服务 → Docker 主机 / Docker 容器均为选择框
- 新增服务 → Proxmox 连接 / VM-LXC 均为选择框
- 暂无 Docker 或 Proxmox 配置时，相应区域正确禁用并提示配置入口
- 编辑已有绑定时，发现连接临时不可用也不会清除原配置
- 页面占位符与示例值不包含开发者个人节点名或局域网 IP
- Docker 主机管理、Docker 发现移除配置、Proxmox 发现取消关联继续正常
