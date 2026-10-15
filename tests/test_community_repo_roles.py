"""Exercise role lookup, inheritance boundaries and Actions output contracts."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts.community_repo_roles import lookup_roles, main, normalize_repository


class CommunityRolesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("CANN/org-info.yaml", {"sigs": [
            {"sig_name": "example", "maintainers": [
                {"atomgit_id": "Owner", "name": "维护者", "email": "owner@example.com"}]}]})
        self.write("CANN/sigs/example/sig-info.yaml", {
            "name": "example", "committers": [{"atomgit_id": "sig_person"}],
            "repositories": [
                {"repo": ["cann/one", "cann/two"], "committers": [
                    {"atomgit_id": "repo_person"}, {"atomgit_id": "sig_person", "name": "审批者"}],
                 "entry_configs": [{"path": ["tools"], "committers": [{"atomgit_id": "local"}]}],
                 "branch_configs": [{"branch": ["master"], "committers": [{"atomgit_id": "branch"}],
                                     "branch_keeper": [{"atomgit_id": "keeper"}]}]},
                {"repo": ["cann/other"], "committers": [{"atomgit_id": "other"}]}]})
        self.write("CANN/sigs/shared_config.yaml", {
            "entry_configs": [{"path": [".gitcode"], "committers": [{"atomgit_id": "shared"}]}]})

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")

    def test_group_membership_deduplication_and_scoped_boundaries(self):
        result = lookup_roles(self.root, "https://atomgit.com/CANN/two.git/")
        self.assertEqual(result["repository"], "cann/two")
        self.assertEqual(result["maintainer_ids"], ["Owner"])
        self.assertEqual(result["committer_ids"], ["sig_person", "repo_person"])
        self.assertEqual(result["committers"][0]["name"], "审批者")
        self.assertEqual(result["scoped_configs"][0]["entry_configs"][0]["path"], ["tools"])
        self.assertEqual(result["shared_config"]["entry_configs"][0]["path"], [".gitcode"])

    def test_multiple_sigs_and_case_insensitive_person_deduplication(self):
        org = yaml.safe_load((self.root / "CANN/org-info.yaml").read_text(encoding="utf-8"))
        org["sigs"].append({"sig_name": "second", "maintainers": [{"atomgit_id": "owner"}]})
        self.write("CANN/org-info.yaml", org)
        self.write("CANN/sigs/second/sig-info.yaml", {"name": "second", "repositories": [
            {"repo": ["cann/two"], "committers": [{"atomgit_id": "second"}]}]})
        result = lookup_roles(self.root, "CANN/TWO")
        self.assertEqual(result["sigs"], ["example", "second"])
        self.assertEqual(result["maintainer_ids"], ["Owner"])
        self.assertEqual(result["committer_ids"], ["sig_person", "repo_person", "second"])

    def test_missing_repo_fails(self):
        with self.assertRaisesRegex(ValueError, "not declared"):
            lookup_roles(self.root, "cann/missing")

    def test_invalid_repo_inputs(self):
        for value in ["one", "../one", "cann/../one", "https://example.com/cann/one",
                      "https://atomgit.com/cann/one/issues/1", "https://atomgit.com/cann/one?q=1",
                      "https://user@atomgit.com/cann/one", "cann/one\nattack"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_repository(value)
        self.assertEqual(normalize_repository("https://atomgit.com/cann/one.git"), "cann/one")
        self.assertEqual(normalize_repository("cann/.atomgit"), "cann/.atomgit")

    def test_legacy_upstream_identity_field_is_read_as_atomgit_identity(self):
        self.write("CANN/org-info.yaml", {"sigs": [{"sig_name": "example", "maintainers": [{"gitcode_id": "Owner"}]}]})
        result = lookup_roles(self.root, "cann/one")
        self.assertEqual(result["maintainer_ids"], ["Owner"])
        self.assertEqual(result["maintainers"], [{"atomgit_id": "Owner"}])

    def test_empty_role_lists_are_valid(self):
        self.write("CANN/org-info.yaml", {"sigs": [{"sig_name": "example", "maintainers": []}]})
        self.write("CANN/sigs/example/sig-info.yaml", {"name": "example", "committers": None,
                   "repositories": [{"repo": ["cann/one"]}]})
        result = lookup_roles(self.root, "cann/one")
        self.assertEqual(result["maintainer_ids"], [])
        self.assertEqual(result["committer_ids"], [])

    def test_unknown_sig_fails(self):
        self.write("CANN/org-info.yaml", {"sigs": []})
        with self.assertRaisesRegex(ValueError, "exactly one entry"):
            lookup_roles(self.root, "cann/one")

    def test_malformed_yaml_fails(self):
        (self.root / "CANN/org-info.yaml").write_text("sigs: [", encoding="utf-8")
        with self.assertRaises(yaml.YAMLError):
            lookup_roles(self.root, "cann/one")

    def test_cli_outputs_json_and_handles_failures(self):
        output = self.root / "out/result.json"
        actions_output = self.root / "github-output"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(actions_output)}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--community-path", str(self.root), "--repository", "cann/one",
                                   "--output-file", str(output)]), 0)
        result = json.loads(output.read_text(encoding="utf-8"))
        lines = dict(line.split("=", 1) for line in actions_output.read_text(encoding="utf-8").splitlines())
        self.assertEqual(json.loads(lines["result"]), result)
        self.assertEqual(json.loads(lines["maintainers"]), ["Owner"])
        self.assertEqual(lines["result-file"], str(output.resolve()))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--community-path", str(self.root), "--repository", "cann/missing",
                                   "--output-file", str(self.root / "missing.json")]), 1)
        self.assertFalse((self.root / "missing.json").exists())


if __name__ == "__main__":
    unittest.main()
