# MP入库助手 (moviepilot-fnos-lite)

基于 [MoviePilot](https://github.com/jxxghp/MoviePilot) 裁剪的**飞牛 fnOS 原生应用**（FPK 格式），专注做好一件事：**影视文件的识别、刮削与整理入库**。原生运行、内置 Python 运行时，**无需 Docker**，安装即用。

> 上游项目：[jxxghp/MoviePilot](https://github.com/jxxghp/MoviePilot)（GPL-3.0）
> 本项目为函数级裁剪衍生版，遵守 GPL-3.0 协议开源。

## ✨ 功能

### 保留的核心功能
- **媒体识别**：文件名解析 + TMDB / 豆瓣 / Bangumi 元数据识别
- **TMDB 刮削**：海报、简介、演员等元数据自动刮削
- **目录扫描整理**：监控下载目录，识别 → 重命名 → 入库媒体库
- **qBittorrent 对接**：下载器管理与下载完成自动整理
- **Emby / Jellyfin / Plex** 媒体服务器对接
- **媒体库分类**：电影 / 电视剧按类型、类别自动归档

### 相比上游的定制（开箱即用默认值）
| 项目 | 默认行为 |
|---|---|
| 整理方式 | **硬链接**（不占双份空间，同卷秒完成） |
| 刮削元数据 | **开启** |
| 类型子目录（电影/电视剧） | **开启** |
| 类别子目录（华语/外语/动画等） | **开启** |
| TMDB API 域名 | `api.tmdb.org`（国内可直连，无需代理） |
| 中文片名兜底 | TMDB 无中文译名时，自动用豆瓣中文名命名（`中文名 英文名 (年份)`），利于飞牛播放器等对英文识别较弱的环境 |
| 广告文件过滤 | 10MB 以下小文件不参与整理 |
| 字幕/音轨 | 不会被误识别为独立影片入库 |

### 已移除的 PT 相关功能
- PT 站点认证、用户认证（不再有认证失败消息）
- 站点管理、站点数据刷新、站点资源更新
- 订阅、推荐（含相关定时任务与菜单）
- Indexer 索引器、Transmission/rTorrent 下载器
- Telegram / WeChat / Slack 等消息推送

## 📦 安装（飞牛 fnOS）

### 方式一：应用中心手动安装
1. 下载 [Releases](https://github.com/wu155867/moviepilot-fnos-lite/releases) 最新 `.fpk`
2. fnOS 桌面 → **应用中心** → 右上角菜单 → **手动安装** → 上传 fpk
3. 安装完成，桌面出现「MP入库助手」图标

### 方式二：命令行
```bash
sudo appcenter-cli install-fpk -e /tmp/empty.env moviepilot-fnos-lite-1.0.3.fpk -v 1
sudo appcenter-cli start moviepilot-fnos-lite
```

- 服务端口：**3011**（浏览器访问 `http://NAS_IP:3011`）
- 数据目录：`/vol1/@appdata/moviepilot-fnos-lite/`（配置、数据库、日志）
- 升级：先卸载再安装，**配置与数据库会保留**

## 🛠 打包（开发者）

详见 [`fnos/fpk/README.md`](fnos/fpk/README.md)，含 FPK 目录结构、生命周期脚本与踩坑记录。

## 📄 许可证

[GPL-3.0](LICENSE) © 基于 [MoviePilot](https://github.com/jxxghp/MoviePilot) 裁剪。
