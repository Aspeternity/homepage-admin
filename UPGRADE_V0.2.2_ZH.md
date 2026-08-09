# 从 v0.2.1 升级到 v0.2.2

v0.2.2 **不需要再次修改 Homepage 的 Docker 网络、PGID 或 docker.yaml**。如果你已经完成 v0.2.1 的共享只读代理迁移，现有结构原样保留即可。

## 1. 更新 GitHub 仓库

使用 `homepage-admin-v0.2.2-web-upload.zip` 覆盖上传到现有 `Aspeternity/homepage-admin` 仓库。

Commit message 建议：

```text
Release v0.2.2
```

等待 GitHub Actions 的 `Test and publish Docker image` 变绿。

## 2. 更新 Portainer Stack

现有 v0.2.1 Compose **无需改内容**。

Portainer → Stacks → `homepage-admin` → Editor：

1. 保留现有密码、SESSION_SECRET、Homepage URL 等环境变量。
2. 保留 `homepage-tools` external network。
3. 保留 `homepage-docker-proxy`。
4. 点击 **Update the stack**，并重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。

## 3. 验证版本

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应看到：

```json
{"status":"ok","version":"0.2.2"}
```

## 4. 验证三个新功能

### 主题菜单

桌面页面右上角应出现小型主题图标。点击后应显示：

- 浅色模式
- 深色模式
- 跟随系统

左侧底部不再出现旧版“切换浅色 / 切换深色”大按钮。

### Docker 导入向导

Docker 发现 → 任意“尚未添加”的容器 → **添加到 Homepage**。

应先进入“Docker 导入向导”，看到：

- 容器状态和发布端口
- 自动推荐的服务名称 / 地址 / 图标 / 说明 / 分组 / Widget
- 卡片实时预览
- YAML 实时预览
- “继续到完整编辑器”按钮

### 备份删除

备份回滚页面应看到：

- 每个备份右侧“删除备份”
- 页面右上“清空全部备份”
- 自动保留上限提示

删除不会影响当前正在使用的 Homepage YAML，只会删除 `/data/backups` 中对应的历史副本。

## 5. Docker 架构保持不变

HomePage 继续使用：

```yaml
local-docker:
  host: homepage-docker-proxy
  port: 2375
```

HomePage 本体继续：

```text
PUID=1000
PGID=1000
```

并且不要重新挂载 `/var/run/docker.sock` 给 HomePage。
