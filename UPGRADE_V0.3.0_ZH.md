# Homepage Admin v0.3.0 升级说明

适用于已经运行 v0.2.4、并完成 `homepage-tools` + `homepage-docker-proxy` 迁移的环境。

## 结论

v0.3.0 **只需要升级 Homepage Admin 镜像**。

以下内容全部保持现状：

```text
HomePage Stack                 不改
homepage-docker-proxy          不改
homepage-tools                 不改
HomePage PUID / PGID           不改
docker.yaml                    不改
HomePage 不挂 docker.sock      保持
```

v0.3.0 也 **不要求 MySQL**，因此不需要创建数据库、账号或给 Admin 增加数据库环境变量。

## 1. GitHub 网页覆盖上传

下载：

```text
homepage-admin-v0.3.0-web-upload.zip
```

解压后进入 GitHub：

```text
Aspeternity/homepage-admin
→ Add file
→ Upload files
```

把解压后的文件覆盖上传。

Commit message：

```text
Release v0.3.0
```

等待 Actions 中 `Test and publish Docker image` 变绿。

## 2. Portainer 更新 homepage-admin Stack

进入：

```text
Portainer
→ Stacks
→ homepage-admin
→ Editor
```

Compose 不需要修改。确认镜像仍是：

```yaml
image: ghcr.io/aspeternity/homepage-admin:latest
pull_policy: always
```

点击 **Update the stack**，并在有选项时勾选重新拉取镜像。

## 3. 验证版本

Docker VM 执行：

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

预期：

```json
{"status":"ok","version":"0.3.0"}
```

## 4. 推荐验收项目

### Widget 中心

左侧应出现：

```text
Widget 中心
```

确认搜索、分类过滤和“使用此 Widget”正常。

### 多 Widget

编辑一个测试服务：

```text
+ 添加 Widget
→ 添加第二个 Widget
→ 调整顺序
→ 预览变更
```

保存后高级 YAML 应使用 `widgets:` 列表。

### 测试连接

推荐用已经配置好的 Portainer / Proxmox / Home Assistant 测试。

编辑已有服务时，不需要重新粘贴已保存的 Secret；后台会在连接测试时从当前 `services.yaml` 安全复用。

### Proxmox 发现

如果 `proxmox.yaml` 已经配置，打开：

```text
Proxmox 发现
```

应该显示 VM / LXC。

如果 `proxmox.yaml` 为空，而 `services.yaml` 已经存在可用的 Proxmox Widget，页面会提供“从此 Widget 导入”。Secret 只在服务端复制，不回传浏览器。

### 保存前 Diff

编辑服务或高级 YAML 后点击保存，应先显示 Diff；Secret 应显示为掩码而不是真实值。

## 5. 关于 MySQL

虽然当前 Docker VM 已经运行 MySQL，但 v0.3.0 没有把它列为依赖。原因是当前状态量很小：Homepage YAML、本地管理偏好、备份、审计都适合文件存储。

如果未来实现以下功能，再评估可选 MySQL 后端：

- 多管理员 / RBAC
- 管理多个 Homepage 实例
- 大量历史版本索引
- Widget 探测历史与趋势
- 集中式 Secret 元数据（不建议把 Secret 明文放数据库）

## 回滚

如果升级后需要回滚应用版本，只需在 Portainer 把镜像改回此前固定 tag（如已发布），或重新部署之前的镜像。Homepage 配置格式仍保持官方 YAML，不需要数据库回滚。
