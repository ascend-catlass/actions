"""Check fleet coverage, single-host dispatch, artifacts and storage rejection."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cann_weekly_runner_matrix import select_weekly_matrix
from cann_weekly_ssh_entry import install_arguments


class WeeklyFleetTests(unittest.TestCase):
    def test_default_covers_all_eleven_unique_hosts(self):
        rows = select_weekly_matrix()["include"]
        self.assertEqual(len(rows), 11)
        self.assertEqual(len({r["host_id"] for r in rows}), 11)
        self.assertEqual(sum(r["cpu"] == "aarch64" for r in rows), 9)
        self.assertEqual(sum(r["cpu"] == "x86_64" for r in rows), 2)
        for row in rows:
            if row["cpu"] == "aarch64":
                self.assertEqual(row["runs_on"], ["self-hosted", "Linux", "bz", "X64"])
                self.assertEqual(row["ssh_host"], row["host_id"][5:].replace("-", "."))
            else:
                self.assertEqual(row["runs_on"], ["self-hosted", "Linux", row["host_id"], "X64"])

    def test_manual_dispatch_selects_only_requested_host(self):
        for label, cpu in [("host-179-182-2-2", "aarch64"), ("host-179-223-2-2", "x86_64")]:
            rows = select_weekly_matrix(label, cpu)["include"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cpu"], cpu)
            self.assertEqual(rows[0]["host_id"], label)
        with self.assertRaises(ValueError):
            select_weekly_matrix("host-179-182-2-2", "x86_64")
        with self.assertRaises(ValueError):
            select_weekly_matrix("host-a,host-b", "aarch64")

    def test_cli_and_workflow_use_fleet_matrix_and_unique_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "outputs"
            subprocess.run([sys.executable, str(ROOT / "scripts/cann_weekly_runner_matrix.py")], check=True,
                           env={**os.environ, "GITHUB_OUTPUT": str(output), "TARGET_RUNNER_LABEL": ""})
            self.assertEqual(len(json.loads(output.read_text().split("=", 1)[1])["include"]), 11)
        workflow = yaml.safe_load((ROOT / ".github/workflows/install-cann-weekly.yml").read_text())
        resolver = workflow["jobs"]["resolve"]["steps"]
        self.assertTrue(any(s.get("run") == "python3 scripts/cann_weekly_runner_matrix.py" for s in resolver))
        worker = workflow["jobs"]["install"]
        artifact = next(s for s in worker["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
        self.assertIn("matrix.host_id", artifact["with"]["name"])
        self.assertFalse(worker["strategy"]["fail-fast"])
        install = next(s for s in worker["steps"] if s.get("name") == "Install only if this build is missing on the host")
        self.assertIn('ssh -T -F "$HOME/.ssh/cann_weekly_ssh_config"', install["run"])
        self.assertIn('StrictHostKeyChecking=yes', install["run"])
        self.assertEqual(worker["if"], "${{ github.ref == 'refs/heads/main' }}")

    @unittest.skipUnless(shutil.which("bash"), "bash required for storage behavior checks")
    def test_storage_gate_rejects_root_filesystem_or_wrong_destination(self):
        text = (ROOT / "scripts/install-cann-weekly.sh").read_text()
        gate = text.split('# All managed hosts store /opt on their LVM /home filesystem.\n', 1)[1].split('if [[ -f', 1)[0]
        for real, mount, success in [("/home/opt/cann_weekly", "/home", True),
                                     ("/home/opt/cann_weekly", "/", False),
                                     ("/opt/cann_weekly", "/home", False)]:
            shell = 'set -euo pipefail\nroot=/opt/cann_weekly\nreadlink() { printf "%s" "$TEST_REAL"; }\nfindmnt() { printf "%s" "$TEST_MOUNT"; }\n' + gate
            result = subprocess.run(["bash", "-c", shell], capture_output=True, text=True,
                                    env={**os.environ, "TEST_REAL": real, "TEST_MOUNT": mount})
            self.assertEqual(result.returncode == 0, success, result.stderr)

    def test_ssh_entry_rejects_shells_forwarding_and_injection(self):
        expected = ["20261009000323778", "9.3.0~weekly.20261009.01", "aarch64"]
        self.assertEqual(install_arguments("install-weekly " + " ".join(expected)), expected)
        for command in ["", "bash", "cat /etc/shadow", "sftp", "install-weekly " + " ".join(expected) + "; id",
                        "install-weekly 20261010000323778 9.3.0~weekly.20261009.01 aarch64",
                        "install-weekly 20261009000323778 9.3.0~weekly.20261009.01 ppc64le"]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                install_arguments(command)
