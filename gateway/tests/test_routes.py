"""路由判断与名单机制测试。

覆盖：
  - 每条路由的命中与拦截条件
  - 名单机制（@maintainer / @committer / 显式用户名）
  - 鉴权与转发失败处理

名单数据用固定样本注入，不联网。

运行: python3 tests/test_routes.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("WEBHOOK_PASSWORD", "test-password")
os.environ.setdefault("GITHUB_ACTIONS_TOKEN", "test-token")

import gateway  # noqa: E402
from community_roster import CommunityRoster, parse_allow_list  # noqa: E402

PASSWORD = os.environ["WEBHOOK_PASSWORD"]

# ---------- 注入离线名单，避免测试联网 ----------
_SIG_INFO = """
name: catlass
repositories:
- repo:
  - cann/catlass
  committers:
  - gitcode_id: yuantao_
  - gitcode_id: zhouhao176
  entry_configs:
  - path:
    - tools
    committers:
    - gitcode_id: gong-siwei
"""
_ORG_INFO = """
name: CANN
sigs:
  - sig_name: catlass
    maintainers:
    - gitcode_id: zhouhao176
"""


def _b64(s):
    import base64
    return base64.b64encode(s.encode()).decode()


def _install_fake_roster(allow_list="@maintainer, @committer"):
    r = CommunityRoster(cache_file="/tmp/test_routes_roster.json")

    def fake_fetch(url):
        if "sig-info.yaml" in url:
            return {"encoding": "base64", "content": _b64(_SIG_INFO)}
        if "org-info.yaml" in url:
            return {"encoding": "base64", "content": _b64(_ORG_INFO)}
        raise KeyError(url)

    r._fetch = fake_fetch
    r.refresh(force=True)
    gateway.roster = r
    gateway.ALLOW_RULES = parse_allow_list(allow_list)
    gateway.ALLOW_LIST = allow_list


_install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)

# 记录转发调用，避免真实请求。
sent = []
gateway.dispatch = lambda workflow, inputs: (sent.append((workflow, inputs)), 204, "1", "https://example/run/1")[1:]


def call(payload, token=PASSWORD):
    return gateway.handle(payload, {"x-gitcode-token": token}, b"")


def note_payload(**over):
    p = {
        "object_kind": "note",
        "user": {"username": "yuantao_"},
        "project": {"path_with_namespace": "cann/catlass"},
        "object_attributes": {"id": 1, "note": "rdvcompile",
                              "noteable_type": "MergeRequest", "system": False},
        "merge_request": {"iid": 123, "target_branch": "master", "state": "opened"},
    }
    p.update(over)
    return p


def pr_payload(**over):
    p = {
        "object_kind": "merge_request",
        "user": {"username": "yuantao_"},
        "project": {"path_with_namespace": "cann/catlass"},
        "object_attributes": {"iid": 55, "state": "opened", "action": "update"},
        "changes": {"labels": {"previous": [], "current": [{"title": "ci-pipeline-passed"}]}},
    }
    p.update(over)
    return p


def issue_payload(**over):
    p = {
        "object_kind": "issue",
        "user": {"username": "yuantao_"},
        "project": {"path_with_namespace": "cann/catlass"},
        "object_attributes": {"iid": 740, "action": "open",
                              "state": "opened", "confidential": False},
    }
    p.update(over)
    return p


def test_auth():
    assert call(note_payload(), token="")[0] == 401
    assert call(note_payload(), token="wrong")[0] == 401
    assert call(note_payload())[0] == 200


def test_rdv_compile_dispatches():
    status, body = call(note_payload())
    assert status == 200
    assert body["action"] == "rdv_compile" and body["dispatched"] is True
    assert body["run_url"] == "https://example/run/1"
    assert sent[-1] == ("test-atomgit-pr.yml", {"pr_number": "123"})


def test_rdv_compile_ignores():
    cases = [
        (lambda p: p.update(object_kind="issue"), "非 note"),
        (lambda p: p["project"].update(path_with_namespace="other/repo"), "错仓库"),
        (lambda p: p["object_attributes"].update(note="compile"), "compile 不触发"),
        (lambda p: p["object_attributes"].update(note="rdvcompile2"), "近似文本不触发"),
        (lambda p: p["object_attributes"].update(system=True), "系统评论"),
        (lambda p: p["object_attributes"].update(noteable_type="Issue"), "非 PR 评论"),
        (lambda p: p["merge_request"].update(target_branch="dev"), "非 master"),
        (lambda p: p["merge_request"].update(state="closed"), "PR 已关"),
        (lambda p: p["merge_request"].update(iid=0), "iid 非法"),
    ]
    for mutate, label in cases:
        p = note_payload()
        mutate(p)
        assert call(p)[1].get("ignored") is True, label


def test_rdv_compile_whitespace():
    for text in ["  rdvcompile\n", "rdvcompile  ", "\trdvcompile\t"]:
        p = note_payload()
        p["object_attributes"]["note"] = text
        assert call(p)[1].get("dispatched") is True, repr(text)


def test_allow_list_committer():
    """在册 committer 可通过。"""
    for name in ["yuantao_", "zhouhao176"]:
        p = note_payload()
        p["user"] = {"username": name}
        assert call(p)[1].get("dispatched") is True, name


def test_allow_list_rejects_stranger():
    """不在名单的人被拦下（网关层拦截，不消耗 Actions）。"""
    p = note_payload()
    p["user"] = {"username": "someone_else"}
    status, body = call(p)
    assert status == 200
    assert body.get("denied") == "not_in_allow_list"


def test_allow_list_is_case_sensitive():
    p = note_payload()
    p["user"] = {"username": "YuanTao_"}
    assert call(p)[1].get("denied") == "not_in_allow_list"


def test_allow_list_missing_user_denied():
    """payload 缺 user 字段时按拒绝处理。"""
    p = note_payload()
    p.pop("user", None)
    assert call(p)[1].get("denied") == "not_in_allow_list"


def test_maintainer_only_mode():
    """只允许 maintainer 时，纯 committer 被拦。"""
    _install_fake_roster("@maintainer")
    try:
        p = note_payload()
        p["user"] = {"username": "yuantao_"}       # 只是 committer
        assert call(p)[1].get("denied") == "not_in_allow_list"

        p2 = note_payload()
        p2["user"] = {"username": "zhouhao176"}    # maintainer
        assert call(p2)[1].get("dispatched") is True
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_explicit_user_mode():
    """显式用户名可与角色混用。"""
    _install_fake_roster("@maintainer, internal_dev")
    try:
        p = note_payload()
        p["user"] = {"username": "internal_dev"}
        assert call(p)[1].get("dispatched") is True

        p2 = note_payload()
        p2["user"] = {"username": "yuantao_"}      # committer 但未显式列出
        assert call(p2)[1].get("denied") == "not_in_allow_list"
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_path_scoped_mode_uses_roster_source():
    """@committer:tools 的语义是「名单来源」：允许 tools 子目录的 committer。

    规则自带 :path 时忽略事件的 files 参数，直接查该子目录名单。
    """
    _install_fake_roster("@committer:tools")
    try:
        # tools 子目录的 committer → 放行
        p = note_payload()
        p["user"] = {"username": "gong-siwei"}
        assert call(p)[1].get("dispatched") is True

        # 主名单的人不在 tools 子名单里 → 拦截
        p2 = note_payload()
        p2["user"] = {"username": "yuantao_"}
        assert call(p2)[1].get("denied") == "not_in_allow_list"
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_files_param_ignored_when_rule_has_path():
    """规则带 :path 时，files 参数不影响判定结果。"""
    _install_fake_roster("@committer:tools")
    try:
        for files in (None, [], ["tools/foo.cpp"], ["docs/readme.md"]):
            p = note_payload()
            p["user"] = {"username": "gong-siwei"}
            if files is not None:
                p["changes"] = {"files": [{"path": f} for f in files]}
            assert call(p)[1].get("dispatched") is True, f"files={files}"
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_files_param_accepted_when_no_path():
    """规则不带 :path 时，files 参数被接受（当前不影响主名单判定，为将来预留）。"""
    _install_fake_roster("@committer")
    try:
        p = note_payload()
        p["user"] = {"username": "yuantao_"}
        p["changes"] = {"files": [{"path": "tools/x.cpp"}]}
        assert call(p)[1].get("dispatched") is True
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_empty_allow_list_allows_all():
    """名单为空 = 不限制。"""
    _install_fake_roster("")
    try:
        p = note_payload()
        p["user"] = {"username": "anyone_at_all"}
        assert call(p)[1].get("dispatched") is True
    finally:
        _install_fake_roster()


def test_multi_repo_registry():
    """仓库表解析：路径、SIG、分支。"""
    repos = gateway.parse_repos("cann/catlass:catlass,cann/ops-nn:ops-nn:develop", "master")
    assert set(repos) == {"cann/catlass", "cann/ops-nn"}
    assert repos["cann/catlass"]["sig"] == "catlass"
    assert repos["cann/catlass"]["branch"] == "master"
    assert repos["cann/ops-nn"]["sig"] == "ops-nn"
    assert repos["cann/ops-nn"]["branch"] == "develop"


def test_multi_repo_falls_back():
    """仓库表为空或格式非法时回落，保证服务可用。"""
    repos = gateway.parse_repos("", "master")
    assert "cann/catlass" in repos
    repos2 = gateway.parse_repos("invalid-without-slash", "master")
    assert "cann/catlass" in repos2


def test_unmanaged_repo_ignored():
    """不在受管表内的仓库不触发任何路由。"""
    gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}
    try:
        p = note_payload()
        p["project"] = {"path_with_namespace": "other/repo"}
        assert call(p)[1].get("ignored") is True
    finally:
        gateway.REPOS = {"cann/catlass": {"sig": "catlass", "branch": "master"}}


def test_clear_only_dry_run():
    """清空只删测试记录，真实转发与拦截保留。"""
    for outcome in ("dry_run", "dispatched", "denied"):
        gateway.record_event(kind="note", outcome=outcome, repo="cann/catlass")
    deleted = gateway.clear_events(["dry_run"], repo="cann/catlass")
    assert deleted >= 1
    left = {e["outcome"] for e in
            gateway.query_events(days=1, limit=2000, repo="cann/catlass")}
    assert "dry_run" not in left
    assert "dispatched" in left
    assert "denied" in left


def test_clear_all():
    """outcomes=None 时清空全部。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    gateway.clear_events(None, repo="cann/catlass")
    assert gateway.query_events(days=1, limit=2000, repo="cann/catlass") == []


