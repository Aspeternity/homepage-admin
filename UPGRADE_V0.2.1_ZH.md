# 从 v0.2.0 升级到 v0.2.1

你当前已经运行 v0.2.0，Docker 状态也通过把 Homepage `PGID` 改为 Docker 组 GID `989` 验证成功。v0.2.1 会把这个临时方案升级成更安全的共享只读代理方案。

## 一、上传代码并等待 GitHub Actions

使用 `homepage-admin-v0.2.1-web-upload.zip` 覆盖上传到现有仓库：

```text
Aspeternity/homepage-admin
```

Commit message：

```text
Release v0.2.1
```

然后进入 GitHub → Actions，等待最新 `Test and publish Docker image` 变绿。

## 二、在 Docker VM 创建共享网络（只需一次）

SSH 执行：

```bash
docker network inspect homepage-tools >/dev/null 2>&1 || docker network create homepage-tools
```

确认：

```bash
docker network inspect homepage-tools --format '{{.Name}}'
```

应输出：

```text
homepage-tools
```

## 三、更新 Homepage Admin Stack

Portainer → Stacks → `homepage-admin` → Editor。

用项目里的：

```text
docker-compose.portainer.yml
```

替换原 Stack。

保留你当前真实的：

- `ADMIN_PASSWORD` / `ADMIN_PASSWORD_HASH`
- `SESSION_SECRET`
- `HOMEPAGE_URL`

更新后应看到：

```text
homepage-admin
homepage-docker-proxy
```

其中 `homepage-docker-proxy` 使用：

```text
ghcr.io/tecnativa/docker-socket-proxy:latest
```

且没有宿主机端口映射。

## 四、把 Homepage 本体加入共享网络

打开你现有的 Homepage Stack，在 `HomePage` service 中加入：

```yaml
networks:
  - homepage-tools
```

并在 Compose 最后加入：

```yaml
networks:
  homepage-tools:
    external: true
```

### 同时恢复 Homepage 的 PUID / PGID

你当前为了直接访问 Docker Socket 临时使用：

```yaml
PUID: 1000
PGID: 989
```

v0.2.1 代理方案完成后可恢复：

```yaml
PUID: 1000
PGID: 1000
```

### 移除 Homepage 直接 Docker Socket 挂载

从 Homepage Stack 删除：

```yaml
- /var/run/docker.sock:/var/run/docker.sock
```

（如果原来写了 `:ro`，同样整行删除。）

更新 Homepage Stack。

## 五、把 docker.yaml 从 Socket 切到 Proxy

打开 Homepage Admin → **Docker 发现**。

如果页面提示当前为：

```text
直接 Socket 模式
```

点击：

```text
切换为只读代理
```

后台会自动备份并把原来的：

```yaml
local-docker:
  socket: /var/run/docker.sock
```

改成：

```yaml
local-docker:
  host: homepage-docker-proxy
  port: 2375
```

## 六、验证

### 1. Admin 版本

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应包含：

```text
"version":"0.2.1"
```

### 2. Proxy 存在且没有宿主机端口

```bash
docker ps --filter name=homepage-docker-proxy
```

### 3. 两个容器都在共享网络

```bash
docker network inspect homepage-tools --format '{{range .Containers}}{{println .Name}}{{end}}'
```

至少应包含：

```text
HomePage
homepage-admin
homepage-docker-proxy
```

### 4. Homepage Docker 状态

刷新 Homepage。之前测试的 `Lsky-pro` 应继续显示：

```text
运行中
```

### 5. 日志不再出现 Socket EACCES

```bash
docker logs HomePage 2>&1 | grep -i -E 'docker|socket|EACCES|local-docker' | tail -30
```

因为 Homepage 已经不再直接连接 `/var/run/docker.sock`，不应再出现新的：

```text
connect EACCES /var/run/docker.sock
```

## 七、浅色 / 深色主题

v0.2.1 左侧底部新增主题按钮：

```text
☀ 切换浅色
```

切到浅色后会变为：

```text
☾ 切换深色
```

选择保存在浏览器本地，不写入 Homepage YAML，也不会影响其他设备上的主题选择。
