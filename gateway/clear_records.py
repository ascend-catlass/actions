"""清空网关的触发记录。

默认只删测试（dry_run）记录，保留真实转发、名单拦截、鉴权失败等。
每次合入后跑一次，让控制台只留真实数据。

用法：
    python3 clear_records.py                    # 只删 dry_run
    python3 clear_records.py --outcomes all     # 全清
    python3 clear_records.py --outcomes ignored,dry_run
    python3 clear_records.py --repo cann/catlass
"""
from __future__ import annotations

import argparse
import sys

# 本文件与 gateway.py 同级；容器里以 /app 为工作目录，
# 因此直接按模块名导入，而不是包路径。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gateway import clear_events  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcomes", default="dry_run",
                        help="逗号分隔的结果类型；all 表示全部清空")
    parser.add_argument("--repo", default=None, help="限定某个仓库")
    args = parser.parse_args(argv)

    raw = (args.outcomes or "").strip()
    outcomes = None if raw.lower() == "all" else [o.strip() for o in raw.split(",") if o.strip()]

    n = clear_events(outcomes, args.repo)
    if n < 0:
        print("清空失败", file=sys.stderr)
        return 1
    label = "全部" if outcomes is None else ", ".join(outcomes)
    target = f"（{args.repo}）" if args.repo else ""
    print(f"已删除 {n} 条记录：{label}{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
