# fnos 原生部署说明（飞牛 x86_64，无 Docker）

## 一、在 NAS 上手工跑通（先验证，再打包）

1. 把整个 `MoviePilot` 项目目录拷到 NAS（如 `/vol1/1000/apps/MoviePilot`）
2. 执行部署：
   ```bash
   cd /vol1/1000/apps/MoviePilot
   bash fnos/deploy.sh
   ```
   自动完成：下载 Python 3.14 独立运行时 → 建 venv → 清华镜像装依赖 → 生成 fnos.env
3. 启动 / 状态 / 停止：
   ```bash
   bash fnos/cmd/main start
   bash fnos/cmd/main status
   bash fnos/cmd/main stop
   ```
4. 浏览器访问 `http://<NAS_IP>:3011`，验证：首次初始化 → 设定 TMDB → 目录扫描 → 刮削 → 入库

## 二、验证通过后的 FPK 打包

按飞牛 FPK 结构组装：
```
manifest            <- fnos/manifest（需按 developer.fnnas.com 文档补全字段）
cmd/main            <- fnos/fpk/cmd/main（生命周期：start/stop/status，root 运行 + setpriv 降权）
cmd/port_sync.py    <- fnos/fpk/cmd/port_sync.py（端口同步到 ui/config、manifest、数据库）
cmd/install_callback、config_callback <- 落盘向导端口并同步登记
config/privilege    <- fnos/fpk/config/privilege（run-as=root，见 fpk/README.md）
wizard/install      <- fnos/wizard/install（JSON 表单，服务端口）
wizard/config       <- fnos/wizard/config（安装后可在设置页改端口）
app/                <- 整个项目（含 runtime/python 与 .venv-linux）
```
用官方 fnpack CLI 构建 .fpk，在飞牛「应用中心 → 手动安装」实测。

## 三、注意事项

- ffmpeg：MoviePilot 截图转码用系统 ffmpeg，fnOS 自带，无需捆绑
- 防火墙：3011 端口仅建议内网访问
- qBittorrent：在 Web 设定页配置下载器地址与账号，注意路径映射与 NAS 目录一致
- 数据目录：CONFIG_PATH 指向项目内 config/，升级时保留该目录与 fnos.env 即可
