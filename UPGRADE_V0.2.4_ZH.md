# 从 v0.2.3 升级到 v0.2.4

v0.2.4 是一个以“页面设置无损保存”和“Docker 图标推荐修复”为重点的小版本。**不需要修改 HomePage Stack、PGID、`docker.yaml`、`homepage-tools` 或 Docker Proxy。**

## 0. 如果 v0.2.3 已经把背景变清晰，先恢复 settings.yaml

v0.2.4 不会主动猜测并改写已经被 v0.2.3 改坏的 `settings.yaml`。

最安全的方法：进入 **备份回滚**，找到“点击页面设置保存”之前自动生成的 `settings.yaml` 备份并回滚。

也可以在高级编辑中确认原来的背景块包含你实际使用的滤镜，例如：

```yaml
background:
  image: https://...
  blur: ""
  saturate: 70
  brightness: 95
  opacity: 80
```

恢复后刷新 Homepage，确认背景重新回到原来的效果。

> 在 v0.2.4 部署完成前，建议不要继续用 v0.2.3 的“页面设置 → 保存设置”。

## 1. 上传代码

使用 `homepage-admin-v0.2.4-web-upload.zip` 覆盖上传到现有 `Aspeternity/homepage-admin` 仓库。

Commit message：

```text
Release v0.2.4
```

## 2. 等待 GitHub Actions

等待 `Test and publish Docker image` 全部变绿。

## 3. 更新 Portainer

只更新 `homepage-admin` Stack 并重新拉取：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

不修改现有 Homepage / Proxy / 网络配置。

验证版本：

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应返回：

```json
{"status":"ok","version":"0.2.4"}
```

## 4. 验证页面设置修复

1. 先确认 Homepage 当前背景正常。
2. 打开 **页面设置**。
3. 什么都不要修改，直接点击 **保存设置**。
4. 页面应提示“未检测到设置变化”，并且：
   - Homepage 背景外观不变；
   - `settings.yaml` 不被重写；
   - 不生成新的备份组。
5. 如果原 YAML 有 `blur: ""`，保存后它仍然存在。

## 5. 验证 Docker 图标

在 Docker 发现中打开 Lsky Pro 导入向导：

```text
图标: mdi-image-multiple
```

右侧预览应显示图片类 MDI 图标。Komari 和 MoviePilot 分别使用：

```text
mdi-server-network
mdi-movie-open
```

已经保存到 `services.yaml` 的旧 `sh-lskypro` 不会被后台自动篡改；请在服务编辑器里手动改为新图标，或者继续使用你自己的 URL / 本地图标。
