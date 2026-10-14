"""Check shared workflow stage wiring without making any publishing requests."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class StageContracts(unittest.TestCase):
    def test_workflows_do_not_embed_gitcode_rest_calls(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            with self.subTest(path=path.name):
                self.assertNotIn("api.gitcode.com", path.read_text(encoding="utf-8"))

    def test_pr_metadata_stage_is_shared_by_both_entrypoints(self):
        for name in ["test-gitcode-pr.yml", "test-gitcode-pr-cann-9-2-beta-2.yml"]:
            workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
            stage = next(step for step in workflow["jobs"]["prepare"]["steps"] if step.get("id") == "pr")
            self.assertIn("/.github/actions/gitcode-pr-metadata@", stage["uses"])

    def test_issue_workflow_model_and_api_stages(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/reply-gitcode-issue.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["reply"]["steps"]
        api_steps = [s for s in steps if s.get("uses") == "./.github/actions/gitcode-issue"]
        self.assertEqual([s["with"]["operation"] for s in api_steps], ["prepare", "publish"])
        analyze = next(s for s in steps if s.get("id") == "trae")
        self.assertEqual(analyze["with"]["model"], "DeepSeek-V4.1-Flash")
        self.assertNotIn("GITCODE_TOKEN", analyze.get("env", {}))

    def test_release_workflow_uses_release_stage(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release-dsl-wheel.yml").read_text(encoding="utf-8"))
        self.assertTrue(any(s.get("uses") == "./.github/actions/gitcode-release"
                            for s in workflow["jobs"]["publish-gitcode"]["steps"]))


if __name__ == "__main__":
    unittest.main()
