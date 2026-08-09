# 从 v0.2.2 升级到 v0.2.3

v0.2.3 是界面与导入体验优化版本。**如果 v0.2.1 / v0.2.2 已经完成 `homepage-tools` + `homepage-docker-proxy` 迁移，本次不需要修改 HomePage Stack、PGID、docker.yaml 或 Docker 网络。**

## 1. GitHub 覆盖上传

使用 `homepage-admin-v0.2.3-web-upload.zip` 覆盖上传到现有 `Aspeternity/homepage-admin` 仓库。

Commit message：

```text
Release v0.2.3
```

等待 `Test and publish Docker image` 变绿。

## 2. Portainer 更新

进入 `homepage-admin` Stack，保持现有 Compose 不变，确认：

```yaml
image: ghcr.io/aspeternity/homepage-admin:latest
pull_policy: always
```

更新 Stack，并重新拉取 latest。

## 3. 验证版本

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

期望：

```json
{"status":"ok","version":"0.2.3"}
```

## 4. 验证 v0.2.3

### Docker 导入向导

1. 打开 `Docker 发现`。
2. `导入分组策略` 默认应为 `智能推荐（按服务类型）`。
3. 选择一个未加入 Homepage 的容器。
4. 向导顶部会显示 `识别为` 与 `置信度`。
5. `访问地址` 与 `图标` 输入框应保持同一水平，不再因“来源”提示数量不同而错位。
6. 已识别服务会推荐说明、图标、Widget（如支持）以及现有分组。
7. 右侧卡片预览会尽量显示 URL 图标或 `sh-*` 图标；加载失败会回退为文字图标。

### 备份保留数量

打开 `备份回滚`：

- `自动保留策略` 可输入 1–500 组。
- 保存后写入 `/data/admin-settings.json`，不需要修改 Portainer 环境变量。
- 如果新上限小于当前备份数，会立即清理最旧备份。
- `恢复默认` 会回到 `BACKUP_LIMIT` 环境变量的值（默认 50）。

## 5. 不需要修改的内容

以下继续保持 v0.2.2 当前状态：

```text
HomePage PUID=1000
HomePage PGID=1000
HomePage 不挂载 /var/run/docker.sock
HomePage docker.yaml -> homepage-docker-proxy:2375
homepage-tools 外部 bridge 网络
homepage-docker-proxy 不映射宿主机 2375
```
