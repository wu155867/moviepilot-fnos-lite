# FPK 打包说明（fnOS 原生应用）

NAS 上打包目录：`/vol1/1000/apps/fpk-build/moviepilot-fnos-lite/`

结构（对应本目录）：
- `manifest` ← `../manifest`：appname=moviepilot-fnos-lite, platform=x86, source=thirdparty, service_port=3011
- `config/privilege` ← `config/privilege`：**run-as=root**（见下文「为什么要 root」）
- `cmd/main` ← `cmd/main`：FPK 生命周期脚本
- `cmd/port_sync.py` ← 把端口同步到系统侧三处登记
- `cmd/install_callback` ← 安装后落盘向导端口并同步登记
- `cmd/config_callback` ← 设置页改端口后同步登记并重启
- `wizard/install`、`wizard/config` ← 来自 `../wizard/`（JSON 表单，字段名即环境变量名）
- `app/`：MoviePilot 载荷（含 `.venv-linux`、`runtime/python`）
- `ICON.PNG` / `ICON_256.PNG` + `app/ui/`（config + images，桌面入口）

## 端口机制（1.0.6 起）

飞牛的端口登记有三处，缺一处点桌面图标就会打不开：

| 位置 | 作用 |
| --- | --- |
| `/var/apps/<app>/manifest` 的 `service_port` | appcenter 启动应用时读它，注入 `TRIM_SERVICE_PORT` |
| `/vol1/@appcenter/<app>/ui/config` 的 `port` | 桌面入口地址 |
| PostgreSQL `appcenter` 库 `app_service` 表的 `url` / `default_url` | 应用中心「访问」按钮与桌面快捷方式解析的地址 |

只有 root 能同时改这三处（manifest 与数据库属 root/postgres，应用用户既无权限也无 sudo），
所以 `config/privilege` 用 `run-as=root`，`cmd/main` 在启动服务前用
`setpriv --reuid=$TRIM_UID --regid=$TRIM_GID --init-groups` 把进程降权回应用用户。

端口优先级（`cmd/main` 的 `pick_port`）：

1. `$TRIM_PKGVAR/port`（由 install/config 回调写入，是唯一真相）
2. 向导值 `$wizard_port`
3. manifest 的 `service_port`
4. 系统注入的 `$TRIM_SERVICE_PORT`
5. 兜底 3011

启动时还会调用 `port_sync.py` 幂等同步三处登记，等于自带自愈：即使回调没跑成功也能纠正。

## 关键坑（已踩过）

1. `.venv-linux/bin/python3` 等软链必须是**包内相对路径**；装包前跑 `fix_links.py` 把指向旧部署目录的绝对软链改写为相对（venv 的 pyvenv.cfg 同步改）
2. `fnpack build` 需要 sudo；`.fpk` 是 tar.gz
3. `appcenter-cli install-fpk` 必须带 `-e env文件`（可为空文件），否则报 code 10107；`-e` 的文件内容就是安装向导的输入（`wizard_port=3012` 等价于界面里填 3012）
4. 升级只能卸载重装，install-fpk 不覆盖已装应用；`/vol1/@appdata/<app>` 数据目录会保留
5. 生命周期脚本以 root 跑，`mkdir` 出来的 `$TRIM_PKGVAR/config` 属主是 root，应用用户写不进去（表现为 `Permission denied: config/app.env`）——main 里启动前统一 `chown -R`
6. `TRIM_PKGVAR` 别用 `$APP_DIR/../var` 推：`target` 是软链，`..` 会指到 `/vol1/@appcenter/var`
7. `appcenter-cli stop` 在上一次异常退出后可能杀不掉残留实例（pidfile 丢失），`cmd/main stop` 里额外按端口和 cmdline 兜底清理

## 构建与安装

```
sudo fnpack build -d moviepilot-fnos-lite          # 产出 moviepilot-fnos-lite.fpk
sudo appcenter-cli install-fpk -e /tmp/wiz.env moviepilot-fnos-lite-1.0.6.fpk -v 1
sudo appcenter-cli start moviepilot-fnos-lite
```
