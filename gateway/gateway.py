#!/usr/bin/env python3
"""
AtomGit → GitHub Actions 网关

职责（只做这些，其余交给 actions 仓）：
  1. 入站鉴权
  2. 按 object_kind 分派
  3. 做最少的字段级筛选
  4. 转发到 GitHub Actions

移植自 Cloudflare Worker（yuantao313/dev），从 JS 转 Python。
按需求做了选择性转移：
  - 评论者白名单    → 移到 actions 仓，网关不做
  - 标签分类逻辑    → 移到 actions 仓，网关不做
  - confidential    → 保留（涉隐私，越早挡越好）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import shlex
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from community_roster import CommunityRoster, describe_rules, parse_allow_list

# ---------------------------------------------------------------------------
# 配置（环境变量）
# ---------------------------------------------------------------------------

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


WEBHOOK_PASSWORD = env("WEBHOOK_PASSWORD")          # 入站密码
GITHUB_ACTIONS_TOKEN = env("GITHUB_ACTIONS_TOKEN")  # 调度 workflow 的凭据
GITHUB_REPO = env("GITHUB_REPO", "ascend-catlass/actions")
GITHUB_REF = env("GITHUB_REF_BRANCH", "main")

# 受管仓库表。格式（逗号分隔）：
#   owner/repo:sig          该仓库用这个 SIG 的名单，目标分支取 TARGET_BRANCH
#   owner/repo:sig:branch   额外指定该仓库要求的 PR 目标分支
# 例：cann/catlass:catlass,cann/ops-nn:ops-nn,cann/ops-basic:ops-basic:master
REPOS_SPEC = env("REPOS", "cann/catlass:catlass")
TARGET_BRANCH = env("TARGET_BRANCH", "master")
CI_PASSED_LABEL = env("CI_PASSED_LABEL", "ci-pipeline-passed")

MAX_BODY_BYTES = int(env("MAX_BODY_BYTES", str(64 * 1024)))
HTTP_TIMEOUT = float(env("HTTP_TIMEOUT", "10"))

# 社区名单：角色引用 + 显式用户名，逗号分隔
# 例: "@maintainer, @committer, internal_dev1"
ALLOW_LIST = env("ALLOW_LIST", "@maintainer, @committer")
SIG_NAME = env("SIG_NAME", "catlass")
ROSTER_CACHE = env("ROSTER_CACHE_FILE", "/tmp/community_roster_cache.json")
ROSTER_TTL = int(env("ROSTER_CACHE_TTL", "3600"))

# 数据目录：放在代码目录下（该目录已挂载，容器重建不丢）
DATA_DIR = env("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

# 触发记录库（供界面查询）
EVENTS_DB = env("EVENTS_DB", os.path.join(DATA_DIR, "events.db"))

# 允许名单配置文件（界面可编辑，容器重建不丢）
ALLOW_FILE = env("ALLOW_FILE", os.path.join(DATA_DIR, "allow_list.txt"))

# 外部命令桥接：网关不含业务逻辑，只把文本交给命令处理。
BRIDGE_CMD = env("BRIDGE_CMD", "")          # 空 = 未启用
BRIDGE_TRIGGER = env("BRIDGE_TRIGGER", "hidevlab-members")  # 评论触发词
BRIDGE_TIMEOUT = float(env("BRIDGE_TIMEOUT", "180"))

# 测试模式：请求头带此开关时，只做完整判断与记录，不真实调用 GitHub
# 请求头名固定为 X-Dry-Run，值需等于 DRY_RUN_SECRET（默认 "1"）
DRY_RUN_HEADER = env("DRY_RUN_HEADER", "x-dry-run")
DRY_RUN_SECRET = env("DRY_RUN_SECRET", "1")

log = logging.getLogger("gateway")


def parse_repos(spec: str, default_branch: str) -> dict[str, dict[str, str]]:
    """解析受管仓库表。

    返回 {仓库路径: {"sig": ..., "branch": ...}}。
    格式非法或为空时回落到 cann/catlass，保证服务仍可用。
    """
    out: dict[str, dict[str, str]] = {}
    for raw in (spec or "").split(","):
        token = raw.strip()
        if not token:
            continue
        parts = token.split(":")
        repo = parts[0].strip()
        if "/" not in repo:
            log.warning("仓库路径无效，已跳过: %s", token)
            continue
        sig = parts[1].strip() if len(parts) > 1 and parts[1].strip() else repo.split("/")[-1]
        branch = parts[2].strip() if len(parts) > 2 and parts[2].strip() else default_branch
        out[repo] = {"sig": sig, "branch": branch}
    if not out:
        log.warning("仓库表为空，回落到 cann/catlass")
        out["cann/catlass"] = {"sig": "catlass", "branch": default_branch}
    return out


REPOS = parse_repos(REPOS_SPEC, TARGET_BRANCH)
# 保留单一仓库时的便捷视图（兼容既有调用）
TARGET_REPOSITORY = next(iter(REPOS))

# 名单客户端按 SIG 缓存，一个 SIG 一个实例
_rosters: dict[str, CommunityRoster] = {}


def roster_for(repo: str) -> CommunityRoster:
    """取该仓库对应 SIG 的名单客户端。"""
    sig = (REPOS.get(repo) or {}).get("sig") or "catlass"
    client = _rosters.get(sig)
    if client is None:
        cache = ROSTER_CACHE.replace(".json", f"-{sig}.json") if len(REPOS) > 1 else ROSTER_CACHE
        client = CommunityRoster(sig=sig, cache_file=cache, cache_ttl=ROSTER_TTL)
        _rosters[sig] = client
    return client


# 默认实例（无仓库上下文时用，例如启动自检）
roster = roster_for(TARGET_REPOSITORY)


# ---------------------------------------------------------------------------
# 预留：字段判断接口
# ---------------------------------------------------------------------------

# 判断器签名： (payload, ctx) -> bool
# 返回 False 表示忽略该事件。
# 需要新增判断时，在 RULES 里加一条即可，不必改主流程。

Ctx = dict[str, Any]
Predicate = Callable[[dict[str, Any], Ctx], bool]


def _kind_is(*kinds: str) -> Predicate:
    """object_kind 属于给定集合。"""
    return lambda p, c: p.get("object_kind") in kinds


def _project_is(target: str) -> Predicate:
    """project.path_with_namespace 精确匹配。"""
    def check(p: dict[str, Any], c: Ctx) -> bool:
        return (p.get("project") or {}).get("path_with_namespace") == target
    return check


def _project_managed(p: dict[str, Any], c: Ctx) -> bool:
    """仓库在受管表内。"""
    return (p.get("project") or {}).get("path_with_namespace") in REPOS


def _mr_branch_is_target(p: dict[str, Any], c: Ctx) -> bool:
    """PR 目标分支等于该仓库要求的分支。"""
    repo = (p.get("project") or {}).get("path_with_namespace") or ""
    want = (REPOS.get(repo) or {}).get("branch") or TARGET_BRANCH
    return (p.get("merge_request") or {}).get("target_branch") == want


def _note_is_mr(p: dict[str, Any], c: Ctx) -> bool:
    """评论是针对 MergeRequest 的，且非系统评论。"""
    note = p.get("object_attributes") or {}
    return note.get("noteable_type") == "MergeRequest" and note.get("system") is not True


def _note_first_line_is(text: str) -> Predicate:
    """评论首行（去空白）恰好等于 text。用于「触发词 + 多行数据」的注释。"""
    def check(p: dict[str, Any], c: Ctx) -> bool:
        note = p.get("object_attributes") or {}
        value = note.get("note")
        if not isinstance(value, str):
            return False
        lines = [l for l in value.splitlines() if l.strip()]
        return bool(lines) and lines[0].strip() == text
    return check


def _note_text_is(text: str) -> Predicate:
    """评论内容去空白后恰好等于 text。"""
    def check(p: dict[str, Any], c: Ctx) -> bool:
        note = p.get("object_attributes") or {}
        value = note.get("note")
        return isinstance(value, str) and value.strip() == text
    return check


def _mr_branch_is(branch: str) -> Predicate:
    def check(p: dict[str, Any], c: Ctx) -> bool:
        return (p.get("merge_request") or {}).get("target_branch") == branch
    return check


def _mr_open(p: dict[str, Any], c: Ctx) -> bool:
    state = (p.get("merge_request") or {}).get("state")
    return state in ("opened", "open")


def _pr_open(p: dict[str, Any], c: Ctx) -> bool:
    state = (p.get("object_attributes") or {}).get("state")
    return state in ("opened", "open")


def _label_added(label: str) -> Predicate:
    """changes.labels 新增了 label（previous 里没有，current 里有）。"""
    def extract(items: Any) -> set[str]:
        if not isinstance(items, list):
            return set()
        out = set()
        for item in items:
            if isinstance(item, str):
                out.add(item)
            elif isinstance(item, dict):
                name = item.get("title") or item.get("name")
                if isinstance(name, str):
                    out.add(name)
        return out

    def check(p: dict[str, Any], c: Ctx) -> bool:
        change = (p.get("changes") or {}).get("labels") or {}
        previous = extract(change.get("previous"))
        current = change.get("current")
        if current is None:
            current = p.get("labels")
        current_set = extract(current)
        return label in current_set and label not in previous
    return check


def _issue_open_or_reopen(p: dict[str, Any], c: Ctx) -> bool:
    issue = p.get("object_attributes") or {}
    return issue.get("action") in ("open", "reopen") and issue.get("state") in ("open", "opened")


def _issue_not_confidential(p: dict[str, Any], c: Ctx) -> bool:
    return (p.get("object_attributes") or {}).get("confidential") is not True


def _iid_positive(*path: str) -> Predicate:
    """指定路径上的编号必须是正的安全整数。"""
    def dig(obj: Any, keys: tuple[str, ...]) -> Any:
        for key in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return obj

    def check(p: dict[str, Any], c: Ctx) -> bool:
        value = dig(p, path)
        return isinstance(value, int) and value > 0
    return check


# ---------------------------------------------------------------------------
# 触发记录（供界面查询最近 N 天）
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(EVENTS_DB, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with _db_lock, _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT    NOT NULL,
                action       TEXT,
                outcome      TEXT    NOT NULL,
                reason       TEXT,
                repo         TEXT,
                user         TEXT,
                iid          TEXT,
                kind         TEXT,
                workflow     TEXT,
                http_status  INTEGER,
                detail       TEXT,
                -- 事件分类：大类/小类，便于筛选与阅读
                category     TEXT,
                subtype      TEXT,
                -- 来源链接（AtomGit 上的 PR / Issue / 评论）
                source_url   TEXT,
                -- 目标运行（GitHub Actions）
                run_id       TEXT,
                run_url      TEXT,
                -- 触发者主页
                user_url     TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_outcome ON events(outcome)")

        # 老库补列（幂等）
        existing = {r[1] for r in conn.execute("PRAGMA table_info(events)")}
        for col, decl in [
            ("category", "TEXT"), ("subtype", "TEXT"),
            ("source_url", "TEXT"), ("run_id", "TEXT"), ("run_url", "TEXT"),
            ("user_url", "TEXT"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE events ADD COLUMN {col} {decl}")


def allow_file_for(repo: str | None = None) -> str:
    """该仓库的名单文件路径。只有多仓时才按仓库分文件。"""
    if not repo or len(REPOS) <= 1:
        return ALLOW_FILE
    safe = repo.replace("/", "__")
    return os.path.join(os.path.dirname(ALLOW_FILE), f"allow_list.{safe}.txt")


def get_allow_list(repo: str | None = None) -> tuple[str, str | None, str | None]:
    """读当前名单。返回 (表达式, 更新时间, 修改者)。

    配置文件不存在时回落到环境变量 ALLOW_LIST（首次启动的初始值）。
    文件格式：第一行可选注释，随后是名单表达式，也支持多行。
    """
    try:
        text = Path(allow_file_for(repo)).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ALLOW_LIST, None, None
    except Exception as exc:  # noqa: BLE001
        log.warning("读名单文件失败: %s", exc)
        return ALLOW_LIST, None, None

    updated_at = None
    updated_by = None
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 元信息行：# updated_at=... / # updated_by=...
        m = re.match(r"^#\s*(updated_at|updated_by)\s*=\s*(.+)$", line)
        if m:
            if m.group(1) == "updated_at":
                updated_at = m.group(2).strip()
            else:
                updated_by = m.group(2).strip()
            continue
        if line.startswith("#"):
            continue
        lines.append(line)

    value = ", ".join(lines) if lines else ALLOW_LIST
    return value, updated_at, updated_by


def set_allow_list(value: str, updated_by: str | None = None,
                   repo: str | None = None) -> None:
    """写名单到配置文件（原子替换）。"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = [
        "# 允许名单（界面可编辑，改完立即生效）",
        "# 语法：@maintainer / @committer / @committer:<子目录> / 显式用户名，逗号分隔",
        f"# updated_at={now}",
        f"# updated_by={updated_by or 'unknown'}",
        "",
        value,
        "",
    ]
    path = Path(allow_file_for(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(body), encoding="utf-8")
    tmp.replace(path)


def current_rules(repo: str | None = None) -> list:
    """当前生效的规则（每次都从文件读，支持界面即时修改）。"""
    expr, _, _ = get_allow_list(repo)
    return parse_allow_list(expr)


def validate_allow_list(value: str) -> tuple[bool, str]:
    """校验表达式。返回 (是否合法, 说明)。"""
    rules = parse_allow_list(value)
    if not rules:
        return True, "空名单表示不限制任何用户"
    unknown = []
    users = 0
    roles = 0
    for raw in re.split(r"[,\n]", value or ""):
        token = raw.strip()
        if not token or token.startswith("#"):
            continue
        if token.startswith("@"):
            m = re.match(r"^@([a-z_]+)(?::([A-Za-z0-9_./-]+))?$", token)
            if not m or m.group(1) not in ("maintainer", "committer"):
                unknown.append(token)
            else:
                roles += 1
        else:
            users += 1
    if unknown:
        return False, "无法识别的角色引用：" + ", ".join(unknown)
    return True, f"{roles} 个角色引用、{users} 个显式用户名"


def record_event(**fields: Any) -> None:
    """写一条触发记录。失败不影响主流程。"""
    try:
        with _db_lock, _db() as conn:
            conn.execute(
                """INSERT INTO events
                   (ts, action, outcome, reason, repo, user, iid, kind, workflow,
                    http_status, detail, category, subtype, source_url, run_id, run_url,
                    user_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    fields.get("action"), fields.get("outcome", "unknown"),
                    fields.get("reason"), fields.get("repo"), fields.get("user"),
                    fields.get("iid"), fields.get("kind"), fields.get("workflow"),
                    fields.get("http_status"), fields.get("detail"),
                    fields.get("category"), fields.get("subtype"),
                    fields.get("source_url"), fields.get("run_id"), fields.get("run_url"),
                    fields.get("user_url"),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("写事件记录失败: %s", exc)


def clear_events(outcomes: list[str] | None = None,
                  repo: str | None = None) -> int:
    """删除指定结果的记录。outcomes 为空时删全部。返回删除行数。"""
    where = []
    args: list[Any] = []
    if outcomes:
        where.append("outcome IN (" + ",".join("?" * len(outcomes)) + ")")
        args.extend(outcomes)
    if repo:
        where.append("repo = ?")
        args.append(repo)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    try:
        with _db_lock, _db() as conn:
            cur = conn.execute(f"DELETE FROM events{clause}", tuple(args))
            n = cur.rowcount
        log.info("清空记录 outcomes=%s repo=%s 删除 %d 行", outcomes, repo, n)
        return n
    except Exception as exc:  # noqa: BLE001
        log.warning("清空记录失败: %s", exc)
        return -1


def query_events(days: int = 7, limit: int = 500, repo: str | None = None,
                 include_ignored: bool = True,
                 include_dry_run: bool = True) -> list[dict[str, Any]]:
    """查最近 N 天的记录，可按仓库过滤并选择是否包含忽略请求与测试记录。"""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat(timespec="seconds")

    where = ["ts >= ?"]
    args: list[Any] = [cutoff_iso]
    if repo:
        where.append("repo = ?")
        args.append(repo)

    excluded = []
    if not include_ignored:
        excluded.append("ignored")
    if not include_dry_run:
        excluded.append("dry_run")
    for outcome in excluded:
        where.append("outcome != ?")
        args.append(outcome)

    args.append(limit)

    try:
        with _db_lock, _db() as conn:
            rows = conn.execute(
                f"SELECT * FROM events WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
                tuple(args),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        log.warning("查事件记录失败: %s", exc)
        return []


def event_stats(days: int = 7, repo: str | None = None,
                include_ignored: bool = True,
                include_dry_run: bool = True) -> dict[str, Any]:
    """按结果与动作聚合，可按仓库过滤并选择是否统计忽略请求与测试记录。"""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat(timespec="seconds")

    where = ["ts >= ?"]
    args: list[Any] = [cutoff_iso]
    if repo:
        where.append("repo = ?")
        args.append(repo)

    excluded = []
    if not include_ignored:
        excluded.append("ignored")
    if not include_dry_run:
        excluded.append("dry_run")
    for outcome in excluded:
        where.append("outcome != ?")
        args.append(outcome)

    cond = " AND ".join(where)

    try:
        with _db_lock, _db() as conn:
            by_outcome = {r["outcome"]: r["n"] for r in conn.execute(
                f"SELECT outcome, COUNT(*) n FROM events WHERE {cond} GROUP BY outcome",
                tuple(args))}
            by_action = {r["action"] or "-": r["n"] for r in conn.execute(
                f"SELECT action, COUNT(*) n FROM events WHERE {cond} GROUP BY action",
                tuple(args))}
            by_reason = {r["reason"] or "-": r["n"] for r in conn.execute(
                f"SELECT reason, COUNT(*) n FROM events WHERE {cond} AND reason IS NOT NULL "
                "GROUP BY reason ORDER BY n DESC LIMIT 20", tuple(args))}
            total = conn.execute(f"SELECT COUNT(*) n FROM events WHERE {cond}",
                                 tuple(args)).fetchone()["n"]
        return {"days": days, "total": total, "by_outcome": by_outcome,
                "by_action": by_action, "by_reason": by_reason}
    except Exception as exc:  # noqa: BLE001
        log.warning("统计失败: %s", exc)
        return {"days": days, "total": 0, "by_outcome": {}, "by_action": {}, "by_reason": {}}


# --------------------------- 路由表 ---------------------------
# 每条规则 = 一组判断 + 转发目标。
# 内置判断不够用时，可在 predicates.py 里加函数，然后在此引用。

ROUTES: list[dict[str, Any]] = [
    {
        "action": "rdv_compile",
        "category": "pr",
        "subtype": "comment/rdvcompile",
        "workflow": "test-atomgit-pr.yml",
        "requires_allow_list": True,
        "when": [
            _kind_is("note"),
            _project_managed,
            _note_is_mr,
            _note_text_is("rdvcompile"),
            # 白名单已移到 actions 仓，这里不过滤评论者
            _mr_branch_is_target,
            _mr_open,
            _iid_positive("merge_request", "iid"),
        ],
        "inputs": lambda p: {"pr_number": str((p.get("merge_request") or {}).get("iid"))},
    },
    {
        "action": "ci_passed",
        "category": "pr",
        "subtype": "label/cipassed",
        "workflow": "reply-atomgit-ci-passed.yml",
        "requires_allow_list": True,
        "when": [
            _kind_is("merge_request"),
            _project_managed,
            _pr_open,
            _label_added(CI_PASSED_LABEL),
            _iid_positive("object_attributes", "iid"),
        ],
        "inputs": lambda p: {"pr_number": str((p.get("object_attributes") or {}).get("iid"))},
    },
    {
        # 把评论正文交给外部命令处理（例如注册账号）。
        # 网关只负责取出正文并调用，不含任何业务逻辑。
        "action": "bridge_members",
        "category": "pr",
        "subtype": "comment/bridge",
        "bridge": True,
        "requires_allow_list": True,
        "when": [
            _kind_is("note"),
            _project_managed,
            _note_is_mr,
            _note_first_line_is(BRIDGE_TRIGGER),
            _iid_positive("merge_request", "iid"),
        ],
        # 传给桥接的是评论正文原文，由命令自行解析
        "bridge_text": lambda p: (p.get("object_attributes") or {}).get("note") or "",
    },
    {
        "action": "issue_analysis",
        "category": "issue",
        "subtype": "open",
        "workflow": "reply-atomgit-issue.yml",
        # 不在网关拦名单：名单内的人也要收到「请闭环」的固定提示。
        # 是否自己人通过 author_is_member 参数告诉下游，由下游决定
        # 跑 AI 分析还是只发固定文案。
        "requires_allow_list": False,
        "when": [
            _kind_is("issue"),
            _project_managed,
            _issue_open_or_reopen,
            _issue_not_confidential,
            _iid_positive("object_attributes", "iid"),
        ],
        "inputs": lambda p: {
            "issue_url": f"{ATOMGIT_WEB}/"
                         f"{(p.get('project') or {}).get('path_with_namespace')}/issues/"
                         f"{(p.get('object_attributes') or {}).get('iid')}",
            "publish": "true",
            # 自己人 -> 下游只发固定文案，不跑 AI
            "author_is_member": "true" if author_is_member(
                (p.get("project") or {}).get("path_with_namespace") or "",
                (p.get("user") or {}).get("username") or "") else "false",
        },
    },
]


def decide(payload: dict[str, Any]) -> dict[str, Any] | None:
    """按路由表决定动作。返回 None 表示忽略。"""
    ctx: Ctx = {"repo": (payload.get("project") or {}).get("path_with_namespace")
                or TARGET_REPOSITORY}
    for route in ROUTES:
        if all(check(payload, ctx) for check in route["when"]):
            return route
    return None


# ---------------------------------------------------------------------------
# 鉴权
# ---------------------------------------------------------------------------

def check_token(provided: str) -> bool:
    """常数时间比较，避免时序泄露。"""
    if not WEBHOOK_PASSWORD:
        return False
    if not provided:
        return False
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(WEBHOOK_PASSWORD.encode()).digest(),
    )


# ---------------------------------------------------------------------------
# 转发
# ---------------------------------------------------------------------------

def _gh_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_ACTIONS_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "atomgit-gateway",
        "Content-Type": "application/json",
    }


def dispatch(workflow: str, inputs: dict[str, Any]) -> tuple[int, str | None, str | None]:
    """触发 workflow。返回 (HTTP 状态码, run_id, run_url)。

    dispatch 接口本身不返回运行 ID，因此成功后立刻查一次最新运行。
    查询失败不影响转发结果，只是链接为空。
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow}/dispatches"
    body = json.dumps({"ref": GITHUB_REF, "inputs": inputs}).encode()
    try:
        req = urllib.request.Request(url, data=body, method="POST", headers=_gh_headers())
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        return exc.code, None, None
    except Exception as exc:  # noqa: BLE001
        log.warning("dispatch error: %s", exc)
        return 0, None, None

    if status != 204:
        return status, None, None

    # 记录发起时刻，用于筛选「本次」触发的运行
    since = datetime.now(timezone.utc)
    run_id, run_url = find_latest_run(workflow, since=since)
    return status, run_id, run_url


def find_latest_run(
    workflow: str,
    since: datetime | None = None,
    retries: int = 5,
    delay: float = 1.5,
) -> tuple[str | None, str | None]:
    """查该 workflow 最新一次运行。

    dispatch 与运行记录出现之间有延迟（实测数秒），且列表可能仍返回上一次
    运行，因此：
      - 只接受 created_at 不早于 since 的运行（允许 30 秒时钟偏差）
      - 多次重试等待记录出现
    查不到不影响转发结果，只是链接为空。
    """
    url = (f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/"
           f"{workflow}/runs?per_page=5&event=workflow_dispatch")
    cutoff = (since.timestamp() - 30) if since else None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_gh_headers())
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for r in data.get("workflow_runs") or []:
                created = r.get("created_at")
                if cutoff and created:
                    try:
                        ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        ts = None
                    if ts is not None and ts < cutoff:
                        continue          # 这是上一次的运行，跳过
                return str(r.get("id")), r.get("html_url")
        except Exception as exc:  # noqa: BLE001
            log.warning("查运行记录失败 (第 %d 次): %s", attempt + 1, exc)
        if attempt < retries - 1:
            time.sleep(delay)
    log.warning("未能定位本次触发对应的运行记录 workflow=%s", workflow)
    return None, None


