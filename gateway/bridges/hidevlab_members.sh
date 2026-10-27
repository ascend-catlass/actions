#!/usr/bin/env bash
# 把 stdin 的「姓名 手机号」逐行注册到 HiDevLab。
#
# 网关只调用本脚本，不含任何加成员逻辑。
# 本脚本转调经过改造的 hidevlab 客户端。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${HIDEVLAB_PYTHON:-python3}"
CLIENT="${HIDEVLAB_DIR:-$HERE/hidevlab}/hidevlab_members.py"

if [[ ! -f "$CLIENT" ]]; then
  printf '{"ok": false, "error": "client_missing"}\n'
  exit 1
fi

# 把 stdin 原样交给客户端；它负责解析、校验、写入
exec "$PY" "$CLIENT" "$@"
