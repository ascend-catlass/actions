"""Exercise default and host-specific dependency dispatch routing."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/dependency_runner_matrix.py"
spec = importlib.util.spec_from_file_location("dependency_runner_matrix", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DependencyRunnerMatrixTests(unittest.TestCase):
    def test_defaults_preserve_both_existing_architectures_and_pools(self):
        for label in ["bz", "ascend-catlass-dsl-build"]:
            rows = module.select_matrix("", "x86_64", label)["include"]
            self.assertEqual([row["target_arch"] for row in rows], ["x86_64", "aarch64"])
            self.assertEqual([row["runs_on"] for row in rows], [
                ["self-hosted", "Linux", label, "X64"],
                ["self-hosted", "Linux", label, "ARM64"],
            ])

    def test_explicit_host_produces_only_one_matching_architecture(self):
        for cpu, arch in [("x86_64", "X64"), ("aarch64", "ARM64")]:
            rows = module.select_matrix("host-179-223-2-2", cpu, "bz")["include"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cpu"], cpu)
            self.assertEqual(rows[0]["runs_on"], ["self-hosted", "Linux", "host-179-223-2-2", arch])
            self.assertEqual(rows[0]["container_image"], f"quay.io/pypa/manylinux_2_28_{cpu}")
            self.assertEqual(rows[0]["use_all_cores"], cpu == "aarch64")

    def test_rejects_invalid_architectures_and_label_lists(self):
        with self.assertRaises(ValueError):
            module.select_matrix("host-1", "ppc64le", "bz")
        for value in ['host-1,host-2', '["host-1"]', '${{ secrets.TOKEN }}', 'host 1', '../host']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.select_matrix(value, "x86_64", "bz")

    def test_cli_writes_one_json_matrix_to_actions_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            subprocess.run([sys.executable, str(SCRIPT)], check=True, env={
                **os.environ, "TARGET_RUNNER_LABEL": "host-179-228-2-2", "TARGET_ARCH": "x86_64",
                "DEFAULT_RUNNER_LABEL": "bz", "GITHUB_OUTPUT": str(output),
            })
            key, value = output.read_text().strip().split("=", 1)
            self.assertEqual(key, "matrix")
            self.assertEqual(json.loads(value)["include"][0]["runs_on"][2], "host-179-228-2-2")

    def test_workflows_wire_selected_matrix_and_keep_main_guard(self):
        for name, resolver, worker in [
            ("install-cann-weekly.yml", "resolve", "install"),
            ("build-ascendnpu-ir-20261013.yml", "runners", "prepare"),
        ]:
            workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
            triggers = workflow.get("on", workflow.get(True))
            self.assertIn("runner_label", triggers["workflow_dispatch"]["inputs"])
            jobs = workflow["jobs"]
            self.assertEqual(jobs[worker]["strategy"]["matrix"], "${{ fromJSON(needs." + resolver + ".outputs.matrix) }}")
            self.assertEqual(jobs[worker]["runs-on"], "${{ matrix.runs_on }}")
            self.assertEqual(jobs[resolver]["if"], "${{ github.ref == 'refs/heads/main' }}")
