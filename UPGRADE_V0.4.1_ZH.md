# Homepage Admin v0.4.1 升级说明

v0.4.1 继续完善 v0.4.0 的多 Docker 主机管理，重点解决 `docker.yaml` 自动发现 Server 无法在可视化界面编辑/删除的问题，并在所有删除动作前加入服务依赖检查。

## 主要变化

1. `docker.yaml` Server 现在与 Admin 自定义主机一样显示“测试连接 / 编辑 / 删除”。
2. 可视化编辑支持 Remote HTTP/HTTPS 与 Unix Socket。Remote 可修改 Host、Port、Protocol；Socket 可修改 socket 路径。
3. 编辑器只改它认识的基础字段；现有 `headers`、`tls` 与其他未知键会保留，敏感 Header 不会回显到浏览器。
4. Docker 主机卡片显示当前 Server 被多少服务引用，并预览服务名。
5. 删除进入独立向导，可按需选择：
   - 删除 Admin 自定义发现连接；
   - 删除 `docker.yaml` Server；
   - 删除 Server 时同时清除引用服务中的 `server` 与 `container`。
6. 如果 `docker.yaml` Server 正被服务引用，执行删除必须输入 `DELETE`。选择保留服务引用时，服务仍存在，但 Docker 状态会失效，直到重新配置同名 Server。
7. 对“Admin 自定义 + 已映射 docker.yaml”的主机，默认删除选项只勾选 Admin 自定义层，避免误删 Homepage Server。

## 升级

解压 `homepage-admin-v0.4.1-web-upload.zip` 后覆盖上传仓库普通文件即可。本包不包含 `.github`，现有成功 Workflow 不需要修改。

Commit message 建议：

```text
Release v0.4.1
```

Actions 绿色后在 Portainer 重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。HomePage、Docker Proxy、共享网络和 MySQL 均无需修改。

## 建议验收

- 打开 Docker 主机管理，确认 `local-docker` 现在显示“编辑”和“删除”。
- 编辑 `local-docker`，确认 Host/Port/Protocol 能保存，现有高级配置不会丢失。
- 进入删除向导，确认能看到使用该 Server 的服务数量与名称。
- 对自定义 Game-Server VM 测试“只删除 Admin 自定义发现连接”，确认 `docker.yaml` 中的 `game-server` 仍保留。
- 对测试 Server 验证“删除 Server + 清除服务 Docker 关联”，确认服务本身和 Widget 仍保留。
