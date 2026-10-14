"""Exercise the adapter contract without a paid Trae account or CLI installation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("trae_cn_stage", ROOT / ".github/actions/trae-cn/run.py")
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.prompt = '中文提示\n$(touch injected)\n`echo injected`\n::error::literal\n'
        (self.repo / "prompt.md").write_text(self.prompt, encoding="utf-8")
        self.cli = self.root / "traecli"
        self.cli.touch()
        self.env = patch.dict(os.environ, {
            "GITHUB_WORKSPACE": str(self.repo), "RUNNER_TEMP": str(self.root),
            "GITHUB_OUTPUT": str(self.root / "outputs"), "TRAE_STAGE_PAT": "private-test-token",
            "TRAE_STAGE_PROMPT_FILE": "prompt.md", "GITHUB_TOKEN": "do-not-pass",
            "OTHER_SECRET": "do-not-pass-either", "PATH": os.environ.get("PATH", ""),
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.calls = []

    def fake_invoke(self, argv, cwd, env, deadline, stdout, stderr, stdin=None):
        self.calls.append((argv, cwd, env.copy(), stdin))
        stdout.touch()
        stderr.touch()
        if argv[1] == "--version":
            stdout.write_text("traecli 2.0.1\n", encoding="utf-8")
        elif "--help" in argv:
            stdout.write_text("--json --output-last-message --ephemeral --ignore-user-config")
        elif argv[1] == "exec":
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                "答复\n::warning::literal\nprivate-test-token\n", encoding="utf-8")
            stdout.write_text('{"type":"done"}\n', encoding="utf-8")
        return 0

    def run_stage(self, invoke=None):
        with patch.object(stage.platform, "system", return_value="Linux"), \
             patch.object(stage.shutil, "which", return_value=str(self.cli)), \
             patch.object(stage, "invoke", side_effect=invoke or self.fake_invoke):
            code = stage.main()
        result_dir = next(self.root.glob("trae-cn-result-*"))
        return code, json.loads((result_dir / "result.json").read_text(encoding="utf-8")), result_dir

    def test_success_prompt_literal_auth_isolation_and_redaction(self):
        code, result, directory = self.run_stage()
        self.assertEqual((code, result["status"], result["cli_version"]), (0, "success", "2.0.1"))
        argv, cwd, env, stdin = self.calls[-1]
        self.assertEqual(stdin.decode(), self.prompt)
        self.assertEqual(cwd, self.repo)
        self.assertEqual(argv[-1], "-")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertEqual(argv[argv.index("--ask-for-approval") + 1], "never")
        for name in ["GITHUB_TOKEN", "OTHER_SECRET", "TRAE_STAGE_PAT", "TRAECLI_PERSONAL_ACCESS_TOKEN"]:
            self.assertNotIn(name, env)
        login_call = next(call for call in self.calls if call[0][1] == "login")
        self.assertIn("TRAECLI_PERSONAL_ACCESS_TOKEN", login_call[2])
        self.assertFalse(Path(env["HOME"]).exists())
        self.assertFalse(list(self.root.glob("trae-cn-auth-*")))
        response = (directory / "response.md").read_text(encoding="utf-8")
        self.assertIn("答复", response)
        self.assertIn("[REDACTED]", response)
        self.assertNotIn("private-test-token", response)
        self.assertNotIn("答复", (self.root / "outputs").read_text())

    def test_schema_and_model_are_separate_arguments(self):
        (self.repo / "schema.json").write_text('{"type":"object"}', encoding="utf-8")
        os.environ.update(TRAE_STAGE_SCHEMA="schema.json", TRAE_STAGE_MODEL="model name")

        def invoke(*args, **kwargs):
            code = self.fake_invoke(*args, **kwargs)
            if args[0][1] == "exec" and "--help" not in args[0]:
                argv = args[0]
                self.assertEqual(json.loads(Path(argv[argv.index("--output-schema") + 1]).read_text()),
                                 {"type": "object"})
                Path(argv[argv.index("--output-last-message") + 1]).write_text('{"ok":true}')
            return code

        code, result, _ = self.run_stage(invoke)
        self.assertEqual(code, 0)
        argv = self.calls[-1][0]
        self.assertEqual(argv[argv.index("--model") + 1], "model name")

    def test_timeout_fails_and_preserves_manifest(self):
        def timeout(*args, **kwargs):
            if args[0][1] == "exec" and "--help" not in args[0]:
                raise subprocess.TimeoutExpired(args[0], 1)
            return self.fake_invoke(*args, **kwargs)
        code, result, _ = self.run_stage(timeout)
        self.assertEqual((code, result["status"]), (124, "timeout"))
        self.assertFalse(list(self.root.glob("trae-cn-auth-*")))

    def test_login_failure_never_invokes_agent(self):
        def fail(*args, **kwargs):
            self.fake_invoke(*args, **kwargs)
            return 7 if args[0][1] == "login" else 0
        code, result, _ = self.run_stage(fail)
        self.assertEqual((code, result["status"]), (1, "failed"))
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(list(self.root.glob("trae-cn-auth-*")))

    def test_nonzero_agent_exit_is_preserved(self):
        def fail(*args, **kwargs):
            self.fake_invoke(*args, **kwargs)
            return 9 if args[0][1] == "exec" and "--help" not in args[0] else 0
        code, result, _ = self.run_stage(fail)
        self.assertEqual((code, result["status"], result["exit_code"]), (9, "failed", 9))

    def test_no_answer_is_failure(self):
        def empty(*args, **kwargs):
            self.fake_invoke(*args, **kwargs)
            if args[0][1] == "exec" and "--help" not in args[0]:
                Path(args[0][args[0].index("--output-last-message") + 1]).unlink()
            return 0
        self.assertEqual(self.run_stage(empty)[0], 1)

    def test_exact_version_mismatch_stops_before_login(self):
        os.environ["TRAE_STAGE_VERSION"] = "2.0.2"
        self.assertEqual(self.run_stage()[0], 1)
        self.assertEqual(len(self.calls), 1)

    def test_legacy_cli_fails_before_login(self):
        def legacy(*args, **kwargs):
            self.fake_invoke(*args, **kwargs)
            return 2 if "--help" in args[0] else 0
        code, result, _ = self.run_stage(legacy)
        self.assertEqual(code, 1)
        self.assertIn("2.0 exec interface", result["message"])
        self.assertEqual(len(self.calls), 2)

    def test_cancelled_cleans_credentials(self):
        def cancel(*args, **kwargs):
            if args[0][1] == "exec" and "--help" not in args[0]:
                raise KeyboardInterrupt
            return self.fake_invoke(*args, **kwargs)
        code, result, _ = self.run_stage(cancel)
        self.assertEqual((code, result["status"]), (130, "cancelled"))
        self.assertFalse(list(self.root.glob("trae-cn-auth-*")))

    def test_missing_pat_fails_before_any_subprocess(self):
        os.environ["TRAE_STAGE_PAT"] = ""
        self.assertEqual(self.run_stage()[0], 1)
        self.assertEqual(self.calls, [])

    def test_invalid_inputs_fail_before_subprocess(self):
        for variable, value in [("PROMPT", "also provided"), ("SANDBOX", "danger-full-access"),
                                ("TIMEOUT", "nan"), ("TIMEOUT", "0"), ("TIMEOUT", "3601"),
                                ("HOST", "http://example.com"), ("HOST", "https://user:pass@example.com"),
                                ("PROMPT_FILE", "../outside.md"), ("WORKDIR", "..")]:
            with self.subTest(variable=variable, value=value), \
                 patch.dict(os.environ, {f"TRAE_STAGE_{variable}": value}):
                with self.assertRaises((stage.StageError, OSError)):
                    stage.prepare(self.repo)

    def test_empty_prompt_and_invalid_schema(self):
        (self.repo / "prompt.md").write_text("  \n")
        with self.assertRaises(stage.StageError):
            stage.prepare(self.repo)
        (self.repo / "prompt.md").write_text("analyze")
        (self.repo / "schema.json").write_text("[]")
        os.environ["TRAE_STAGE_SCHEMA"] = "schema.json"
        with self.assertRaises(stage.StageError):
            stage.prepare(self.repo)

    def test_redaction_across_chunk_boundary(self):
        path = self.root / "large.log"
        path.write_bytes(b"x" * 65530 + b"private-test-token" + b"y" * 65536)
        stage.redact_file(path, "private-test-token")
        self.assertEqual(path.read_bytes(), b"x" * 65530 + b"[REDACTED]" + b"y" * 65536)

    @unittest.skipUnless(os.name == "posix", "Linux process-group integration")
    def test_real_process_timeout_kills_group(self):
        import sys
        import time
        with self.assertRaises(subprocess.TimeoutExpired):
            stage.invoke([sys.executable, "-c", "import time; time.sleep(30)"],
                         self.repo, os.environ.copy(), time.monotonic() + 0.1,
                         self.root / "out", self.root / "err")


if __name__ == "__main__":
    unittest.main()
