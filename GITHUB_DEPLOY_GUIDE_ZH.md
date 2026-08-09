# Homepage Admin: GitHub + GHCR + Portainer 逐步部署指南

这份指南面向第一次使用 GitHub / GitHub Actions / GHCR 的用户。

最终目标：

```text
修改源码 -> 上传/提交到 GitHub -> GitHub Actions 自动测试和构建
        -> GHCR 发布 Docker 镜像 -> Portainer 直接拉取并部署
```

最终镜像地址形式：

```text
ghcr.io/你的GitHub用户名/homepage-admin:latest
```

## 一、创建 GitHub 仓库

1. 登录 GitHub。
2. 右上角点击 `+`，选择 `New repository`。
3. `Repository name` 填：`homepage-admin`。
4. 第一版建议选择 `Public`，这样源码和后续镜像都更容易公开使用。注意：仓库公开不代表 GHCR 包一定自动公开，GHCR 包发布后仍需单独确认可见性。
5. 不要勾选自动创建 README、.gitignore 或 License，因为本项目已经自带这些文件。
6. 点击 `Create repository`。

创建完成后停留在仓库页面。

## 二、把项目源码上传到 GitHub

1. 在电脑上解压 `homepage-admin-v0.2.0.zip`。
2. 打开解压后的项目文件夹，确认能看到：
   - `.github/`
   - `app/`
   - `Dockerfile`
   - `docker-compose.ghcr.yml`
   - `README.md`
   - `requirements.txt`
3. 回到刚创建的 GitHub 仓库。
4. 点击 `uploading an existing file`；如果仓库已经有文件，则点击 `Add file` -> `Upload files`。
5. 将“项目文件夹里面的所有文件和文件夹”拖入上传区域。不要只上传 ZIP 文件。
6. 确认上传列表里能看到 `.github/workflows/docker-publish.yml`。这是自动构建镜像最关键的文件。
7. 页面底部 `Commit changes` 保持默认即可，提交说明可以写：`Initial Homepage Admin v0.2.0`。
8. 点击 `Commit changes`。

重要：项目中的 `.gitignore` 已经排除 `.env`。以后不要把真实密码、Session Secret、Homepage API Key 等提交到 GitHub。

## 三、确认 GitHub Actions 已经自动运行

1. 打开仓库顶部的 `Actions` 标签页。
2. 如果 GitHub 第一次询问是否启用 Actions，按页面提示启用。
3. 找到工作流：`Test and publish Docker image`。
4. 点击最新一次运行。
5. 里面应看到两个 Job：
   - `Run tests`
   - `Build and publish image`
6. 等待两个 Job 都显示绿色对勾。

第一次多架构构建可能需要几分钟。

如果 `Build and publish image` 报权限错误：

1. 仓库顶部进入 `Settings`。
2. 左侧选择 `Actions` -> `General`。
3. 找到 `Workflow permissions`。
4. 通常保留默认即可，因为工作流本身已经声明 `packages: write`；如果账户/组织策略阻止写包，需要允许 Actions 写入 Packages。
5. 保存后回到 `Actions`，打开失败的运行，点击 `Re-run jobs`。

## 四、找到刚生成的 GHCR 镜像

成功运行后：

1. 回到仓库首页。
2. 在仓库右侧或 GitHub 个人主页的 `Packages` 区域找到 `homepage-admin`。
3. 打开这个 Package。
4. 你应该能看到 `latest` 标签，以及类似 `sha-xxxxxxx` 的标签。

镜像地址：

```text
ghcr.io/你的GitHub用户名/homepage-admin:latest
```

注意 GitHub 用户名在镜像地址里建议全部使用小写。

## 五、把 GHCR Package 改成 Public

首次发布的个人 GHCR Container Package 默认可能是 Private。要让 Docker / Portainer 无需登录即可拉取：

1. 打开 `homepage-admin` Package 页面。
2. 点击右侧的 `Package settings`。
3. 找到 `Danger Zone` 或包可见性相关区域。
4. 选择 `Change visibility`。
5. 改成 `Public`。
6. 按 GitHub 页面要求输入确认文字并确认。

这是“仓库 Public”和“镜像 Public”两个不同设置。最终请确认 Package 页面显示为 Public。

## 六、先在 Docker VM 测试能否直接拉镜像

SSH 登录 Docker VM，执行：

```bash
docker pull ghcr.io/你的GitHub用户名/homepage-admin:latest
```

成功时会下载镜像，并看到类似：