def test_clear_scoped_to_repo():
    """限定仓库时只删该仓库的记录，别的仓库不受影响。"""
    def dry(repo):
        return len([e for e in gateway.query_events(days=1, limit=2000, repo=repo)
                    if e["outcome"] == "dry_run"])

    gateway.record_event(kind="note", outcome="dry_run", repo="scope/a")
    gateway.record_event(kind="note", outcome="dry_run", repo="scope/b")
    before_a, before_b = dry("scope/a"), dry("scope/b")
    assert before_a >= 1 and before_b >= 1

    gateway.clear_events(["dry_run"], repo="scope/a")
    assert dry("scope/a") == 0, "目标仓库应被清空"
    assert dry("scope/b") == before_b, "别的仓库不应受影响"


def test_events_carry_user_profile_url():
    """记录里带上触发者主页链接，便于界面跳转。"""
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass",
                         user="zhouhao176",
                         user_url=gateway.profile_url_for("zhouhao176"))
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass")
    hit = [e for e in rows if e.get("user") == "zhouhao176"]
    assert hit, "应找到刚写入的记录"
    assert hit[0]["user_url"] == f"{gateway.ATOMGIT_WEB}/zhouhao176"


def test_profile_url_handles_missing_user():
    assert gateway.profile_url_for(None) is None
    assert gateway.profile_url_for("") is None


