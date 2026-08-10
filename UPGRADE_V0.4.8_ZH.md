# Homepage Admin v0.4.8 升级说明

v0.4.8 将 Proxmox 发现升级为与 Docker 发现类似的多节点管理模式。

## 核心变化

1. **多节点聚合发现**
   - `/proxmox` 默认显示“全部节点”，同时读取 `proxmox.yaml` 中的全部有效连接。
   - 可以切换到单个节点查看。
   - 同一 Cluster 使用相同 URL 的多个节点只请求一次 API，并按 `物理节点 + VMID + 类型` 去重。
   - 独立 Proxmox Cluster 会并行读取。

2. **Proxmox 节点管理**
   - 新增 `/proxmox/nodes`。
   - 支持添加、编辑、测试、删除节点。
   - Token Secret 只写入 `proxmox.yaml`，编辑页面永不回显。
   - URL 保存时自动移除末尾 `/`。
   - 未识别的未来 `proxmox.yaml` 字段在编辑保存时继续保留。

3. **节点名与 Homepage 兼容性**
   - Homepage 当前要求 `proxmoxNode` 同时匹配 `proxmox.yaml` 键名和 PVE 的真实 `/nodes/<node>` 名称。
   - 因此节点名应使用真实 PVE 物理节点名，例如 `pve-node1`。
   - 有服务引用的节点名禁止直接重命名，避免现有服务失效。

4. **补齐集群节点**
   - 对任一可用节点点击“补齐集群节点”，Admin 会通过 PVE `/api2/json/nodes` 获取实际节点列表。
   - 对缺失的物理节点自动复制相同 URL / Token / Secret 到 `proxmox.yaml`。
   - 已存在节点不会覆盖。

5. **安全删除**
   - 删除前列出所有使用该 `proxmoxNode` 的 Homepage 服务。
   - 有引用时必须输入 `DELETE`。
   - 可选择同时清除服务中的 `proxmoxNode` / `proxmoxVMID` / `proxmoxType`。
   - 服务、Widget、URL、图标等其他配置不会删除。

6. **发现页筛选**
   - 支持名称 / VMID / 节点搜索。
   - 支持 QEMU / LXC 筛选。
   - 支持 running / stopped 状态筛选。

## 升级

解压 `homepage-admin-v0.4.8-web-upload.zip` 后覆盖 GitHub 仓库普通文件即可。Web Upload 包仍不包含 `.github`。

建议 Commit：

```text
Release v0.4.8
```

Actions 绿色后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应返回 `0.4.8`。
