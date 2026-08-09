# Homepage Admin v0.3.4 升级说明

v0.3.4 主要修复 Widget Schema 管理页的时间显示，并把自动同步从环境变量固定配置升级为可在后台持久化管理的计划任务。

## 主要变化

### 1. 最后同步 / 下次计划显示浏览器本地时间

Schema 缓存内部仍使用 UTC ISO 时间（例如 `2026-08-09T18:12:32Z`），保证跨时区一致；页面不再直接显示原始 UTC 字符串，而是由浏览器转换为当前系统本地时间。鼠标悬停仍可查看原始 UTC 值。

### 2. 自动同步计划可视化配置

进入 **Widget 中心 → Schema 管理 → 自动同步计划**，可以直接配置：

- 开启 / 关闭自动同步；
- 固定间隔：1–720 小时；
- 每天固定时间：例如 `03:00`；
- IANA 时区：例如 `Asia/Shanghai`、`Asia/Tokyo`、`Europe/London`、`UTC`；
- 一键使用当前浏览器时区；
- 恢复环境变量默认值。

后台配置写入 `/data/admin-settings.json`，不会修改 Homepage YAML，也不要求修改 Portainer Stack。修改后最长约 1 分钟生效，不需要重启容器。

如果选择“每天固定时间”，调度器会按选定时区判断当天是否已执行；手动同步也会更新最后同步时间，因此不会在同一计划窗口重复拉取。

### 3. 页面文案改为版本无关

删除 Schema 管理和服务编辑页中诸如“v0.3.2 ……”的固定版本描述，避免升级后页面仍显示旧版本号。

### 4. 环境变量仍可作为默认值

新增 / 保留以下默认项：

```env
WIDGET_SCHEMA_AUTO_SYNC=true
WIDGET_SCHEMA_SYNC_MODE=interval
WIDGET_SCHEMA_SYNC_INTERVAL_HOURS=24
WIDGET_SCHEMA_SYNC_TIME=03:00
WIDGET_SCHEMA_TIMEZONE=Asia/Shanghai
WIDGET_SCHEMA_REF=dev
```

只要在后台保存过计划，`/data/admin-settings.json` 中的值优先；点击“恢复环境默认”后重新使用环境变量默认值。

Docker 镜像增加系统 `tzdata`，用于 IANA 时区调度。

## 升级

网页上传用户推荐解压：

```text
homepage-admin-v0.3.4-web-upload.zip
```

该网页上传包不包含隐藏的 `.github` 目录；你当前已经成功运行的 Workflow 不需要再次修改。

提交信息建议：

```text
Release v0.3.4
```

Actions 绿色后，在 Portainer 重新拉取：

```text
ghcr.io/aspeternity/homepage-admin:latest
```

升级后检查：

```bash
curl -s http://127.0.0.1:3001/healthz ; echo
```

应显示 `0.3.4`。
