# Homepage Admin v0.3.8 升级说明

v0.3.8 是 Proxmox 发现 / 服务编辑器的小版本修复。

## 本次修复

1. **Proxmox VM / LXC 集成输入框对齐**
   - `Proxmox 节点名`、`VMID`、`类型` 使用统一的标题 / 42px 控件 / 帮助文字三行布局。
   - 没有帮助文字的字段保留不可见占位，不再被其他字段的说明文字挤偏。

2. **已关联服务支持取消关联**
   - Proxmox 发现页已关联卡片现在同时显示“编辑服务”和“取消关联”。
   - “取消关联”只移除 `proxmoxNode`、`proxmoxVMID`、`proxmoxType`。
   - 不删除服务，不修改 Widget，不修改 Docker 配置。
   - 提交前会校验当前关联是否仍与页面一致，避免旧页面误解绑已经变化的配置。
   - 操作仍通过 `services.yaml` 原子写入与备份机制。

## 升级

解压 `homepage-admin-v0.3.8-web-upload.zip`，覆盖上传 GitHub 仓库普通文件即可。Web Upload 包仍不包含 `.github`。

Commit message 建议：

```text
Release v0.3.8
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.3.8`。
