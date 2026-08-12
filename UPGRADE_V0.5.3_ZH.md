# Homepage Admin v0.5.3 升级说明

v0.5.3 重点简化首次部署和管理员认证。

## 首次运行创建账号

新安装不再要求在 Compose 中设置：

```text
ADMIN_USERNAME
ADMIN_PASSWORD
ADMIN_PASSWORD_HASH
SESSION_SECRET
```

第一次访问 `http://服务器:3001` 时会自动进入 `/setup`，填写管理员用户名、密码和确认密码即可。

认证数据保存在：

```text
/data/auth.json
```

密码只保存 bcrypt 哈希；Session Secret 由程序自动生成并持久化。

## 推荐 Compose

```yaml
services:
  homepage-admin:
    image: ghcr.io/aspeternity/homepage-admin:latest
    container_name: homepage-admin
    restart: unless-stopped
    ports:
      - "3001:3001"
    volumes:
      - /path/to/homepage/config:/config
      - homepage-admin-data:/data

volumes:
  homepage-admin-data:
```

只需要把 `/path/to/homepage/config` 改成 Homepage 的实际配置目录。

## 从旧版本升级

如果旧 Compose 仍然包含管理员用户名、密码或 Session Secret，不需要立即删除。v0.5.3 第一次启动会把现有账号迁移到 `/data/auth.json`：

- `ADMIN_PASSWORD` 会转换为 bcrypt 哈希；
- `ADMIN_PASSWORD_HASH` 会原样迁移；
- `SESSION_SECRET` 会写入持久化认证文件；
- 原有账号仍可正常登录。

确认 v0.5.3 正常登录后，可以从 Compose 删除这些认证环境变量并重新部署。

> 必须继续持久化原来的 `/data`。如果删除 `/data`，管理员账号、Session Secret、备份和 Admin 设置都会一起丢失。

## 忘记密码 / 重新初始化

如果拥有 Docker 主机权限，可以停止容器并删除 `/data/auth.json`，再启动容器重新进入首次设置。使用旧认证环境变量的部署还需要先删除对应环境变量，否则它们会再次自动迁移。

首次初始化完成前，不要把 3001 端口直接暴露到公网。
