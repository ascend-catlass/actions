"""Check the container resource limits and their input validation."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/actions/create-ascend-container/create-ascend-container.sh"
ACTION = ROOT / ".github/actions/create-ascend-container/action.yml"


def run_script(tmpdir, env_overrides):
    """Run the script up to the docker calls, which a stub intercepts."""
    # A real CANN/NPUIR layout under the temp dir satisfies the script's
    # preflight checks without a provisioned Ascend host.
    cann = Path(tmpdir) / "cann"
    npuir = Path(tmpdir) / "npuir"
    (cann / "ascend-toolkit").mkdir(parents=True, exist_ok=True)
    (cann / "ascend-toolkit" / "set_env.sh").write_text("# stub\n", encoding="utf-8")
    npuir.mkdir(parents=True, exist_ok=True)
    (npuir / ".npuir-pipeline").write_text("SOURCE_SHA=stub\n", encoding="utf-8")

    output_file = Path(tmpdir) / "github-output"
    output_file.write_text("", encoding="utf-8")
    # Stand-ins for the Ascend driver paths, which only exist on a real host.
    driver_dirs = []
    for name in ("dcmi", "driver", "install.info"):
        path = Path(tmpdir) / "driver" / name
        path.mkdir(parents=True, exist_ok=True)
        driver_dirs.append(str(path))
    env = {
        **os.environ,
        "NAME": "catlass-rdv-test",
        "CANN_REPO": "catlass-dsl-lab",
        "CANN_TAG": "ubuntu24-py312-rdv-v2",
        "HOST_WORKTREE": str(tmpdir),
        "CONTAINER_WORKTREE": "/workspace/catlass",
        "CANN_ROOT": str(cann / "ascend-toolkit"),
        "NPUIR_ROOT": str(npuir),
        "GITHUB_OUTPUT": str(output_file),
        "DRIVER_PATHS": " ".join(driver_dirs),
        **env_overrides,
    }
    # Replace docker work with a stub so the test exercises argument assembly
    # without touching a Docker daemon. `container inspect` must fail so the
    # script treats the name as free.
    stub = (
        'docker() {\n'
        '  if [[ "$1" == "container" && "$2" == "inspect" ]]; then return 1; fi\n'
        '  if [[ "$1" == "info" ]]; then return 0; fi\n'
        '  echo "DOCKER $*"\n'
        '}\n'
        'bash() { :; }\n'
        f'source "{SCRIPT}"\n'
    )
    return subprocess.run(
        ["bash", "-c", stub],
        capture_output=True, text=True, env=env,
        cwd=str(ROOT), timeout=60,
    )


class ContainerResourceLimitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_action_exposes_default_cpu_and_memory_limits(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertRegex(text, r"cpus:\n(?:.*\n)*?\s+default: '16'")
        self.assertRegex(text, r"memory:\n(?:.*\n)*?\s+default: 128g")
        # Swap must default to the memory value so containers cannot swap.
        self.assertRegex(text, r"memory-swap:\n(?:.*\n)*?\s+default: 128g")

    def test_script_rejects_malformed_limits(self):
        for bad_cpus in ["0", "-1", "16.5", "sixteen", "16 "]:
            with self.subTest(cpus=bad_cpus):
                result = run_script(self._tmp.name, {"CONTAINER_CPUS": bad_cpus})
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("cpus must be", result.stdout + result.stderr)
        for bad_memory in ["0", "-5", "128gb", "lots", "128g "]:
            with self.subTest(memory=bad_memory):
                result = run_script(self._tmp.name, {"CONTAINER_MEMORY": bad_memory})
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("memory must", result.stdout + result.stderr)

    def test_swap_requires_memory(self):
        result = run_script(self._tmp.name, {"CONTAINER_MEMORY": "", "CONTAINER_MEMORY_SWAP": "128g"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("memory-swap requires memory", result.stdout + result.stderr)

    def test_limits_are_passed_to_docker_run(self):
        result = run_script(self._tmp.name, {
            "CONTAINER_CPUS": "16",
            "CONTAINER_MEMORY": "128g",
            "CONTAINER_MEMORY_SWAP": "128g",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--cpus 16", result.stdout)
        self.assertIn("--memory 128g", result.stdout)
        self.assertIn("--memory-swap 128g", result.stdout)

    def test_parallelism_follows_the_cpu_cap(self):
        result = run_script(self._tmp.name, {
            "CONTAINER_CPUS": "16",
            "CONTAINER_MEMORY": "128g",
            "CONTAINER_MEMORY_SWAP": "128g",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CMAKE_BUILD_PARALLEL_LEVEL=16", result.stdout)

    def test_explicit_parallelism_is_preserved(self):
        result = run_script(self._tmp.name, {
            "CONTAINER_CPUS": "16",
            "CONTAINER_MEMORY": "128g",
            "CONTAINER_MEMORY_SWAP": "128g",
            "CMAKE_BUILD_PARALLEL_LEVEL": "8",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("CMAKE_BUILD_PARALLEL_LEVEL=16", result.stdout)

    def test_empty_limits_disable_the_flags(self):
        result = run_script(self._tmp.name, {
            "CONTAINER_CPUS": "",
            "CONTAINER_MEMORY": "",
            "CONTAINER_MEMORY_SWAP": "",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("--cpus", result.stdout)
        self.assertNotIn("--memory", result.stdout)


if __name__ == "__main__":
    unittest.main()
