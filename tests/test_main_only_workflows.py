"""Prevent worker execution and service writes outside the main branch."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class MainOnlyWorkflowTests(unittest.TestCase):
    def test_every_job_requires_main_including_cleanup_and_reusable_jobs(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
            for name, job in workflow["jobs"].items():
                with self.subTest(workflow=path.name, job=name):
                    condition = job["if"]
                    self.assertTrue(condition.startswith("${{ github.ref == 'refs/heads/main'"))
                    self.assertNotIn("||", condition.split("&&", 1)[0])

    def test_issue_has_no_automatic_test_branch_trigger(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/reply-gitcode-issue.yml").read_text(encoding="utf-8"))
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(set(triggers), {"workflow_dispatch"})


if __name__ == "__main__":
    unittest.main()
