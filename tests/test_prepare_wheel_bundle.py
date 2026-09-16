from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import prepare_wheel_bundle


class PrepareWheelBundleTest(unittest.TestCase):
    version = "2.1.0"
    source_sha = "a" * 40

    def make_input(self, root: Path) -> Path:
        input_dir = root / "input"
        input_dir.mkdir()
        for arch in prepare_wheel_bundle.ARCHITECTURES:
            wheel_names = []
            for python_tag in prepare_wheel_bundle.PYTHON_TAGS:
                name = (
                    f"ascend_catlass_dsl-{self.version}-{python_tag}-{python_tag}-"
                    f"manylinux_2_27_{arch}.manylinux_2_28_{arch}.whl"
                )
                wheel_names.append(name)
                with zipfile.ZipFile(input_dir / name, "w") as archive:
                    archive.writestr(
                        f"ascend_catlass_dsl-{self.version}.dist-info/METADATA",
                        f"Name: ascend-catlass-dsl\nVersion: {self.version}\n",
                    )
            (input_dir / f"release-metadata-{arch}.json").write_text(
                json.dumps(
                    {
                        "package_version": self.version,
                        "source_sha": self.source_sha,
                        "build_date": "2026-09-16T00:00:00Z",
                        "wheel_files": ",".join(wheel_names),
                    }
                ),
                encoding="utf-8",
            )
            (input_dir / f"npuir-metadata-{arch}.md").write_text(
                f"### {arch}\n\n- AscendNPU-IR commit: {'b' * 40}\n",
                encoding="utf-8",
            )
        return input_dir

    def test_prepares_complete_two_architecture_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            prepare_wheel_bundle.prepare(
                self.make_input(root), output, self.version, self.source_sha, "v2.1.0"
            )
            self.assertEqual(len(list((output / "wheels").glob("*.whl"))), 8)
            self.assertEqual(len((output / "SHA256SUMS").read_text().splitlines()), 8)
            manifest = json.loads((output / "release-manifest.json").read_text())
            self.assertEqual(manifest["version"], self.version)
            self.assertEqual(
                {(item["python_tag"], item["architecture"]) for item in manifest["wheels"]},
                {
                    (python_tag, arch)
                    for python_tag in prepare_wheel_bundle.PYTHON_TAGS
                    for arch in prepare_wheel_bundle.ARCHITECTURES
                },
            )

    def test_rejects_missing_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = self.make_input(root)
            next(input_dir.glob("*cp310*aarch64.whl")).unlink()
            with self.assertRaisesRegex(RuntimeError, "Expected 8 wheels"):
                prepare_wheel_bundle.prepare(
                    input_dir,
                    root / "output",
                    self.version,
                    self.source_sha,
                    "v2.1.0",
                )


if __name__ == "__main__":
    unittest.main()
