"""Reject incompatible cached compiler trees before starting a DSL job."""
import os
from pathlib import Path
import platform
import shutil
import shlex
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/dsl-env/run.sh"
SHA = "693abf31f3d88d13d30d9578fcf6513b90c0ee33"
CONTRACT = "clang19-lld19-release-rtti-assert-triton-zstd-off-v1"


@unittest.skipUnless(shutil.which("bash") and os.name != "nt", "requires Linux bash")
class DslEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.venv, self.cann, self.npuir = [self.root / n for n in ("source", "venv", "cann", "npuir")]
        self.source.mkdir()
        for path, content in {
            self.venv / "bin/activate": ":\n",
            self.cann / "set_env.sh": f'export ASCEND_HOME_PATH="{self.cann}"\n',
            self.npuir / "build/install/lib/cmake/mlir/MLIRConfig.cmake": "",
            self.npuir / "build/install/lib/cmake/llvm/LLVMConfig.cmake": "",
            self.npuir / "third-party/llvm-project/mlir/CMakeLists.txt": "",
        }.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.marker = self.npuir / ".npuir-pipeline"
        self.marker.write_text(f"SOURCE_SHA={SHA}\nBUILD_CONTRACT={CONTRACT}\nTARGET_ARCH={platform.machine()}\n")

    def run_environment(self, expected=SHA):
        env = os.environ.copy()
        env.pop("CATLASS_DSL_EXPECTED_NPUIR_SHA", None)
        if expected:
            env["CATLASS_DSL_EXPECTED_NPUIR_SHA"] = expected
        return subprocess.run(["bash", str(SCRIPT), *map(str, (self.source, self.venv, self.cann, self.npuir)), "--", "bash", "-c", 'printf "%s\\n" "$CATLASS_DSL_PREBUILT_ASCENDNPU_IR" "$CMAKE_ARGS"'], env=env, text=True, capture_output=True)

    def test_matching_archive_and_local_lit(self):
        result = self.run_environment()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.npuir), result.stdout)
        self.assertIn(str(self.venv / "bin/lit"), result.stdout)

    def test_different_source_is_rejected(self):
        result = self.run_environment("a" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)

    def test_different_architecture_is_rejected(self):
        self.marker.write_text(self.marker.read_text().replace(platform.machine(), "wrong-arch"))
        self.assertNotEqual(self.run_environment().returncode, 0)

    def test_missing_metadata_is_rejected(self):
        self.marker.unlink()
        self.assertNotEqual(self.run_environment().returncode, 0)

    def test_revision_is_read_from_source_gitlink(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True)
        git("init", "--quiet")
        git("update-index", "--add", "--cacheinfo", f"160000,{SHA},python/tla_dsl/3rdparty/AscendNPU-IR")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        result = self.run_environment(expected=None)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_container_bootstrap_does_not_reactivate_in_test_children(self):
        fake_bin = self.root / 'fake-bin'
        fake_bin.mkdir()
        fake_python = fake_bin / 'python'
        fake_python.write_text('#!/bin/sh\nexit 0\n')
        fake_python.chmod(0o755)
        activations = self.root / 'activations'
        (self.venv / 'bin/activate').write_text(
            f'printf "activated\\n" >> {shlex.quote(str(activations))}\n'
        )
        env = {**os.environ, 'BASH_ENV': str(SCRIPT.parent / 'container-env.sh'),
               'CATLASS_DSL_VENV': str(self.venv), 'ASCEND_HOME_PATH': str(self.cann),
               'CATLASS_DSL_PREBUILT_ASCENDNPU_IR': str(self.npuir)}
        child = 'PATH=' + shlex.quote(str(fake_bin)) + ':"$PATH" ASCEND_HOME_PATH=/missing bash -c ' + shlex.quote('command -v python')
        entry = self.root / 'test-step.sh'
        entry.write_text(child + '\n')
        result = subprocess.run(['bash', str(entry)], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), str(fake_python))
        self.assertEqual(activations.read_text().splitlines(), ['activated'])


if __name__ == "__main__":
    unittest.main()