def test_hide_dry_run_excludes_tests():
    """屏蔽测试记录：dry_run 不返回，其他照常。"""
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    shown = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                 include_dry_run=True)
    hidden = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                  include_dry_run=False)
    assert any(e["outcome"] == "dry_run" for e in shown)
    assert all(e["outcome"] != "dry_run" for e in hidden)
    # 用计数比较，避免受 limit 截断影响
    assert len(hidden) == len([e for e in shown if e["outcome"] != "dry_run"])


def test_hide_ignored_and_dry_run_together():
    """两个开关可叠加：同时隐藏忽略与测试。"""
    gateway.record_event(kind="push", outcome="ignored", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dry_run", repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    rows = gateway.query_events(days=1, limit=2000, repo="cann/catlass",
                                include_ignored=False, include_dry_run=False)
    outcomes = {e["outcome"] for e in rows}
    assert "ignored" not in outcomes, outcomes
    assert "dry_run" not in outcomes, outcomes
    assert "dispatched" in outcomes, "至少应保留一条真实触发"


def test_show_ignored_default_hidden():
    """默认查询不返回忽略请求。"""
    gateway.record_event(kind="push", outcome="ignored", reason="no_route",
                         repo="cann/catlass")
    gateway.record_event(kind="note", outcome="dispatched", repo="cann/catlass")
    hidden = gateway.query_events(days=1, repo="cann/catlass", include_ignored=False)
    shown = gateway.query_events(days=1, repo="cann/catlass", include_ignored=True)
    assert all(e["outcome"] != "ignored" for e in hidden)
    assert any(e["outcome"] == "ignored" for e in shown)
    assert len(shown) >= len(hidden)


