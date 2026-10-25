"""社区名单：从 cann/community 仓库的 YAML 配置动态获取 SIG 角色成员。

## 数据来源（全部为公开仓库的结构化 YAML，无需认证）

  - Maintainer: CANN/org-info.yaml
                结构：sigs[] -> {sig_name, maintainers[] -> {gitcode_id, name, email}}
  - Committer:  CANN/sigs/<sig>/sig-info.yaml
                结构：repositories[] -> {repo[], committers[], entry_configs[]}

注意：GitCode/AtomGit 的 `/raw/` 直链返回的是前端 HTML 外壳，不是文件内容。
必须走 contents API（响应是 base64 编码的正文）。

## 配置语法

允许名单支持角色引用与显式用户名混用：

    @maintainer                    org-info.yaml 里该 SIG 的 maintainers
    @committer                     sig-info.yaml 里该仓库的 committers
    @committer:tools               限定子目录（entry_configs）
    alice, bob                     显式用户名（内部未获权限的人写这里）

示例：

    ALLOW = "@maintainer, @committer, internal_dev1, internal_dev2"

## 行为约定

  - 名单是权威来源，本地只做缓存，不硬编码
  - 获取失败降级到缓存；缓存也不可用时放行（fail-open），交由下游复核
  - 用户名匹配大小写敏感（与 GitCode 行为一致）
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("community_roster")

DEFAULT_API_BASE = "https://atomgit.com/api/v5/repos/cann/community/contents"
DEFAULT_REF = "master"
DEFAULT_SIG = "catlass"
DEFAULT_CACHE_TTL = 3600
DEFAULT_CACHE_FILE = "/tmp/community_roster_cache.json"
DEFAULT_TIMEOUT = 15

ROLE_MAINTAINER = "maintainer"
ROLE_COMMITTER = "committer"

# 角色引用：@role 或 @role:subpath
ROLE_RE = re.compile(r"^@([a-z_]+)(?::([A-Za-z0-9_./-]+))?$")

# org-info.yaml（SIG → maintainers）
ORG_INFO_PATH = "CANN/org-info.yaml"
# 单个 SIG 的 sig-info.yaml
SIG_INFO_PATH = "CANN/sigs/{sig}/sig-info.yaml"


class RosterError(Exception):
    """名单获取或解析失败。"""


@dataclass
class RepoRoster:
    """单个仓库的角色名单。

    角色作用域不同：
      - maintainer 是 SIG 级角色，对 SIG 名下所有仓库都有效
      - committer 是仓库级角色，只对自己仓库有效
    """

    repo: str
    roles: dict[str, set[str]] = field(default_factory=dict)
    # 子目录名单：{"tools": {"committer": {...}}}
    entry_roles: dict[str, dict[str, set[str]]] = field(default_factory=dict)

    def members(self, role: str, path: str | None = None) -> set[str]:
        """取某角色的人。

        语义（与社区配置一致）：
          - path 为 None：取主名单 roles[role]
          - path 指定：**仅**取该子目录的名单 entry_roles[path][role]，
            不含主名单。即 @committer:tools 只算 tools 目录的人。
        """
        if path:
            sub = self.entry_roles.get(path) or {}
            return set(sub.get(role) or set())
        return set(self.roles.get(role) or set())

    def has(self, user: str, role: str, path: str | None = None) -> bool:
        return user in self.members(role, path)

    def all_members(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for role, users in self.roles.items():
            out.setdefault(role, set()).update(users)
        for sub in self.entry_roles.values():
            for role, users in sub.items():
                out.setdefault(role, set()).update(users)
        return out

    def summary(self) -> dict[str, int]:
        return {r: len(u) for r, u in sorted(self.all_members().items())}


# ---------------------------------------------------------------------------
# 允许名单表达式
# ---------------------------------------------------------------------------

@dataclass
class AllowRule:
    """一条允许规则：角色引用或显式用户名。"""

    role: str | None = None
    path: str | None = None
    user: str | None = None

    def matches(
        self,
        roster: RepoRoster | None,
        user: str,
        files: list[str] | None = None,
    ) -> bool:
        """判断该规则是否匹配。

        files 为事件涉及的文件列表（预留，用于细粒度路径判断）。

        优先级：
          1. 显式用户名 —— 直接比较
          2. 角色 + 规则自带 path（@committer:tools）—— 按该子目录名单查，
             此时**忽略** files，因为名单来源已经明确指定
          3. 角色 + 无 path —— 查主名单；files 保留供未来按目录细分
        """
        if self.user is not None:
            return self.user == user
        if roster is None or self.role is None:
            return False

        if self.path:
            # 规则显式指定了子目录：以名单来源为准，忽略 files
            return roster.has(user, self.role, self.path)

        # 未指定路径：查主名单。
        # files 参数在此预留——将来可据此推断用户是否有权改动相关目录。
        return roster.has(user, self.role, None)


def parse_allow_list(expr: str | Iterable[str]) -> list[AllowRule]:
    """解析 "@maintainer, @committer, @committer:tools, alice, bob"。"""
    items: list[str] = []
    if isinstance(expr, str):
        items = re.split(r"[,\n]", expr)
    else:
        for chunk in expr:
            items.extend(re.split(r"[,\n]", str(chunk)))

    rules: list[AllowRule] = []
    for raw in items:
        token = raw.strip()
        if not token or token.startswith("#"):
            continue
        m = ROLE_RE.match(token)
        if m:
            role = m.group(1).lower()
            if role not in (ROLE_MAINTAINER, ROLE_COMMITTER):
                log.warning("未知角色 %s（已忽略）", token)
                continue
            rules.append(AllowRule(role=role, path=m.group(2)))
        elif token.startswith("@"):
            log.warning("无法识别的角色引用: %s（已忽略）", token)
        else:
            rules.append(AllowRule(user=token))
    return rules


def describe_rules(rules: list[AllowRule]) -> str:
    parts = []
    for r in rules:
        if r.user:
            parts.append(r.user)
        elif r.path:
            parts.append(f"@{r.role}:{r.path}")
        else:
            parts.append(f"@{r.role}")
    return ", ".join(parts) if parts else "(空)"


# ---------------------------------------------------------------------------
# 名单客户端
# ---------------------------------------------------------------------------

class CommunityRoster:
    """SIG 名单客户端，带缓存与降级。"""

    def __init__(
        self,
        sig: str = DEFAULT_SIG,
        api_base: str = DEFAULT_API_BASE,
        ref: str = DEFAULT_REF,
        cache_file: str = DEFAULT_CACHE_FILE,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: int = DEFAULT_TIMEOUT,
        fetch: Any = None,
    ) -> None:
        self.sig = sig
        self.api_base = api_base.rstrip("/")
        self.ref = ref
        self.cache_file = Path(cache_file)
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._fetch = fetch or self._http_get

        self._rosters: dict[str, RepoRoster] = {}
        self._fetched_at: float = 0.0
        self._last_error: str | None = None

    # ---------- 获取 ----------

    def _contents_url(self, path: str) -> str:
        return f"{self.api_base}/{path}?ref={self.ref}"

    def _http_get(self, url: str) -> Any:
        req = urllib.request.Request(url, headers={
            "User-Agent": "atomgit-forwarder/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _file_text(self, path: str) -> str:
        data = self._fetch(self._contents_url(path))
        if not isinstance(data, dict):
            raise RosterError(f"{path}: 响应不是对象")
        content = data.get("content")
        if not content:
            raise RosterError(f"{path}: 无 content 字段")
        if data.get("encoding") == "base64":
            return base64.b64decode(content).decode("utf-8", "replace")
        return content

    def refresh(self, force: bool = False) -> dict[str, RepoRoster]:
        if not force and self._is_fresh():
            return self._rosters
        try:
            rosters = self._fetch_all()
            if not rosters:
                raise RosterError("名单为空")
            self._rosters = rosters
            self._fetched_at = time.time()
            self._last_error = None
            self._save_cache(rosters)
            log.info("名单已刷新: %s", {n: r.summary() for n, r in rosters.items()})
            return rosters
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"{type(exc).__name__}: {exc}"
            log.warning("名单刷新失败 (%s)，尝试缓存", self._last_error)
            if self._load_cache():
                return self._rosters
            log.error("无可用缓存，名单为空（判断将放行）")
            return {}

    def _fetch_all(self) -> dict[str, RepoRoster]:
        """读取 org-info.yaml（maintainer）与 sig-info.yaml（committer）。"""
        rosters: dict[str, RepoRoster] = {}

        # 1) committer：sig-info.yaml
        sig_info_path = SIG_INFO_PATH.format(sig=self.sig)
        try:
            text = self._file_text(sig_info_path)
            for repo, parsed in parse_sig_info(text).items():
                r = rosters.setdefault(repo, RepoRoster(repo=repo))
                r.roles.setdefault(ROLE_COMMITTER, set()).update(
                    parsed.roles.get(ROLE_COMMITTER, set()))
                for path, subs in parsed.entry_roles.items():
                    r.entry_roles.setdefault(path, {})
                    r.entry_roles[path].setdefault(ROLE_COMMITTER, set()).update(
                        subs.get(ROLE_COMMITTER, set()))
        except Exception as exc:  # noqa: BLE001
            log.warning("读取 %s 失败: %s", sig_info_path, exc)

        # 2) maintainer：org-info.yaml
        try:
            text = self._file_text(ORG_INFO_PATH)
            maintainers = parse_org_info(text, self.sig)
            if maintainers:
                # maintainer 属于 SIG 级；挂到该 SIG 名下的所有仓库
                for repo in list(rosters.keys()):
                    rosters[repo].roles[ROLE_MAINTAINER] = set(maintainers)
                if not rosters:
                    # sig-info 失败时，至少给一个占位仓库，保证 maintainer 可用
                    for repo in _repos_from_maintainers_only(self.sig):
                        rosters.setdefault(repo, RepoRoster(repo=repo))
                        rosters[repo].roles[ROLE_MAINTAINER] = set(maintainers)
        except Exception as exc:  # noqa: BLE001
            log.warning("读取 %s 失败: %s", ORG_INFO_PATH, exc)

        return rosters

    def _is_fresh(self) -> bool:
        return bool(self._rosters) and (time.time() - self._fetched_at) < self.cache_ttl

    # ---------- 查询 ----------

    def roster(self, repo: str) -> RepoRoster | None:
        self.refresh()
        return self._rosters.get(repo)

    def allows(
        self,
        repo: str,
        user: str,
        rules: list[AllowRule] | str | None = None,
        path: str | None = None,
        files: list[str] | None = None,
    ) -> bool:
        """判断 user 是否被允许。

        参数：
          repo   仓库路径（committer 按仓库生效，maintainer 按 SIG 生效）
          user   待判断的用户名
          rules  允许规则列表，或 "@maintainer, @committer, alice" 形式的字符串；
                 为空表示不限制
          path   事件涉及的目录（单值，可选，暂未使用）
          files  事件涉及的文件列表（预留，用于细粒度路径判断；规则带 :path 时忽略）

        rules 为空 → 放行。
        名单不可用且规则含角色引用 → 放行（fail-open），交由下游复核。
        """
        if rules is None:
            return True
        if isinstance(rules, str):
            rules = parse_allow_list(rules)
        if not rules:
            return True

        r = self.roster(repo)
        needs_roster = any(rule.role for rule in rules)
        if r is None and needs_roster:
            log.warning("无 %s 的名单，角色规则无法判定（fail-open）", repo)
            return True
        return any(rule.matches(r, user, files) for rule in rules)

    def status(self) -> dict[str, Any]:
        return {
            "sig": self.sig,
            "ref": self.ref,
            "fetched_at": self._fetched_at or None,
            "age_seconds": int(time.time() - self._fetched_at) if self._fetched_at else None,
            "repos": len(self._rosters),
            "last_error": self._last_error,
            "counts": {name: r.summary() for name, r in self._rosters.items()},
        }

    # ---------- 缓存 ----------

    def _save_cache(self, rosters: dict[str, RepoRoster]) -> None:
        try:
            data = {
                "fetched_at": time.time(),
                "sig": self.sig,
                "rosters": {
                    name: {
                        "roles": {k: sorted(v) for k, v in r.roles.items()},
                        "entry_roles": {
                            p: {k: sorted(v) for k, v in subs.items()}
                            for p, subs in r.entry_roles.items()
                        },
                    }
                    for name, r in rosters.items()
                },
            }
            tmp = self.cache_file.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.cache_file)
        except Exception as exc:  # noqa: BLE001
            log.warning("写缓存失败: %s", exc)

    def _load_cache(self) -> bool:
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
            self._rosters = {
                name: RepoRoster(
                    repo=name,
                    roles={k: set(v) for k, v in (v2.get("roles") or {}).items()},
                    entry_roles={
                        p: {k: set(v) for k, v in subs.items()}
                        for p, subs in (v2.get("entry_roles") or {}).items()
                    },
                )
                for name, v2 in (data.get("rosters") or {}).items()
            }
            self._fetched_at = float(data.get("fetched_at") or 0)
            log.info("已从缓存加载名单: %d 个仓库", len(self._rosters))
            return bool(self._rosters)
        except FileNotFoundError:
            return False
        except Exception as exc:  # noqa: BLE001
            log.warning("读缓存失败: %s", exc)
            return False


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def parse_sig_info(text: str) -> dict[str, RepoRoster]:
    """解析 sig-info.yaml → {repo: RepoRoster(roles={'committer': ...})}"""
    doc = _load_yaml(text, "sig-info.yaml")
    out: dict[str, RepoRoster] = {}
    for entry in doc.get("repositories") or []:
        if not isinstance(entry, dict):
            continue
        repos = entry.get("repo") or []
        if isinstance(repos, str):
            repos = [repos]

        main = _ids(entry.get("committers"))
        entries: dict[str, set[str]] = {}
        for cfg in entry.get("entry_configs") or []:
            if not isinstance(cfg, dict):
                continue
            paths = cfg.get("path") or []
            if isinstance(paths, str):
                paths = [paths]
            sub = _ids(cfg.get("committers"))
            for p in paths:
                if isinstance(p, str) and p:
                    entries.setdefault(p, set()).update(sub)

        for repo in repos:
            if isinstance(repo, str) and repo:
                out[repo] = RepoRoster(
                    repo=repo,
                    roles={ROLE_COMMITTER: set(main)},
                    entry_roles={p: {ROLE_COMMITTER: set(u)} for p, u in entries.items()},
                )
    return out


def parse_org_info(text: str, sig: str) -> set[str]:
    """从 org-info.yaml 取指定 SIG 的 maintainer gitcode_id 集合。

    结构：
        sigs:
          - sig_name: catlass
            maintainers:
              - gitcode_id: zhouhao176
                name: 周浩
                email: ...
    """
    doc = _load_yaml(text, "org-info.yaml")
    for entry in doc.get("sigs") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("sig_name") != sig:
            continue
        return _ids(entry.get("maintainers"))
    log.warning("org-info.yaml 中未找到 SIG %s", sig)
    return set()


def _repos_from_maintainers_only(sig: str) -> list[str]:
    """sig-info.yaml 不可用时的仓库名兜底（仅用于承载 maintainer 规则）。"""
    return [f"cann/{sig}"]


def _load_yaml(text: str, label: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RosterError("需要 PyYAML") from exc
    try:
        doc = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001
        raise RosterError(f"{label} 解析失败: {exc}") from exc
    if not isinstance(doc, dict):
        raise RosterError(f"{label} 根节点不是映射")
    return doc


def _ids(node: Any) -> set[str]:
    """从 maintainers/committers 列表提取 gitcode_id。"""
    out: set[str] = set()
    if not isinstance(node, list):
        return out
    for item in node:
        if isinstance(item, str):
            out.add(item)
        elif isinstance(item, dict):
            v = item.get("gitcode_id")
            if isinstance(v, str) and v:
                out.add(v)
    return out
