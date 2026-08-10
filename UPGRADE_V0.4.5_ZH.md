# Homepage Admin v0.4.5 升级说明

v0.4.5 重点优化“新增/编辑服务”的 Docker 与 Proxmox 集成体验，并清理面向开源发布时不应出现的个人环境示例。

## 1. Docker 集成改为发现选择器

新增/编辑服务不再手工输入 `server` 与 `container`。页面先选择 Docker 主机，再实时读取该主机的容器。最终仍按 Homepage 官方格式保存：

```yaml
server: docker-node
container: media-server
```

如果尚未配置可发现的 Docker 主机，该区域会禁用并提示先进入 **Docker 主机管理**。

## 2. Proxmox 集成改为发现选择器

先选择 `proxmox.yaml` 连接，再实时读取 VM/LXC。保存时仍写入：

```yaml
proxmoxNode: pve-node1
proxmoxVMID: 100
proxmoxType: qemu
```

若 PVE 返回的物理节点没有同名 `proxmox.yaml` 连接，对应资源会显示为不可选，避免生成 Homepage 无法读取的绑定。

如果尚未配置 Proxmox 连接，该区域会禁用并提示先配置 `proxmox.yaml`。

## 3. 已有配置保护

如果服务已有 Docker/Proxmox 绑定，但对应发现连接临时不存在或不可达，表单不会因为控件禁用而删除原配置；保存时仍会保留当前值。

## 4. 开源友好化

用户界面的示例节点名、私网 IP、书签示例和分组提示已改成通用值。IP 示例使用 RFC 5737 TEST-NET，例如 `192.0.2.20`，避免把开发者自己的局域网信息写进公开仓库。

Compose 示例中的 Homepage 默认地址调整为同 Docker 网络 DNS `http://HomePage:3000`；`DOCKER_PUBLIC_HOST` 默认留空，建议部署者按自己的 LAN 地址填写。现有 Portainer Stack 若已经显式设置这些环境变量，不受影响。

## 升级

解压 `homepage-admin-v0.4.5-web-upload.zip`，覆盖上传仓库普通文件。Web Upload 包不包含 `.github`。

Commit message 建议：

```text
Release v0.4.5
```

Actions 绿色后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.4.5`。
