# Homepage Admin v0.4.7 升级说明

v0.4.7 集中优化“顶部组件”，将原本的“类型 + YAML”通用编辑器升级成 Homepage Information Widget 可视化工作区。

## 主要变化

1. **官方 Info Widget 目录**
   - 当前官方文档列出的 12 类组件均进入目录。
   - 支持搜索、分类、已添加数量和官方文档入口。
   - 天气、Search、Datetime 会提示 Homepage 自身的靠右布局特性。

2. **专属表单**
   - Greeting / DateTime / Logo / Search / Resources / Glances / Open-Meteo / OpenWeatherMap / Stocks / UniFi / Kubernetes / Longhorn 均提供可视化字段。
   - Search 支持多个内置 Provider 和 Custom Search。
   - Resources 与 Glances 的磁盘路径支持每行一项。
   - DateTime 暴露常用 Intl.DateTimeFormat，同时保留高级 format YAML。

3. **依赖提示**
   - Stocks 检查 `providers.finnhub`。
   - Longhorn 检查 `providers.longhorn`。
   - Kubernetes 检查 `kubernetes.yaml` mode。
   - OpenWeatherMap 可使用共享 Provider 或组件级 API Key。

4. **兼容与安全**
   - 未覆盖字段继续保存在“其他配置 YAML”。
   - 未收录类型继续使用完整 YAML 编辑。
   - password / apiKey / key 等敏感内容不会明文回显。

## 升级

解压 `homepage-admin-v0.4.7-web-upload.zip`，覆盖上传 GitHub 仓库普通文件即可。Web Upload 包不包含 `.github`。

Commit message 建议：

```text
Release v0.4.7
```

Actions 绿色后重新拉取 `ghcr.io/aspeternity/homepage-admin:latest`。`/healthz` 应显示 `0.4.7`。