# ---------------------------------------------------------------------------
# HTTP 处理
# ---------------------------------------------------------------------------

def profile_url_for(user: str | None) -> str | None:
    """AtomGit 用户主页链接。"""
    if not user:
        return None
    return f"{ATOMGIT_WEB}/{user}"


def _payload_facts(payload: dict[str, Any]) -> dict[str, Any]:
    """从 payload 提取用于记录与名单判断的字段。"""
    note = payload.get("object_attributes") or {}
    mr = payload.get("merge_request") or {}
    user = (payload.get("user") or {}).get("username")
    return {
        "kind": payload.get("object_kind"),
        "repo": (payload.get("project") or {}).get("path_with_namespace"),
        "user": user,
        "user_url": profile_url_for(user),
        "iid": mr.get("iid") or note.get("iid"),
        "files": _changed_files(payload),   # 预留：细粒度路径判断用
    }


# AtomGit 网页地址（可通过配置覆盖，便于换域名或测试环境）
# AtomGit 网页域名。gitcode.com 与 atomgit.com 是同一个站；
# 下游 parse_url 只接受 atomgit.com，所以统一用它。
ATOMGIT_WEB = env("ATOMGIT_WEB", "https://atomgit.com")


def source_url_for(payload: dict[str, Any], kind: str | None = None) -> str | None:
    """生成来源链接（AtomGit 上的 PR / Issue）。

    优先用 payload 自带的 URL 字段；没有则按仓库与编号拼。
    """
    note = payload.get("object_attributes") or {}
    mr = payload.get("merge_request") or {}
    repo = (payload.get("project") or {}).get("path_with_namespace")

    # 1) payload 自带字段（不同平台命名不一，逐个试）
    for container in (note, mr, payload):
        if not isinstance(container, dict):
            continue
        for key in ("html_url", "web_url", "target_url"):
            v = container.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v

    # 2) 按编号拼
    kind = kind or payload.get("object_kind")
    if not repo:
        return None
    if kind == "issue":
        iid = note.get("iid")
        if iid:
            return f"{ATOMGIT_WEB}/{repo}/issues/{iid}"
    if kind == "merge_request":
        iid = note.get("iid") or mr.get("iid")
        if iid:
            return f"{ATOMGIT_WEB}/{repo}/merge_requests/{iid}"
    if kind == "note":
        # 评论挂在 PR 或 Issue 上；不带锚点，避免拼出无效片段
        iid = mr.get("iid") or note.get("iid")
        noteable = note.get("noteable_type")
        if iid:
            path = "issues" if noteable == "Issue" else "merge_requests"
            return f"{ATOMGIT_WEB}/{repo}/{path}/{iid}"
    return None


