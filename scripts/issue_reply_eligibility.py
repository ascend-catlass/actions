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


def eligibility(issue, roles, repository):
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
        return {"analyze": False, "assign": False, "reason": "issue-is-not-open"}
    if author.casefold() in members:
        return {"analyze": False, "assign": True, "atomgit_id": author,
                "reason": "author-is-committer-or-maintainer"}
    return {"analyze": True, "assign": False, "reason": "author-is-not-committer-or-maintainer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue-file", type=Path, required=True)
    parser.add_argument("--roles-file", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    result = eligibility(json.loads(args.issue_file.read_text(encoding="utf-8")),
                         json.loads(args.roles_file.read_text(encoding="utf-8")),
                         args.repository)
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