```text
Status: Downloaded newer image for ghcr.io/.../homepage-admin:latest
```

然后可以检查：

```bash
docker images | grep homepage-admin
```

如果提示 `denied` / `unauthorized`，首先检查第五步，确认 GHCR Package 已经改成 Public。

## 七、在 Portainer 中部署

### 1. 准备数据目录

在 Docker VM 上执行：

```bash
mkdir -p /opt/docker/homepage-admin/data
chown -R 1000:1000 /opt/docker/homepage-admin/data
```

当前已确认的 Homepage 配置目录是：

```text
/opt/docker/HomePage/data/config
```

### 2. 打开 Portainer Stack

1. 登录 Portainer。
2. 进入 Docker Environment。
3. 点击 `Stacks` -> `Add stack`。
4. Name 填 `homepage-admin`。
5. 选择 `Web editor`。

### 3. 粘贴 v0.2.0 Compose

直接复制项目里的 `docker-compose.ghcr.yml`。这个文件已经使用：

```text
ghcr.io/aspeternity/homepage-admin:latest
/opt/docker/HomePage/data/config:/config
/opt/docker/homepage-admin/data:/data
```

v0.2.0 Compose 有两个服务：

```text
homepage-admin
homepage-admin-docker-proxy
```

第二个容器专门做 Docker 只读发现，不映射宿主机端口。

### 4. 添加 Portainer 环境变量

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你自己设置的强密码
SESSION_SECRET=至少32位的随机字符串
HOMEPAGE_URL=http://10.10.1.11:3000
ADMIN_ALLOWED_HOSTS=*
ADMIN_COOKIE_SECURE=false
PUID=1000
PGID=1000
TZ=Asia/Shanghai
DOCKER_PUBLIC_HOST=10.10.1.11
```

生成 Session Secret：

```bash
openssl rand -hex 32
```

### 5. 部署并验证

点击 `Deploy the stack`。然后检查：

```bash
docker ps --filter name=homepage-admin
```

应该看到主后台和 Docker discovery sidecar。访问：

```text
http://10.10.1.11:3001
```

左侧应出现 `Docker 发现`。

## 八、以后如何更新

以后源码发生修改，只要新的代码提交到 GitHub `main` 分支：

1. GitHub Actions 自动测试。
2. 自动构建新的 `latest` 镜像。
3. 自动推送到 GHCR。

Portainer 更新：

1. 打开 `Stacks` -> `homepage-admin`。
2. 点击 `Editor`。
3. 使用 `Update the stack`。
4. 如果 Portainer 页面提供 `Re-pull image` / `Pull latest image` 选项，勾选它。
5. 更新 Stack。

Compose 中已经写入：

```yaml
pull_policy: always
```

因此重新创建容器时会请求最新镜像。

也可以在 Docker VM 终端手动执行：

```bash
docker pull ghcr.io/你的GitHub用户名/homepage-admin:latest
```

## 九、发布正式版本号

当前工作流支持 Git Tag，例如：

```text
v0.2.0
v0.2.1
v1.0.0
```

创建 `v0.2.0` Tag 后，工作流会额外发布：

```text
homepage-admin:0.2.0
homepage-admin:0.2
```

日常部署推荐使用：

```text
:latest
```

如果你希望生产环境固定版本、不自动跨版本更新，则可以把 Portainer Compose 改成：

```yaml
image: ghcr.io/你的GitHub用户名/homepage-admin:0.2.0
```

## 十、常见故障

### GHCR 拉取提示 unauthorized

优先检查 Package 是否已经设置为 Public，而不只是 Repository 是 Public。

### Actions 没有运行

确认仓库中真的存在：

```text
.github/workflows/docker-publish.yml
```

并确认文件不是被上传成：

```text
homepage-admin-v0.2.0/.github/workflows/...
```

也就是说，仓库根目录应直接看到 `Dockerfile`、`README.md`、`app/`、`.github/`。

### Actions 测试成功，但发布失败

检查仓库 `Settings` -> `Actions` -> `General` 的 Workflow permissions，以及个人/组织是否限制 GitHub Packages。

### Portainer 能拉镜像但容器启动失败

依次检查：

```bash
docker logs homepage-admin
```

以及配置目录权限：

```bash
stat -c '%u:%g %n' /opt/docker/HomePage/data/config
stat -c '%u:%g %n' /opt/docker/homepage-admin/data
```

如果不是 `1000:1000`，将 Portainer 环境变量 `PUID` / `PGID` 改成实际拥有者，或者调整目录权限。
