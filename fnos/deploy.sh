#!/bin/bash
# MoviePilot fnos-lite 飞牛 NAS (x86_64) 原生部署脚本
# 用法: 把整个项目目录拷到 NAS 后，在项目根目录执行 bash fnos/deploy.sh
# 产物: <项目根>/runtime/python  内置 Python 3.14
#       <项目根>/.venv-linux     独立虚拟环境
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY_VERSION="3.14.9"
PYS_URL="https://gh-proxy.com/https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-${PY_VERSION}+20261021-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

echo "==> 1/4 下载 Python ${PY_VERSION} 运行时"
mkdir -p "$ROOT/runtime"
if [ ! -x "$ROOT/runtime/python/bin/python3" ]; then
  curl -fL "$PYS_URL" -o /tmp/python314.tar.gz
  tar -xzf /tmp/python314.tar.gz -C "$ROOT/runtime"
  mv "$ROOT/runtime/python" "$ROOT/runtime/python" 2>/dev/null || true
fi
PY="$ROOT/runtime/python/bin/python3"
"$PY" --version

echo "==> 2/4 创建虚拟环境"
"$PY" -m venv "$ROOT/.venv-linux"
VPIP="$ROOT/.venv-linux/bin/pip"

echo "==> 3/4 安装依赖（清华镜像）"
"$VPIP" install -q --upgrade pip
"$VPIP" install -q -i "$PIP_MIRROR" $(.venv-linux/bin/python -c "import tomllib;print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

echo "==> 4/4 写入默认环境配置"
mkdir -p "$ROOT/config"
cat > "$ROOT/fnos.env" <<EOF
HOST=0.0.0.0
PORT=3011
CONFIG_PATH=$ROOT/config
EOF

echo "部署完成。启动: bash fnos/cmd/main start   状态: bash fnos/cmd/main status"