def classify_outcome(payload: dict[str, Any], route: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """给事件打上大类/小类标签。

    命中路由时用路由定义；未命中时按事件自身特征推断，便于在界面上读懂。
    """
    if route:
        return route.get("category"), route.get("subtype")

    kind = payload.get("object_kind")
    note = payload.get("object_attributes") or {}
    if kind == "note":
        noteable = "pr" if note.get("noteable_type") == "MergeRequest" else "issue"
        if note.get("system") is True:
            return noteable, "system"
        return noteable, "comment/other"
    if kind == "merge_request":
        action = note.get("action") or note.get("state") or "update"
        return "pr", f"action/{action}"
    if kind == "issue":
        action = note.get("action") or note.get("state") or "update"
        return "issue", f"action/{action}"
    if kind == "push":
        return "push", "commit"
    return (kind, None) if kind else (None, None)


def _changed_files(payload: dict[str, Any]) -> list[str]:
    """事件涉及的文件列表。

    预留接口：目前 GitCode 的评论事件 payload 不含改动文件清单，
    因此通常返回空列表。将来若事件携带文件信息，在此解析即可，
    名单规则中的 @role:path 会自动优先使用规则自带的路径。
    """
    files: list[str] = []
    # PR/MR 事件可能带 changes 字段
    changes = payload.get("changes") or {}
    if isinstance(changes, dict):
        for key in ("files", "changed_files", "paths"):
            v = changes.get(key)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        files.append(item)
                    elif isinstance(item, dict):
                        p = item.get("path") or item.get("new_path") or item.get("file_path")
                        if isinstance(p, str):
                            files.append(p)
    return files


def run_bridge(text: str, timeout: float | None = None) -> tuple[bool, dict[str, Any]]:
    """把文本交给外部命令，返回 (是否成功, 结果)。

    命令从 stdin 读文本，向 stdout 写单行 JSON。
    网关不解析业务细节，只透传结果。
    """
    if not BRIDGE_CMD:
        return False, {"error": "bridge_not_configured"}

    try:
        proc = subprocess.run(
            shlex.split(BRIDGE_CMD),
            input=text, text=True, capture_output=True,
            timeout=timeout or BRIDGE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.warning("bridge timeout after %ss", timeout or BRIDGE_TIMEOUT)
        return False, {"error": "bridge_timeout"}
    except Exception as exc:  # noqa: BLE001
        log.warning("bridge failed to start: %s", exc)
        return False, {"error": "bridge_start_failed", "detail": str(exc)[:200]}

    out = (proc.stdout or "").strip().splitlines()
    if not out:
        return False, {"error": "bridge_no_output",
                       "stderr": (proc.stderr or "")[-300:]}
    try:
        result = json.loads(out[-1])
    except ValueError:
        return False, {"error": "bridge_bad_output", "raw": out[-1][:200]}

    ok = bool(result.get("ok")) and proc.returncode == 0
    return ok, result


def author_is_member(repo: str, user: str) -> bool:
    """该用户是否在允许名单内（committer/maintainer/手写用户名）。"""
    if not user:
        return False
    rules = current_rules(repo)
    try:
        return roster_for(repo).allows(repo, user, rules)
    except Exception as exc:  # noqa: BLE001
        log.warning("名单判断失败（按外部处理）: %s", exc)
        return False


def is_dry_run(headers: dict[str, str]) -> bool:
    """判断是否为测试模式请求。

    请求头 X-Dry-Run 的值需匹配 DRY_RUN_SECRET（默认 1）。
    测试模式走完整的路由与名单判断，但跳过真实的 GitHub 调用。
    """
    value = (headers.get(DRY_RUN_HEADER) or "").strip()
    return bool(value) and hmac.compare_digest(value, DRY_RUN_SECRET)


def handle(payload: dict[str, Any], headers: dict[str, str], raw: bytes) -> tuple[int, dict[str, Any]]:
    token = headers.get("x-gitcode-token") or ""
    if not token:
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]

    facts = _payload_facts(payload)

    if not check_token(token):
        record_event(**facts, outcome="rejected", reason="unauthorized", http_status=401)
        return 401, {"error": "unauthorized"}

    route = decide(payload)
    category, subtype = classify_outcome(payload, route)
    src_url = source_url_for(payload, facts.get("kind"))
    facts.update({"category": category, "subtype": subtype, "source_url": src_url})

    # 未命中任何路由：仍然记录，便于观察流量构成
    if route is None:
        log.info("ignored kind=%s repo=%s", facts["kind"], facts["repo"])
        record_event(**facts, outcome="ignored", reason="no_route", http_status=200)
        return 200, {"ok": True, "ignored": True}

    # 名单判断：命中路由后再校验触发者是否有权限
    # 规则每次从库里读，界面改完立即生效，无需重启
    user = facts.get("user") or ""
    repo_path = facts.get("repo") or ""

    # 只有声明需要名单的路由才校验。Issue 分析对所有作者开放。
    if route.get("requires_allow_list", True):
        rules = current_rules(repo_path)
        if not roster_for(repo_path).allows(repo_path, user, rules,
                                            files=facts.get("files") or None):
            log.info("denied action=%s user=%s repo=%s", route["action"], user, facts.get("repo"))
            record_event(**facts, action=route["action"], outcome="denied",
                         reason="not_in_allow_list", workflow=route["workflow"], http_status=200)
            return 200, {"ok": True, "ignored": True, "denied": "not_in_allow_list"}

    # 桥接路由：把文本交给外部命令，不走 workflow
    if route.get("bridge"):
        text = route["bridge_text"](payload)
        if is_dry_run(headers):
            log.info("dry-run bridge action=%s chars=%d", route["action"], len(text))
            record_event(**facts, action=route["action"], outcome="dry_run",
                         http_status=None, detail=f"{len(text)} chars")
            return 200, {"ok": True, "action": route["action"], "dry_run": True,
                         "bridge": True, "chars": len(text)}

        ok, result = run_bridge(text)
        outcome = "dispatched" if ok else "failed"
        record_event(**facts, action=route["action"], outcome=outcome,
                     workflow="bridge" if not ok else None,
                     http_status=200 if ok else 500,
                     detail=json.dumps(result, ensure_ascii=False)[:500])
        if ok:
            log.info("bridge ok action=%s user=%s", route["action"], user)
            return 200, {"ok": True, "action": route["action"], "bridge": True,
                         "result": result}
        log.warning("bridge failed action=%s result=%s", route["action"], result)
        return 502, {"ok": False, "action": route["action"], "bridge": True,
                     "error": result.get("error"), "detail": result.get("detail")}

    inputs = route["inputs"](payload)

    # 测试模式：只走完判断链并记录，不真实调用 GitHub
    if is_dry_run(headers):
        log.info("dry-run action=%s workflow=%s user=%s inputs=%s",
                 route["action"], route["workflow"], user, inputs)
        record_event(**facts, action=route["action"], outcome="dry_run",
                     workflow=route["workflow"], http_status=None,
                     detail=json.dumps(inputs, ensure_ascii=False))
        return 200, {"ok": True, "action": route["action"],
                     "dry_run": True, "would_dispatch": route["workflow"],
                     "inputs": inputs}

    status, run_id, run_url = dispatch(route["workflow"], inputs)

    if status == 204:
        log.info("dispatched action=%s workflow=%s user=%s run=%s",
                 route["action"], route["workflow"], user, run_id)
        record_event(**facts, action=route["action"], outcome="dispatched",
                     workflow=route["workflow"], http_status=204,
                     run_id=run_id, run_url=run_url,
                     detail=json.dumps(inputs, ensure_ascii=False))
        return 200, {"ok": True, "action": route["action"], "dispatched": True,
                     "run_id": run_id, "run_url": run_url}

    log.warning("dispatch failed action=%s status=%s", route["action"], status)
    record_event(**facts, action=route["action"], outcome="failed",
                 reason="downstream_rejected", workflow=route["workflow"], http_status=status)
    return 502, {"error": "downstream_rejected", "upstream_status": status}


# ---------------------------------------------------------------------------
# FastAPI 入口
# ---------------------------------------------------------------------------

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

api = FastAPI(title="AtomGit Gateway", docs_url=None, redoc_url=None)
init_db()


@api.get("/healthz")
async def healthz():
    configured = bool(WEBHOOK_PASSWORD and GITHUB_ACTIONS_TOKEN)
    payload = {"service": "atomgit-gateway", "configured": configured}
    return JSONResponse(payload, status_code=200 if configured else 503)


# ---------------- 简易界面：近 7 天触发记录 ----------------

# 静态资源目录（模板与 CSS/JS）
WEB_DIR = env("WEB_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"))