def test_ci_passed_dispatches():
    status, body = call(pr_payload())
    assert status == 200
    assert body["action"] == "ci_passed" and body["dispatched"] is True
    assert sent[-1] == ("reply-atomgit-ci-passed.yml", {"pr_number": "55"})


def test_ci_passed_ignores():
    cases = [
        (lambda p: p["project"].update(path_with_namespace="other/repo"), "错仓库"),
        (lambda p: p["object_attributes"].update(state="closed"), "PR 已关"),
        (lambda p: p["changes"]["labels"].update(
            previous=[{"title": "ci-pipeline-passed"}]), "标签未新增"),
        (lambda p: p["changes"]["labels"].update(current=[]), "标签被移除"),
    ]
    for mutate, label in cases:
        p = pr_payload()
        mutate(p)
        assert call(p)[1].get("ignored") is True, label


def test_ci_passed_other_labels():
    for labels in [[], [{"title": "other"}], [{"name": "different"}]]:
        p = pr_payload()
        p["changes"]["labels"]["current"] = labels
        assert call(p)[1].get("ignored") is True, str(labels)


def test_issue_url_matches_downstream_parser():
    """传给 workflow 的 issue_url 必须能被下游 parse_url 接受。

    下游 scripts/atomgit_issue_reply.py 的正则是：
        https://atomgit\.com/<owner>/<repo>/issues/<number>
    域名一旦用错，workflow 在「Resolve Issue repository」步骤就失败。
    """
    import re
    status, body = call(issue_payload())
    assert status == 200
    url = sent[-1][1]["issue_url"]
    pattern = r"https://atomgit\.com/([\w.-]+)/([\w.-]+)/issues/([1-9][0-9]*)/?"
    assert re.fullmatch(pattern, url), f"下游无法解析: {url}"


def test_source_url_uses_same_domain():
    """来源链接与传给 workflow 的 URL 用同一个域名。"""
    p = issue_payload()
    assert gateway.source_url_for(p, "issue").startswith(gateway.ATOMGIT_WEB)


