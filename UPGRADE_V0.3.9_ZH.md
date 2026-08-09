# Homepage Admin v0.3.9 升级说明

v0.3.9 是一个纯 UI 小修复。

## 修复

- Proxmox 发现页中，已关联 VM/LXC 卡片的“编辑服务”和“取消关联”现在使用完全一致的高度与拉伸规则。
- 原因是前者为 `<a>`，后者位于 `<form>` 内；CSS Grid 会拉伸直接子元素，但不会自动让表单内部按钮填满父元素高度。v0.3.9 让表单本身使用 Flex，并让两侧按钮都填满同一网格单元。

## 升级

解压 `homepage-admin-v0.3.9-web-upload.zip`，覆盖上传 GitHub 仓库普通文件即可。Web Upload 包不包含 `.github`，现有 Workflow 不需要修改。

Commit 建议：

```text
Release v0.3.9
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.3.9`。
