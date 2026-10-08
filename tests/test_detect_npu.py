import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".github/actions/prepare-ci-tests/detect_npu.sh"


def npu_table(chips, model="950"):
    lines = []
    for card, free, processes in chips:
        if model == "950":
            lines.append(f"| {card} | 950PR | OK | 70 |")
        else:
            lines.append(f"| {card} 910B3 | OK | 70 |")
        lines.append(f"| 0 | 0000:01:00.0 | 0 | 100 / {100 + free} |")
    lines.append("| NPU Chip | Process id | Process name | Process memory(MB) |")
    for card, _, processes in chips:
        if not processes:
            lines.append(f"| No running processes found in NPU {card} |")
        for number in range(processes):
            lines.append(f"| {card} 0 | {1000 + number} | python | 100 |")
    return "\n".join(lines)


class DetectNpuTest(unittest.TestCase):
    def run_selector(self, table):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "info.txt"
            fixture.write_text(table)
            npu_smi = root / "npu-smi"
            npu_smi.write_text('#!/bin/sh\ncat "$NPU_SMI_FIXTURE"\n')
            npu_smi.chmod(0o755)
            env = dict(os.environ)
            for name in ("NPU_SELECTED_DEVICE", "CI_REQUIRE_HEALTHY_NPU", "CI_NPU_MAX_TASKS", "CI_NPU_MIN_FREE_MB"):
                env.pop(name, None)
            env.update(NPU_SMI_BIN=str(npu_smi), NPU_SMI_FIXTURE=str(fixture))
            return subprocess.run(["bash", str(SCRIPT), "--env"], env=env, text=True, capture_output=True)

    def test_selects_fewest_processes_on_950_and_910(self):
        for model in ("950", "910"):
            with self.subTest(model=model):
                result = self.run_selector(npu_table([(0, 32000, 2), (3, 32000, 1)], model))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "export NPU_SELECTED_DEVICE=3")

    def test_idle_card_and_tie_use_lowest_card_id(self):
        result = self.run_selector(npu_table([(7, 32000, 0), (2, 32000, 0)]))
        self.assertEqual(result.stdout.strip(), "export NPU_SELECTED_DEVICE=2")

    def test_preserves_upstream_memory_and_process_limits(self):
        result = self.run_selector(npu_table([(0, 1024, 0), (1, 32000, 4), (2, 32000, 2)]))
        self.assertEqual(result.stdout.strip(), "export NPU_SELECTED_DEVICE=2")

    def test_no_candidate_fails(self):
        for table in ("", npu_table([(0, 1024, 0), (1, 32000, 4)])):
            with self.subTest(table=table):
                result = self.run_selector(table)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("export", result.stdout)


if __name__ == "__main__":
    unittest.main()
