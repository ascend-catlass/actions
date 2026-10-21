"""Check shared workflow stage wiring without making any publishing requests."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class StageContracts(unittest.TestCase):
    def test_workflows_do_not_embed_atomgit_rest_calls(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            with self.subTest(path=path.name):
                self.assertNotIn("api.atomgit.com", path.read_text(encoding="utf-8"))

    def test_pr_workflow_uses_metadata_stage(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/test-atomgit-pr.yml").read_text(encoding="utf-8"))
        stage = next(step for step in workflow["jobs"]["prepare"]["steps"] if step.get("id") == "pr")
        self.assertIn("yuantao313/actions/atomgit-pr-metadata@", stage["uses"])

    def test_issue_workflow_model_and_api_stages(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/reply-atomgit-issue.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["reply"]["steps"]
        api_steps = [s for s in steps if s.get("uses") == "./.github/actions/atomgit-issue"]
        self.assertEqual([s["with"]["operation"] for s in api_steps], ["prepare", "publish"])
        analyze = next(s for s in steps if s.get("id") == "trae")
        self.assertEqual(analyze['uses'], './.github/actions/catlass-ai')
        self.assertNotIn("ATOMGIT_TOKEN", analyze.get("env", {}))
        publish = api_steps[1]['with']
        self.assertEqual(publish['stage-result'], '_issue-analysis/reply')
        extract = next(s for s in steps if s.get('id') == 'extract')
        self.assertEqual(extract['env']['STAGE_RESULT'], '${{ steps.trae.outputs.result-directory }}')
        for redundant in ('model', 'response-file', 'issue-url'):
            self.assertNotIn(redundant, publish)

    def test_all_model_publishers_consume_results_without_reselecting_the_model(self):
        for name in ('fix-atomgit-issue', 'review-atomgit-pr'):
            text = (ROOT / f'.github/workflows/{name}.yml').read_text(encoding='utf-8')
            self.assertNotIn('TASK_RESPONSE', text)
            self.assertNotIn('model:', text)
            self.assertNotIn('expected-version: 0.209.1', text)
        action = yaml.safe_load((ROOT / '.github/actions/analyze-ci-failure/action.yml').read_text(encoding='utf-8'))
        render = next(step for step in action['runs']['steps'] if step.get('id') == 'render')
        self.assertEqual(render['env']['TRAE_RESULT'], '${{ steps.model.outputs.result-directory }}')
        self.assertNotIn('ANALYSIS_MODEL', render['env'])
        self.assertNotIn('ANALYSIS_RESPONSE', render['env'])

    def test_release_workflow_uses_release_stage(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release-dsl-wheel.yml").read_text(encoding="utf-8"))
        self.assertTrue(any(s.get("uses") == "./.github/actions/atomgit-release"
                            for s in workflow["jobs"]["publish-atomgit"]["steps"]))

    def test_issue_role_gate_controls_replies_but_not_classification(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/reply-atomgit-issue.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["reply"]["steps"]
        roles = next(s for s in steps if s.get("id") == "roles")
        self.assertEqual(roles["uses"], "./.github/actions/community-repo-roles")
        gate_index = next(i for i, s in enumerate(steps) if s.get("id") == "eligibility")
        guarded = [s for s in steps if s.get("uses") == "./.github/actions/atomgit-issue"]
        self.assertEqual(len(guarded), 2)
        for step in guarded:
            self.assertLess(gate_index, steps.index(step))
            self.assertIn("steps.eligibility.outputs.analyze == 'true'", step["if"])
            if step.get("uses") == "./.github/actions/atomgit-issue":
                self.assertEqual(step["with"]["roles-file"], "${{ steps.roles.outputs.result-file }}")
        self.assertFalse(any(s.get("id") == "assign" for s in steps))
        request = next(s for s in steps if s.get('id') == 'request')
        self.assertEqual(request['env']['ANALYZE_REPLY'], '${{ steps.eligibility.outputs.analyze }}')
        self.assertEqual(request['env']['ANALYZE_LABEL'], '${{ steps.label.outputs.analyze }}')


if __name__ == "__main__":
    unittest.main()
