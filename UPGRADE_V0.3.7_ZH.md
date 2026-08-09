# Homepage Admin v0.3.7 升级说明

v0.3.7 重点修复 Proxmox 发现与 Homepage 本体 per-VM/LXC 状态之间的兼容性问题。

## 主要修复

- 检测 `proxmox.yaml` 中以 `/` 结尾的 URL，并提供“一键修复 URL”。Homepage 会自行拼接 `/api2/json`，因此连接 URL 应保存为不带末尾 `/` 的基础地址。
- 从已有 Proxmox Service Widget 导入连接时自动去掉末尾 `/`。
- 绑定 VM/LXC 时使用 PVE API 返回的真实节点名；若对应实际节点没有同名 `proxmox.yaml` 连接，则不生成可能错误的绑定。
- 若目标 Homepage 服务已经配置 `server + container`，绑定时会提示 Docker/Proxmox 冲突，并默认提供“关联时清除 Docker 集成”的选择。
- 已经绑定的服务若仍有 Docker 集成，Proxmox 发现卡片会显示冲突，并提供“一键清除该服务的 Docker 集成”。
- 服务编辑页同时存在 Docker + Proxmox 时显示警告。

## 升级

解压 `homepage-admin-v0.3.7-web-upload.zip` 后覆盖上传仓库。Web Upload 包不包含 `.github`，现有成功的 Workflow 无需修改。

Commit 建议：

```text
Release v0.3.7
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。升级后 `/healthz` 应显示 `0.3.7`。

## 针对当前 Proxmox 关联的建议

升级后打开 **Proxmox 发现**：

1. 若顶部提示 URL 末尾包含 `/`，点击 **一键修复 URL**。
2. 若已关联的服务提示仍配置 Docker，确认该服务代表 PVE VM/LXC 后点击 **清除该服务的 Docker 集成**。
3. 刷新 Homepage，per-VM 状态应使用 `proxmoxNode + proxmoxVMID` 从 Proxmox API 读取。