def test_issue_open_to_non_members():
    """Issue 分析面向所有作者，外部用户也能触发。"""
    p = issue_payload()
    p["user"] = {"username": "not_a_member_at_all"}
    status, body = call(p)
    assert status == 200
    assert body["action"] == "issue_analysis"
    assert sent[-1][0] == "reply-atomgit-issue.yml"


def test_pr_still_requires_allow_list():
    """PR 评论仍受名单约束，与 Issue 不同。"""
    p = note_payload()
    p["user"] = {"username": "not_a_member_at_all"}
    assert call(p)[1].get("denied") == "not_in_allow_list"


def test_issue_dispatches():
    status, body = call(issue_payload())
    assert status == 200
    assert body["action"] == "issue_analysis"
    assert sent[-1][0] == "reply-atomgit-issue.yml"
    assert sent[-1][1]["issue_url"] == f"{gateway.ATOMGIT_WEB}/cann/catlass/issues/740"
    assert sent[-1][1]["publish"] == "true"


def test_issue_ignores():
    cases = [
        (lambda p: p["object_attributes"].update(action="close"), "close 不触发"),
        (lambda p: p["object_attributes"].update(confidential=True), "机密 issue"),
        (lambda p: p["object_attributes"].update(state="closed"), "issue 已关"),
        (lambda p: p["object_attributes"].update(iid=0), "iid 非法"),
        (lambda p: p["project"].update(path_with_namespace="x/y"), "错仓库"),
    ]
    for mutate, label in cases:
        p = issue_payload()
        mutate(p)
        assert call(p)[1].get("ignored") is True, label


def test_issue_reopen():
    p = issue_payload()
    p["object_attributes"]["action"] = "reopen"
    assert call(p)[1].get("dispatched") is True


def test_unknown_kind_ignored():
    for kind in ["push", "tag_push", "wiki", "", None]:
        assert call({"object_kind": kind})[1].get("ignored") is True, str(kind)


def test_dry_run_skips_real_dispatch():
    """X-Dry-Run 头触发测试模式：走完判断但不调用 GitHub。"""
    before = len(sent)
    p = note_payload()
    status, body = gateway.handle(
        p, {"x-gitcode-token": PASSWORD, "x-dry-run": "1"}, b"")
    assert status == 200
    assert body.get("dry_run") is True
    assert body.get("would_dispatch") == "test-atomgit-pr.yml"
    assert body.get("inputs") == {"pr_number": "123"}
    assert len(sent) == before, "测试模式不应产生真实转发"


def test_dry_run_respects_allow_list():
    """测试模式下名单判断仍然生效。"""
    p = note_payload()
    p["user"] = {"username": "someone_not_allowed"}
    status, body = gateway.handle(
        p, {"x-gitcode-token": PASSWORD, "x-dry-run": "1"}, b"")
    assert body.get("denied") == "not_in_allow_list"


def test_dry_run_wrong_value_is_normal():
    """X-Dry-Run 值不匹配时按正常请求处理（会真实转发）。"""
    before = len(sent)
    p = note_payload()
    status, body = gateway.handle(
        p, {"x-gitcode-token": PASSWORD, "x-dry-run": "wrong-value"}, b"")
    assert body.get("dispatched") is True
    assert len(sent) == before + 1


def test_dry_run_absent_is_normal():
    before = len(sent)
    p = note_payload()
    status, body = gateway.handle(p, {"x-gitcode-token": PASSWORD}, b"")
    assert body.get("dispatched") is True
    assert len(sent) == before + 1


def test_dispatch_failure_returns_502():
    gateway.dispatch = lambda w, i: (403, None, None)
    try:
        status, body = call(note_payload())
        assert status == 502
        assert body["upstream_status"] == 403
    finally:
        gateway.dispatch = lambda workflow, inputs: (sent.append((workflow, inputs)), 204, "1", "https://example/run/1")[1:]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"  ✓ {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  ✗ {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n通过 {passed}   失败 {failed}")
    sys.exit(1 if failed else 0)
