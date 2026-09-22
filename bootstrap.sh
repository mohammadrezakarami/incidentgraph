#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
UV_VERSION=0.12.17
PYTHON_VERSION=3.12.14
UV_BIN="$PROJECT_ROOT/.tools/uv"

if [ ! -x "$UV_BIN" ]; then
  mkdir -p "$PROJECT_ROOT/.tools"
  curl --proto '=https' --tlsv1.2 -LsSf \
    "https://astral.sh/uv/$UV_VERSION/install.sh" \
    | env UV_INSTALL_DIR="$PROJECT_ROOT/.tools" sh
fi

ACTUAL_UV=$("$UV_BIN" --version | awk '{print $2}')
if [ "$ACTUAL_UV" != "$UV_VERSION" ]; then
  echo "Expected uv $UV_VERSION, found $ACTUAL_UV" >&2
  exit 2
fi

UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.tools/python" \
UV_CACHE_DIR="$PROJECT_ROOT/.tools/cache" \
  "$UV_BIN" python install --no-bin "$PYTHON_VERSION"

UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.tools/python" \
UV_CACHE_DIR="$PROJECT_ROOT/.tools/cache" \
  "$UV_BIN" sync --frozen --dev

npm --prefix "$PROJECT_ROOT/frontend" ci --ignore-scripts
npm --prefix "$PROJECT_ROOT/frontend" run verify-runtime

echo "Bootstrap complete. Copy .env.example to .env and replace CHANGE_ME values."