# 界面模板在启动时读入内存；开发时改文件后重启即可生效
_dashboard_cache: dict[str, str] = {}


def render_dashboard() -> str:
    """读取界面模板。失败时返回最小可用页面。"""
    path = os.path.join(WEB_DIR, "index.html")
    try:
        mtime = os.path.getmtime(path)
        cached = _dashboard_cache.get("html")
        cached_mtime = _dashboard_cache.get("mtime")
        if cached is not None and cached_mtime == mtime:
            return cached
        html = open(path, encoding="utf-8").read()
        _dashboard_cache.update({"html": html, "mtime": mtime})
        return html
    except FileNotFoundError:
        log.error("界面模板不存在: %s", path)
        return "<h1>AtomGit 转发网关</h1><p>界面模板缺失，请检查 web/index.html</p>"
    except Exception as exc:  # noqa: BLE001
        log.error("读取界面模板失败: %s", exc)
        return "<h1>AtomGit 转发网关</h1><p>界面加载失败</p>"


@api.get("/")
async def dashboard():
    from fastapi.responses import HTMLResponse
    return HTMLResponse(render_dashboard(), headers={"Cache-Control": "no-cache"})


@api.get("/assets/{path:path}")
async def assets(path: str):
    """提供 smartisan.css / smartisan.js / icons-sprite.svg 等静态资源。"""
    from fastapi.responses import FileResponse
    base = os.path.join(WEB_DIR, "assets")
    safe = os.path.normpath(os.path.join(base, path))
    if not safe.startswith(base):
        return JSONResponse({"error": "invalid_path"}, status_code=400)
    if not os.path.isfile(safe):
        return JSONResponse({"error": "not_found"}, status_code=404)

    # 显式指定 MIME，避免 css/js 被当成 text/plain
    ext = os.path.splitext(safe)[1].lower()
    media = {
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".woff2": "font/woff2",
    }.get(ext, "application/octet-stream")
    return FileResponse(safe, media_type=media)


