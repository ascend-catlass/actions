import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/actions/prepare-ci-tests/install-requirements.py"
spec = importlib.util.spec_from_file_location("install_ci_requirements", SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallRequirementsTests(unittest.TestCase):
    def test_wheel_matches_python_and_architecture(self):
        for minor in (10, 11, 12):
            for arch in ("x86_64", "aarch64"):
                with self.subTest(minor=minor, arch=arch), \
                     patch.object(installer.sys, "platform", "linux"), \
                     patch.object(installer.sys, "version_info", Version(minor)), \
                     patch.object(installer.platform, "machine", return_value=arch):
                    self.assertIn(f"cp3{minor}-cp3{minor}-manylinux_2_28_{arch}",
                                  installer.torch_wheel_url())

    def test_install_order_constraints_and_filtering(self):
        self.exercise_install(download_fails=False)

    def test_unsupported_architecture_fails_before_pip(self):
        with patch.object(installer.platform, "machine", return_value="riscv64"), \
             patch.object(installer.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                installer.main()
            run.assert_not_called()

    def test_failed_download_does_not_uninstall(self):
        self.exercise_install(download_fails=True)

    def exercise_install(self, download_fails):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            original = "torch\nTorch_NPU>=2.9\ntorchvision\nnumpy<=1.24.0\nml_dtypes\n"
            (root / "requirements.txt").write_text(original)
            commands = []

            def run(args, **kwargs):
                commands.append(args)
                self.assertTrue(kwargs["check"])
                self.assertEqual(kwargs["cwd"], root)
                if "download" in args:
                    if download_fails:
                        raise subprocess.CalledProcessError(1, args)
                    dest = Path(args[args.index("--dest") + 1])
                    for name in ("torch.whl", "torch_npu.whl"):
                        (dest / name).touch()
                if "install" in args:
                    constraints = Path(args[args.index("-c") + 1]).read_text()
                    self.assertEqual(constraints, "torch==2.9.0+cpu\ntorch-npu==2.9.0\n")
                    if "-r" in args:
                        self.assertEqual(Path(args[-1]).read_text(), "numpy<=1.24.0\nml_dtypes\n")

            with patch.object(installer.sys, "argv", [str(SCRIPT), str(root)]), \
                 patch.object(installer, "torch_wheel_url", return_value="https://mirror.nju.edu.cn/torch.whl"), \
                 patch.object(installer.subprocess, "run", side_effect=run):
                if download_fails:
                    with self.assertRaises(subprocess.CalledProcessError):
                        installer.main()
                    self.assertEqual(len(commands), 1)
                else:
                    installer.main()
                    self.assertEqual([args[3] for args in commands[:-1]],
                                     ["download", "uninstall", "install", "install"])
                    self.assertIn("torch.version.cuda is None", commands[-1][-1])
            self.assertEqual((root / "requirements.txt").read_text(), original)
            self.assertFalse(list(root.glob(".ci-requirements-*")))


class Version(tuple):
    def __new__(cls, minor):
        return super().__new__(cls, (3, minor))

    major = property(lambda self: self[0])
    minor = property(lambda self: self[1])


if __name__ == "__main__":
    unittest.main()
