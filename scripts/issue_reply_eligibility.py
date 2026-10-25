"""Decide whether an Issue author should receive automated analysis."""
import argparse
import json
import os
from pathlib import Path
import re

try:
    from .community_repo_roles import normalize_repository
except ImportError:
    from community_repo_roles import normalize_repository


# 标明重点写「这个仓库有问题 / 有建议」的标签。新 Issue 此刻通常还没有标签，
# 所以主要看正文；标签作为补充信号。
FEEDBACK_LABELS = {"bug-report", "bug", "question", "enhancement", "feature",
                   "documentation", "kind/feature"}

# 正文里能看出在反馈仓库问题的线索（中英文各取常见说法）。
FEEDBACK_HINTS = (
    "bug", "error", "crash", "fail", "incorrect", "wrong", "unexpected",
    "panic", "segfault", "out of bounds", "leak", "hang", "regression",
    "does not work", "doesn't work", "not work", "broken", "missing",
    "建议", "问题", "错误", "异常", "崩溃", "失败", "报错", "不支持",
    "无法", "不能", "期望", "应该是", "优化", "缺陷", "越界", "泄漏",
    "希望", "支持", "增加", "新增", "能否", "可否", "建议增加",
    "need", "support", "add", "request", "improve", "allow",
)


def _labels_of(issue):
    """取 Issue 上的标签名集合。"""
    out = set()
    for item in issue.get("labels") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name:
            out.add(name.strip())
    return out


def _looks_like_feedback(issue):
    """判断这条 Issue 是不是在反馈本仓库的问题。

    先看标签；新 Issue 一般没有标签，再看标题与正文的措辞。
    标题命中即可（例如标题就叫 Bug），正文命中则要求有实际内容，
    避免只有一个词的空 Issue 被当成反馈。
    """
    if _labels_of(issue) & FEEDBACK_LABELS:
        return True

    title = (issue.get("title") or "").casefold()
    body = (issue.get("body") or "").casefold()

    # 标题能说明问题就直接算反馈
    if any(hint in title for hint in FEEDBACK_HINTS):
        return True

    # 否则要看正文，且正文得有一定篇幅
    if len(body.strip()) < 20:
        return False
    return any(hint in body for hint in FEEDBACK_HINTS)


def eligibility(issue, roles, repository, developers=None):
    """判定 Issue 该收到哪种处理。

    规则（按顺序）：
      1. Issue 不是开启状态 -> 什么都不做
      2. 内容属于反馈（带反馈类标签，或正文明显在描述问题/建议）
         -> 跑 AI 分析并回复，不管作者是谁
      3. 否则 -> 发固定文案提示闭环；若作者是 committer/maintainer 则一并分配

    返回的 reason 取值固定，供 workflow 分支使用。
    """
    if not isinstance(issue, dict) or not isinstance(roles, dict):
        raise ValueError("Issue and role responses must be objects")
    if roles.get("repository") != normalize_repository(repository):
        raise ValueError("Role query does not match the Issue repository")
    user = issue.get("user")
    author = user.get("login") if isinstance(user, dict) else None
    if not isinstance(author, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", author):
        raise ValueError("Issue author login is missing or invalid")
    members = set()
    for field in ("maintainer_ids", "committer_ids"):
        values = roles.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value)
            for value in values
        ):
            raise ValueError(f"Invalid role list: {field}")
        members.update(value.casefold() for value in values)
    if issue.get("state") not in {"open", "opened"}:
        return {"analyze": False, "assign": False, "remind": False,
                "reason": "issue-is-not-open"}

    is_member = author.casefold() in members

    # 反馈类：说这个仓库有问题的，就分析并回复。
    # 作者是 committer/maintainer 时不发 AI 回复（他们自己判断即可），
    # 但内容仍会被分析，标签照常应用。
    if _looks_like_feedback(issue):
        if is_member:
            return {"analyze": False, "assign": True, "remind": True,
                    "atomgit_id": author, "reason": "author-is-committer-or-maintainer"}
        return {"analyze": True, "assign": False, "remind": False,
                "atomgit_id": None, "reason": "issue-is-feedback"}

    # 非反馈类：发固定提示；作者是自己人就顺带分配
    reason = ("author-is-committer-or-maintainer" if is_member
              else "author-is-internal-developer")
    return {"analyze": False, "assign": is_member, "remind": True,
            "atomgit_id": author, "reason": reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-file", type=Path, required=True)
    parser.add_argument("--roles-file", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--developers-file", type=Path, default=None,
                        help="可选。内部开发者名单，每行一个 AtomGit ID。")
    args = parser.parse_args()

    developers = []
    if args.developers_file and args.developers_file.is_file():
        developers = [line.strip() for line in
                      args.developers_file.read_text(encoding="utf-8").splitlines()
                      if line.strip() and not line.strip().startswith("#")]

    result = eligibility(json.loads(args.issue_file.read_text(encoding="utf-8")),
                         json.loads(args.roles_file.read_text(encoding="utf-8")),
                         args.repository, developers)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
        handle.write(f"analyze={str(result['analyze']).lower()}\n")
        handle.write(f"assign={str(result['assign']).lower()}\n")
    summary = ("Proceed with Issue analysis." if result["analyze"] else
               "Assign Issue to its author without model analysis." if result["assign"] else
               "Skip closed Issue.")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
        handle.write(f"{summary} Reason: `{result['reason']}`.\n")
    print(summary)


if __name__ == "__main__":
    main()
