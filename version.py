"""
声明后端与前端发布版本。
"""

# 软件版本：本精简版独立发版，与应用中心 fpk 版本保持一致。
# 应用内更新检查以此版本与本仓库（wu155867/moviepilot-fnos-lite）Release 标签比较。
APP_VERSION = 'v1.0.9'
# 前端版本：上游 MoviePilot 前端基线，仅作展示，不参与任何更新判定。
FRONTEND_VERSION = 'v3.1.9'
# 本版本要求的最低 Docker 镜像系统基线（ISO 日期），与镜像内 /etc/moviepilot/system-baseline 比较。
# 低于该值的镜像拒绝应用内更新，提示用户先更新 Docker 镜像。只在修复严重系统级漏洞时提高，
# 且在同一发布中把 docker/system-baseline 改成相同日期，保证新镜像自身满足要求。
# 2026-01-01 是基线机制引入前的下限，旧镜像缺少基线文件时按此值处理，因此不拦截任何更新。
MIN_SYSTEM_BASELINE = '2026-01-01'
