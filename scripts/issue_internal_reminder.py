"""给内部作者（committer / maintainer / 内部开发者）发闭环提示。

外部作者的 Issue 走 AI 分析回复；自己人不需要分析，但要提示及时闭环。
本脚本负责这类固定文案的发布，并在发之前查重，避免重复提醒。

用法：
    python3 -m scripts.issue_internal_reminder --issue-url <URL> [--publish]

不带 --publish 时只做判断并打印结果，不写评论。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MARKER = "<!-- issue-internal-reminder:v1 -->"

# 固定文案。语气面向社区成员，说明下一步动作。
MESSAGE = """{greeting}请注意及时闭环该 Issue；若有需要，请在 SIG 例会上介绍相关的工作。"""


def role_of(reason: str) -> str:
    """把 eligibility 的 reason 映射成称呼。"""
    if reason == "author-is-committer-or-maintainer":
        return "Maintainer/Committer"
    if reason == "author-is-internal-developer":
        return "开发者"
    return ""


def compose(reason: str) -> str:
    role = role_of(reason)
    greeting = f"{role}你好，" if role else "你好，"
    return f"{MARKER}\n{MESSAGE.format(greeting=greeting).strip()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--reason", required=True,
                        help="eligibility 输出的 reason，决定称呼")
    parser.add_argument("--publish", action="store_true",
                        help="实际写入评论；缺省只打印")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    body = compose(args.reason)
    print(body)
    print()

    if args.dry_run or not args.publish:
        print("未发布（缺少 --publish）")
        return 0

    # 延迟导入，避免无 token 的场景也要求装依赖
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from atomgit_issue_reply import Client  # noqa: E402

    token = os.environ.get("ATOMGIT_TOKEN") or os.environ.get("GITCODE_TOKEN")
    if not token:
        print("缺少 ATOMGIT_TOKEN/GITCODE_TOKEN，跳过发布", file=sys.stderr)
        return 1

    client = Client(args.issue_url, token)

    # 查重：已有同样提示就不再发
    for c in client.comments():
        existing = c.get("body") or ""
        if MARKER in existing:
            print("已存在闭环提示，跳过")
            return 0

    result = client.request("POST", f"{client.root}/issues/{client.number}/comments",
                            {"body": body})
    url = result.get("html_url") if isinstance(result, dict) else None
    print(f"已发布: {url or '(无 url)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