@api.get("/api/events")
async def api_events(days: int = 7, limit: int = 500, repo: str | None = None,
                     show_ignored: bool = False, show_dry_run: bool = True):
    """触发记录。忽略请求默认隐藏；测试记录默认显示，可传 show_dry_run=false 隐藏。"""
    return {"days": days, "repo": repo,
            "show_ignored": show_ignored, "show_dry_run": show_dry_run,
            "events": query_events(days=days, limit=min(limit, 2000), repo=repo,
                                   include_ignored=show_ignored,
                                   include_dry_run=show_dry_run)}


@api.get("/api/stats")
async def api_stats(days: int = 7, repo: str | None = None,
                    show_ignored: bool = False, show_dry_run: bool = True):
    return event_stats(days=days, repo=repo, include_ignored=show_ignored,
                       include_dry_run=show_dry_run)


@api.put("/api/roster")
async def api_roster_update(request: Request):
    """更新允许名单。需在 X-Webhook-Token 头带 WEBHOOK_PASSWORD。"""
    # 鉴权：复用入站密码
    token = (request.headers.get("x-webhook-token") or "").strip()
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not check_token(token):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    value = (body or {}).get("allow_list")
    if not isinstance(value, str):
        return JSONResponse({"ok": False, "error": "allow_list_required"}, status_code=400)
    value = value.strip()
    if len(value) > 4000:
        return JSONResponse({"ok": False, "error": "too_long", "max": 4000}, status_code=400)

    ok, detail = validate_allow_list(value)
    if not ok:
        return JSONResponse({"ok": False, "error": "invalid_allow_list",
                             "detail": detail}, status_code=400)

    repo = (body or {}).get("repo") or None
    if repo and repo not in REPOS:
        return JSONResponse({"ok": False, "error": "unknown_repo", "repo": repo},
                            status_code=400)

    # 记录修改者：优先用请求头里的用户名，其次记 IP
    who = request.headers.get("x-editor") or (request.client.host if request.client else None)
    set_allow_list(value, who, repo)
    log.info("allow_list updated by=%s rules=%s", who, describe_rules(parse_allow_list(value)))
    return {"ok": True, "rules": describe_rules(parse_allow_list(value)),
            "detail": detail, "updated_by": who}


