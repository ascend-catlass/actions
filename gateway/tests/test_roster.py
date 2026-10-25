"""社区名单包的测试。

离线测试用固定 YAML 样本；联网测试（标记 online）会访问 AtomGit。
运行: python3 tests/test_roster.py            （仅离线）
      RUN_ONLINE=1 python3 tests/test_roster.py（含联网）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from community_roster import (  # noqa: E402
    ROLE_COMMITTER,
    ROLE_MAINTAINER,
    CommunityRoster,
    describe_rules,
    parse_allow_list,
    parse_org_info,
    parse_sig_info,
)

SIG_INFO = """
name: catlass
repositories:
- repo:
  - cann/catlass
  committers:
  - gitcode_id: zhouhao176
  - gitcode_id: yuantao_
  - gitcode_id: Lulu_scut
  entry_configs:
  - path:
    - tools
    committers:
    - gitcode_id: gong-siwei
    - gitcode_id: yan_yw
- repo:
  - cann/catccos
  committers:
  - gitcode_id: caixuyi
"""

ORG_INFO = """
name: CANN
sigs:
  - sig_name: catlass
    maintainers:
    - gitcode_id: zhouhao176
      name: 周浩
    - gitcode_id: Lulu_scut
      name: 陆璐
  - sig_name: other
    maintainers:
    - gitcode_id: someone
"""


def make_roster():
    """构造离线 roster：数据全部来自固定样本。"""
    r = CommunityRoster(cache_file="/tmp/test_roster_offline.json")

    def fake_fetch(url):
        if "sig-info.yaml" in url:
            return {"encoding": "base64", "content": _b64(SIG_INFO)}
        if "org-info.yaml" in url:
            return {"encoding": "base64", "content": _b64(ORG_INFO)}
        raise KeyError(url)

    r._fetch = fake_fetch
    r.refresh(force=True)
    return r


def _b64(s):
    import base64
    return base64.b64encode(s.encode()).decode()


def test_parse_sig_info():
    rosters = parse_sig_info(SIG_INFO)
    assert set(rosters) == {"cann/catlass", "cann/catccos"}
    catlass = rosters["cann/catlass"]
    assert catlass.roles[ROLE_COMMITTER] == {"zhouhao176", "yuantao_", "Lulu_scut"}
    assert catlass.entry_roles["tools"][ROLE_COMMITTER] == {"gong-siwei", "yan_yw"}
    assert rosters["cann/catccos"].roles[ROLE_COMMITTER] == {"caixuyi"}


def test_parse_org_info():
    assert parse_org_info(ORG_INFO, "catlass") == {"zhouhao176", "Lulu_scut"}
    assert parse_org_info(ORG_INFO, "nonexistent") == set()


def test_parse_allow_list():
    rules = parse_allow_list("@maintainer, @committer, @committer:tools, alice, bob")
    kinds = [(r.role, r.path, r.user) for r in rules]
    assert ("maintainer", None, None) in kinds
    assert ("committer", None, None) in kinds
    assert ("committer", "tools", None) in kinds
    assert (None, None, "alice") in kinds
    assert (None, None, "bob") in kinds
    assert "@committer" in describe_rules(rules)
    assert "alice" in describe_rules(rules)


def test_parse_allow_list_ignores_unknown_role():
    rules = parse_allow_list("@nonexistent, alice")
    assert [r.user for r in rules if r.user] == ["alice"]
    assert all(r.role != "nonexistent" for r in rules)


def test_maintainer_role():
    r = make_roster()
    assert r.allows("cann/catlass", "zhouhao176", "@maintainer") is True
    assert r.allows("cann/catlass", "yuantao_", "@maintainer") is False


def test_maintainer_is_sig_wide():
    """maintainer 是 SIG 级，对所有归属仓库生效。"""
    r = make_roster()
    assert r.allows("cann/catccos", "zhouhao176", "@maintainer") is True
    assert r.allows("cann/catccos", "Lulu_scut", "@maintainer") is True


def test_committer_is_repo_scoped():
    """committer 只对自己仓库生效。"""
    r = make_roster()
    assert r.allows("cann/catlass", "yuantao_", "@committer") is True
    assert r.allows("cann/catccos", "yuantao_", "@committer") is False
    assert r.allows("cann/catccos", "caixuyi", "@committer") is True


def test_path_scoped_committer_is_strict():
    """@committer:tools 严格只算子目录，不含主名单。"""
    r = make_roster()
    assert r.allows("cann/catlass", "gong-siwei", "@committer:tools") is True
    assert r.allows("cann/catlass", "yan_yw", "@committer:tools") is True
    assert r.allows("cann/catlass", "yuantao_", "@committer:tools") is False
    assert r.allows("cann/catlass", "zhouhao176", "@committer:tools") is False


def test_combined_rules():
    r = make_roster()
    expr = "@committer, @committer:tools"
    assert r.allows("cann/catlass", "yuantao_", expr) is True
    assert r.allows("cann/catlass", "gong-siwei", expr) is True
    assert r.allows("cann/catlass", "stranger", expr) is False


def test_explicit_users_mixed_with_roles():
    r = make_roster()
    expr = "@maintainer, @committer, internal_a, internal_b"
    assert r.allows("cann/catlass", "internal_a", expr) is True
    assert r.allows("cann/catlass", "internal_b", expr) is True
    assert r.allows("cann/catlass", "internal_c", expr) is False
    assert r.allows("cann/catlass", "yuantao_", expr) is True


def test_explicit_only():
    r = make_roster()
    assert r.allows("cann/catlass", "internal_a", "internal_a") is True
    assert r.allows("cann/catlass", "yuantao_", "internal_a") is False


def test_case_sensitive():
    r = make_roster()
    assert r.allows("cann/catlass", "YuanTao_", "@committer") is False
    assert r.allows("cann/catlass", "yuantao_", "@committer") is True


def test_empty_rules_allow_all():
    r = make_roster()
    assert r.allows("cann/catlass", "anyone", "") is True
    assert r.allows("cann/catlass", "anyone", None) is True
    assert r.allows("cann/catlass", "anyone", []) is True


def test_cache_roundtrip():
    r = make_roster()
    cached = r.cache_file
    assert cached.exists()

    r2 = CommunityRoster(cache_file=str(cached))
    r2._fetch = lambda url: (_ for _ in ()).throw(RuntimeError("network down"))
    r2.refresh(force=True)          # 拉取失败 → 降级到缓存
    assert r2.allows("cann/catlass", "yuantao_", "@committer") is True
    assert r2.allows("cann/catlass", "gong-siwei", "@committer:tools") is True


def test_fail_open_without_any_data():
    """无网络且无缓存时放行，避免误拦（交由下游复核）。"""
    r = CommunityRoster(cache_file="/tmp/does-not-exist-roster.json")
    r._fetch = lambda url: (_ for _ in ()).throw(RuntimeError("network down"))
    r.refresh(force=True)
    assert r.allows("cann/catlass", "anyone", "@committer") is True
    assert r.status()["last_error"] is not None


def test_online_real_data():
    """联网获取真实名单（默认跳过）。"""
    if not os.environ.get("RUN_ONLINE"):
        return
    r = CommunityRoster(cache_file="/tmp/test_roster_online.json")
    r.refresh(force=True)
    status = r.status()
    assert status["last_error"] is None, status["last_error"]
    assert status["repos"] >= 1
    # catlass 应能解析出 committer 与 maintainer
    roster = r.roster("cann/catlass")
    assert roster is not None
    assert len(roster.roles.get(ROLE_COMMITTER, set())) > 5
    assert len(roster.roles.get(ROLE_MAINTAINER, set())) > 1


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
