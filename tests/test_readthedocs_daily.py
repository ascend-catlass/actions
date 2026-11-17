"""Exercise daily documentation triggering without sending real webhooks."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/nightly-dsl-wheel.yml"


class ReadTheDocsDailyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        self.job = self.workflow["jobs"]["readthedocs"]

    def test_languages_run_independently_on_main(self):
        self.assertEqual(self.job["if"], "${{ github.ref == 'refs/heads/main' }}")
        self.assertNotIn("needs", self.job)
        self.assertFalse(self.job["strategy"]["fail-fast"])
        self.assertEqual(self.job["permissions"], {})
        self.assertEqual(
            self.job["strategy"]["matrix"]["include"],
            [
                {"project": "catlass", "integration_id": "331563",
                 "token_secret": "READTHEDOCS_ZH_WEBHOOK_TOKEN"},
                {"project": "catlass-en", "integration_id": "331564",
                 "token_secret": "READTHEDOCS_EN_WEBHOOK_TOKEN"},
            ],
        )
        self.assertEqual(
            self.job["steps"][0]["env"]["RTD_WEBHOOK_TOKEN"],
            "${{ secrets[matrix.token_secret] }}",
        )

    @unittest.skipIf(os.name == "nt", "job shell behavior requires Linux bash")
    def test_webhook_outcomes_and_token_handling(self):
        script = self.job["steps"][0]["run"]
        # curl is replaced by a shell function; no network or live token is used.
        stub = (
            'curl() { printf "%s\\n" "$@" > "$CALL_LOG"; '
            'printf "%s" "$MOCK_STATUS"; return "$MOCK_EXIT"; }\n'
        )
        for token, status, exit_code, accepted in [
            ("", "200", 0, False),
            ("fake&a+b=token", "200", 0, True),
            ("fake&a+b=token", "202", 0, True),
            ("fake&a+b=token", "302", 0, False),
            ("fake&a+b=token", "403", 22, False),
            ("fake&a+b=token", "000", 28, False),
        ]:
            with self.subTest(token_present=bool(token), status=status):
                with tempfile.TemporaryDirectory() as directory:
                    log = Path(directory) / "curl.log"
                    summary = Path(directory) / "summary.md"
                    env = {
                        **os.environ,
                        "RTD_WEBHOOK_TOKEN": token,
                        "RTD_PROJECT": "catlass",
                        "RTD_INTEGRATION_ID": "331563",
                        "GITHUB_STEP_SUMMARY": str(summary),
                        "CALL_LOG": str(log),
                        "MOCK_STATUS": status,
                        "MOCK_EXIT": str(exit_code),
                    }
                    result = subprocess.run(
                        ["bash", "-c", stub + script], env=env, text=True,
                        capture_output=True, timeout=10,
                    )
                    self.assertEqual(result.returncode == 0, accepted,
                                     result.stdout + result.stderr)
                    self.assertNotIn("fake&a+b=token", result.stdout + result.stderr)
                    self.assertEqual(summary.exists(), accepted)
                    if not token:
                        self.assertFalse(log.exists())
                    else:
                        args = log.read_text().splitlines()
                        self.assertIn("branches=latest", args)
                        self.assertIn("token=" + token, args)
                        self.assertIn("--data-urlencode", args)
                        self.assertIn("--fail", args)
                        self.assertIn("--max-time", args)
                        self.assertEqual(
                            args[-1],
                            "https://app.readthedocs.org/api/v2/webhook/catlass/331563/",
                        )


if __name__ == "__main__":
    unittest.main()
