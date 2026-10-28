"""Tests for scripts/atomgit_rdv_reset.py (no network)."""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "atomgit_rdv_reset", ROOT / "scripts" / "atomgit_rdv_reset.py")


class FakeAPI:
    def __init__(self, state="opened", labels=()):
        self.state = state
        self.labels = list(labels)
        self.calls = []

    def request(self, method, path, body=None, encoding="form"):
        self.calls.append((method, path))
        if method == "GET":
            return {"state": self.state,
                    "labels": [{"title": name} for name in self.labels]}
        if method == "DELETE":
            name = path.rsplit("/", 1)[-1]
            if name in self.labels:
                self.labels.remove(name)
            return {}
        raise AssertionError(f"unexpected {method}")


def load():
    """Import the script with a stubbed transport."""
    module = importlib.util.module_from_spec(SPEC)
    fake = mock.MagicMock()
    fake.AtomGitAPI = FakeAPI
    fake.resolve_token = lambda: "token"
    with mock.patch.dict("sys.modules", {"atomgit_api": fake}):
        SPEC.loader.exec_module(module)
    return module


class RdvResetTests(unittest.TestCase):
    def test_removes_every_rdv_label_and_verifies(self):
        api = FakeAPI(labels=["RDV-SUCC", "RDV-FAIL", "RDV-RUNNING", "cann-cla/yes"])
        self.assertEqual(
            load().remove(api, "100"),
            "removed:RDV-SUCC,RDV-FAIL,RDV-RUNNING")
        # 每个标签一次 DELETE，最后 GET 复查
        deletes = [c for c in api.calls if c[0] == "DELETE"]
        self.assertEqual(len(deletes), 3)
        self.assertEqual(api.calls[-1][0], "GET")
        self.assertEqual(api.labels, ["cann-cla/yes"])

    def test_no_rdv_label_is_a_noop(self):
        api = FakeAPI(labels=["cann-cla/yes", "approved"])
        self.assertEqual(load().remove(api, "100"), "no_rdv_label")
        self.assertFalse([c for c in api.calls if c[0] == "DELETE"])

    def test_closed_pr_is_skipped(self):
        api = FakeAPI(state="closed", labels=["RDV-FAIL"])
        self.assertEqual(load().remove(api, "100"), "pr_not_open")
        self.assertFalse([c for c in api.calls if c[0] == "DELETE"])

    def test_delete_that_did_not_take_effect_raises(self):
        """DELETE 返回成功但标签还在，必须报错而不是当作成功。"""
        class Stubborn(FakeAPI):
            def request(self, method, path, body=None, encoding="form"):
                self.calls.append((method, path))
                if method == "GET":
                    return {"state": "opened",
                            "labels": [{"title": "RDV-SUCC"}]}
                return {}
        with self.assertRaises(RuntimeError):
            load().remove(Stubborn(), "100")

    def test_rejects_bad_pr_number(self):
        api = FakeAPI()
        for bad in ("", "0", "-1", "abc", "1\n2", "１０"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                load().remove(api, bad)

    def test_rejects_invalid_pr_response(self):
        class Broken(FakeAPI):
            def request(self, method, path, body=None, encoding="form"):
                return {"state": "opened"}          # 没有 labels
        with self.assertRaises(ValueError):
            load().remove(Broken(), "100")


if __name__ == "__main__":
    unittest.main()
