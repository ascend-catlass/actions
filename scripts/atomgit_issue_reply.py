"""CATLASS Issue identity and discussion snapshots for manual fix tasks."""
from __future__ import annotations

import hashlib
import json
import re
try:
    from .atomgit_api import AtomGitAPI
except ImportError:
    from atomgit_api import AtomGitAPI

MARKER = "<!-- issue-assistant-reply:v1 -->"
LEGACY_MARKER = "<!-- trae-cn-issue-reply:v1 -->"


def parse_url(url):
    match = re.fullmatch(r"https://atomgit\.com/([\w.-]+)/([\w.-]+)/issues/([1-9][0-9]*)/?", url)
    if not match:
        raise ValueError("Expected an https://atomgit.com/owner/repo/issues/number URL")
    return match.groups()


class Client:
    def __init__(self, url, token):
        owner, repo, number = parse_url(url)
        self.root = f"/repos/{owner}/{repo}"
        self.number = number
        self.api = AtomGitAPI(token)

    def request(self, method, path, body=None):
        return self.api.request(method, path, body)

    def issue(self):
        return self.request("GET", f"{self.root}/issues/{self.number}")

    def comments(self):
        comments = []
        for page in range(1, 101):
            batch = self.request("GET", f"{self.root}/issues/{self.number}/comments?per_page=100&page={page}")
            if not isinstance(batch, list):
                raise ValueError("Unexpected AtomGit comments response")
            comments.extend(batch)
            if len(batch) < 100:
                return comments
        raise ValueError("Too many comments; refusing to analyze incomplete context")


def owned(comment, user_id):
    body = comment.get("body") or ""
    return (comment.get("user") or {}).get("id") == user_id and (MARKER in body or LEGACY_MARKER in body or "<!-- shared-actions:issue-reply:v1 -->" in body)


def snapshot(issue, comments, user_id):
    return {"issue": {key: issue.get(key) for key in ("number", "title", "body", "state")},
            "author_login": (issue.get("user") or {}).get("login"),
            "comments": [{key: comment.get(key) for key in ("id", "body", "updated_at")}
                         for comment in comments if not owned(comment, user_id)]}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def check_author_roles(issue, url, roles):
    if roles is None:
        return
    try:
        from .issue_reply_eligibility import eligibility
    except ImportError:
        from issue_reply_eligibility import eligibility
    owner, repo, _ = parse_url(url)
    if not eligibility(issue, roles, f"{owner}/{repo}")["analyze"]:
        raise ValueError("Issue author is ineligible for automated analysis and reply")
