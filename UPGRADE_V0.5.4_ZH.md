# Homepage Admin v0.5.4 升级说明

v0.5.4 继续降低首次部署门槛，重点优化 Compose 持久化方式和首次创建管理员账号的页面体验。

## Docker Compose 更直观

默认推荐改为宿主机目录挂载，不再使用 Docker Named Volume：

```yaml
services:
  homepage-admin:
    image: ghcr.io/aspeternity/homepage-admin:latest
    container_name: homepage-admin
    restart: unless-stopped
    network_mode: bridge
    ports:
      - "3001:3001"
    volumes:
      - /path/to/homepage/config:/config
      - ./data:/data
```

现在 `/data` 会直接保存在 Compose 文件旁边的 `data` 目录，账号、Session Secret、备份、审计日志和 Admin 设置更方便备份与迁移。

> `/config` 与 `/data` 必须允许容器内 UID/GID `1000:1000` 读写。

## 首次初始化页面升级

第一次访问 `/setup` 时使用新的初始化界面：

- 使用正式 Homepage Admin Logo；
- 显示 3 步初始化流程；
- 新增密码显示/隐藏；
- 新增实时密码强度；
- 新增两次密码一致性检查；
- 新增 Caps Lock 提示；
- 高级安全信息改为可折叠区域；
- 提交时显示创建中状态；
- 服务端校验失败时保留已填写的用户名，但永远不会回填密码。

认证方式不变：密码只保存 bcrypt 哈希，Session Secret 自动生成并保存在 `/data/auth.json`。

## Compose 网络写法统一

仓库和 GitHub 首页的完整 Compose 示例统一显式使用：

```yaml
network_mode: bridge
```

Docker Socket Proxy 的端口映射也改为：

```yaml
ports:
  - "2375:2375"
```

不再在 Compose 中写死宿主机 IP。请使用宿主机防火墙限制 2375 只允许可信局域网来源访问，绝对不要暴露到公网。

## 从 v0.5.3 升级

原有 `/data` 目录必须保留。升级后认证文件格式没有变化，不需要重新创建账号。

如果之前使用 Docker Named Volume，可以继续使用；本版本只是把新部署的推荐示例改成宿主机目录。若希望迁移到 Bind Mount，请先把 Named Volume 中的 `/data` 内容完整复制到新的宿主机目录，再重新部署。
