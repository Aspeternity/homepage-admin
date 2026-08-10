# Homepage Admin v0.4.9 升级说明

v0.4.9 是 Proxmox 发现筛选栏的界面小修复。

## 本次优化

桌面端将以下三个筛选控件固定在同一行：

- 搜索 VM / LXC
- 类型
- 状态

搜索框保持较宽比例，类型与状态使用较窄列。小于 980px 的窗口仍会自动切换成单列，保证手机与窄屏可用。

## 升级

解压 `homepage-admin-v0.4.9-web-upload.zip` 后覆盖 GitHub 仓库普通文件即可；`.github` 无需修改。

Commit 建议：

```text
Release v0.4.9
```