@api.post("/api/events/clear")
async def api_events_clear(request: Request):
    """清空记录。需 X-Webhook-Token；默认只删测试记录。

    body: {"outcomes": ["dry_run"]} 或 {"outcomes": ["all"]}
    """
    token = (request.headers.get("x-webhook-token") or "").strip()
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not check_token(token):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    outcomes = (body or {}).get("outcomes") or ["dry_run"]
    if isinstance(outcomes, str):
        outcomes = [outcomes]
    if "all" in outcomes:
        outcomes = None

    n = clear_events(outcomes, (body or {}).get("repo"))
    if n < 0:
        return JSONResponse({"ok": False, "error": "clear_failed"}, status_code=500)
    return {"ok": True, "deleted": n, "outcomes": outcomes or "all"}


@api.get("/api/config")
async def api_config():
    """前端需要的少量配置。"""
    return {"atomgit_web": ATOMGIT_WEB, "repos": list(REPOS)}


@api.get("/api/repos")
async def api_repos():
    """受管仓库列表，供界面下拉选择。"""
    return {"repos": [{"path": k, "sig": v["sig"], "branch": v["branch"]}
                      for k, v in REPOS.items()]}


@api.get("/api/roster")
async def api_roster(repo: str | None = None):
    """当前名单状态。repo 缺省时取默认仓库。"""
    target = repo or TARGET_REPOSITORY
    expr, updated_at, updated_by = get_allow_list(target)
    client = roster_for(target)
    client.refresh()          # 主动刷新一次，保证状态是最新的
    st = client.status()
    st["repo"] = target
    st["sig"] = (REPOS.get(target) or {}).get("sig")
    st["allow_list"] = expr
    st["rules"] = describe_rules(parse_allow_list(expr))
    st["updated_at"] = updated_at
    st["updated_by"] = updated_by
    return st


@api.post("/hooks/gitcode")
@api.post("/webhook/gitcode/cann/catlass")
async def receive(request: Request):
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return JSONResponse({"error": "payload_too_large", "max_bytes": MAX_BODY_BYTES},
                            status_code=413)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    headers = {k.lower(): v for k, v in request.headers.items()}
    started = time.monotonic()
    status, body = handle(payload, headers, raw)
    log.info("status=%s elapsed=%.3fs kind=%s", status, time.monotonic() - started,
             payload.get("object_kind"))
    return JSONResponse(body, status_code=status)
