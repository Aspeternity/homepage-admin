# Homepage Admin v0.5.0 升级说明

v0.5.0 将原“备份回滚”升级为完整的“备份中心”。

## 新功能

1. **完整配置快照**：可手动一次备份全部当前 Homepage 配置，并添加备注。手动快照不会被自动保留策略删除。
2. **备份元数据**：新备份记录创建时间、来源操作、操作者、类型和备注；旧备份无需迁移。
3. **保护备份**：可锁定重要备份。受保护备份不会被自动清理、批量清理或直接删除。
4. **ZIP 导出**：每个备份都可以导出 ZIP 保存到其他设备。
5. **恢复前 Diff**：单文件恢复前可比较“当前 → 恢复后”，YAML Token、Password、API Key 等敏感值会被掩码。
6. **整体恢复**：多文件快照支持恢复全部；执行前自动创建一个受保护的恢复前快照。
7. **筛选与概览**：增加全部/自动/手动/受保护数量、总占用，以及搜索、类型和文件筛选。
8. **保留策略修正**：`BACKUP_LIMIT` / 后台自定义上限只限制普通自动备份，不会清理手动快照和恢复保护点。

## 兼容性

- `/data/backups` 中已有旧版备份会继续显示为兼容备份，无需人工迁移。
- Homepage 配置目录与 Docker/Proxmox/Widget 等现有配置不需要修改。
- Web Upload 包仍不包含 `.github`，现有 Docker Publish Workflow 无需调整。

## 升级

解压 `homepage-admin-v0.5.0-web-upload.zip` 后覆盖上传 GitHub 仓库普通文件，Commit 建议：

```text
Release v0.5.0
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。
