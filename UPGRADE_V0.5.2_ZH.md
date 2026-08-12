# Homepage Admin v0.5.2 升级说明

v0.5.2 主要优化 Docker 部署模型与开源文档，不改变 Homepage YAML 数据结构。

## 默认部署更简单

新用户只需要运行一个 `homepage-admin` 容器，并挂载：

```text
/config -> Homepage 配置目录
/data   -> Homepage Admin 持久化目录
```

默认不再要求：

```text
homepage-tools 共享网络
Docker Socket Proxy
/var/run/docker.sock
与 Homepage 容器加入同一个 Docker Network
```

## Docker 发现改为明确的可选集成

如果需要 Docker 发现，在每台目标 Docker 主机部署只读 Docker Socket Proxy，并把宿主机 LAN IP / DNS 地址加入：

```text
Docker 发现 -> Docker 主机管理
```

Homepage Admin 与 Proxy 不要求处于同一个 Docker Network。

仓库新增：

```text
docker-compose.docker-proxy.example.yml
```

## 现有用户需要改吗？

不需要。

原来通过：

```text
DOCKER_DISCOVERY_URL
homepage-docker-proxy
homepage-tools
```

工作的部署仍然保持兼容，可以继续使用。

如果希望简化现有部署，可以改用新的单容器 `docker-compose.ghcr.yml`，再从 Docker 主机管理中配置目标 Docker API。

## 升级建议

升级前建议先在 Homepage Admin 的备份中心创建完整快照，然后：

```bash
docker compose pull
docker compose up -d
```

健康检查：

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应返回版本 `0.5.2`。
