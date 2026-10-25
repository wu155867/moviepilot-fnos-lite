# FPK 打包说明（fnOS 原生应用）

NAS 上打包目录：`/vol1/1000/apps/fpk-build/moviepilot-fnos-lite/`

结构：
- `manifest`：appname=moviepilot-fnos-lite, platform=x86, source=thirdparty, service_port=3011
- `config/resource`（`{"data-share":{"shares":[]}}`）、`config/privilege`（run-as=package）
- `cmd/main`：FPK 生命周期脚本（本目录 main 的 NAS 版）。要点：
  - APP_DIR 用 `$(dirname $0)/../target` 解析（安装后载荷在 `/vol1/@appcenter/<app>`，`/var/apps/<app>/target` 是其软链）
  - 必须导出 **CONFIG_DIR**（不是 CONFIG_PATH），指向 `TRIM_PKGVAR/config`，否则 user.db 落到只读的包目录
  - start 快速返回（最多 6s 健康检查），状态由 `status` 子命令汇报，避免 appcenter 启动超时 11000
- `app/`：MoviePilot 载荷（含 `.venv-linux`、`runtime/python`）
- `ICON.PNG` / `ICON_256.PNG` + `app/ui/`（config + images，桌面入口）

关键坑（已踩过）：
1. `.venv-linux/bin/python3` 等软链必须是**包内相对路径**；装包前跑 `fix_links.py` 把指向旧部署目录的绝对软链改写为相对（venv 的 pyvenv.cfg 同步改）
2. `fnpack build` 需要 sudo；`.fpk` 是 tar.gz
3. `appcenter-cli install-fpk` 必须带 `-e env文件`（可为空文件），否则报 code 10107
4. 升级只能卸载重装，install-fpk 不覆盖已装应用

安装：
```
sudo appcenter-cli install-fpk -e /tmp/empty.env moviepilot-fnos-lite.fpk -v 1
sudo appcenter-cli start moviepilot-fnos-lite
```
