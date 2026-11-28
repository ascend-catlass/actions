"""Exercise real compatibility packaging, offline dependency resolution and release retries."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import urllib.error
import venv
import zipfile

import yaml
from wheel.wheelfile import WheelFile

from scripts.build_compat_wheel import build
from scripts.prepare_wheel_bundle import prepare
from scripts.validate_release_bundle import check_pypi, validate, validate_compat
from tests import test_prepare_wheel_bundle as bundle_fixtures

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityTests(unittest.TestCase):
    version = "2.1.0"
    source_sha = "a" * 40

    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.wheel = build(Path(cls.workspace.name) / "built", cls.version, ">=3.10,<3.14")

    def bundle(self, root):
        inputs = bundle_fixtures.PrepareWheelBundleTest().make_input(root)

        def copy_built(folder, *_):
            folder.mkdir()
            destination = folder / self.wheel.name
            shutil.copy2(self.wheel, destination)
            return destination

        with patch("scripts.build_compat_wheel.build", side_effect=copy_built):
            prepare(inputs, root / "bundle", self.version, self.source_sha, "v2.1.0", with_compat=True)
        return root / "bundle"

    def validate(self, folder, **kwargs):
        return validate(folder, self.version, self.source_sha, "v2.1.0", require_compat=True, **kwargs)

    def test_actual_wheel_is_metadata_only_and_passes_twine(self):
        validate_compat(self.wheel, self.version, ">=3.10,<3.14")
        subprocess.run([sys.executable, "-m", "twine", "check", str(self.wheel)], check=True)
        with zipfile.ZipFile(self.wheel) as archive:
            self.assertTrue(all(name.startswith(f"ascend_catlass_dsl-{self.version}.dist-info/")
                                for name in archive.namelist()))
        with tempfile.TemporaryDirectory() as directory:
            second = build(Path(directory) / "wheel", self.version, ">=3.10,<3.14")
            self.assertEqual(self.wheel.read_bytes(), second.read_bytes())

    def test_compatibility_requires_a_stable_version(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "stable version"):
                build(Path(directory), "2.1.0.dev20261128", ">=3.10,<3.14")

    def test_release_bundle_and_retry_never_rebuild_the_compatibility_wheel(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self.bundle(Path(directory))
            before = {path.name: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
            with patch("scripts.build_compat_wheel.build", side_effect=AssertionError("rebuilt")):
                manifest = self.validate(folder)
                self.validate(folder)
            self.assertEqual(manifest["package"], "ascend-catlass")
            self.assertEqual(manifest["compatibility"]["requires_dist"], "ascend-catlass==2.1.0")
            self.assertEqual(len(list((folder / "wheels").glob("*.whl"))), 8)
            self.assertEqual(len(list((folder / "compat-wheels").glob("*.whl"))), 1)
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()})

    def test_atomgit_assets_exclude_the_pypi_compatibility_wheel(self):
        from scripts.prepare_atomgit_assets import prepare as prepare_assets

        with tempfile.TemporaryDirectory() as directory:
            folder = self.bundle(Path(directory))
            assets = prepare_assets(Mock(request=Mock(return_value={"assets": []})),
                                    "cann/catlass", "v2.1.0", folder)
            self.assertEqual(len(assets), 9)
            self.assertFalse(any("compat" in Path(path).parts for path in assets))
            self.assertFalse(any(Path(path).name.startswith("ascend_catlass_dsl-") for path in assets))

    def test_rejects_identity_changes_missing_compatibility_and_corruption(self):
        cases = ("version", "source_sha", "source_ref", "package", "compatibility", "hash", "extra")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                folder = self.bundle(Path(directory))
                manifest_file = folder / "release-manifest.json"
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                if case == "compatibility":
                    del manifest[case]
                elif case == "hash":
                    next((folder / "compat-wheels").glob("*.whl")).write_bytes(b"corrupt")
                elif case == "extra":
                    (folder / "wheels" / "unexpected.whl").write_bytes(b"extra")
                else:
                    manifest[case] = "incorrect"
                manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises((ValueError, RuntimeError)):
                    self.validate(folder)

    def test_compatibility_rejects_wrong_dependency_python_range_and_payload(self):
        for case in ("dependency", "python", "payload"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                wheel = Path(directory) / self.wheel.name
                with zipfile.ZipFile(self.wheel) as source, zipfile.ZipFile(wheel, "w") as dest:
                    for name in source.namelist():
                        data = source.read(name)
                        if name.endswith("/METADATA"):
                            if case == "dependency":
                                data = data.replace(b"ascend-catlass==2.1.0", b"ascend-catlass>=2.1.0")
                            elif case == "python":
                                data = data.replace(b"<3.14,>=3.10", b">=3.10")
                        dest.writestr(name, data)
                    if case == "payload":
                        dest.writestr("catlass/__init__.py", "")
                with self.assertRaises(ValueError):
                    validate_compat(wheel, self.version, ">=3.10,<3.14")

    def test_pypi_retries_accept_only_identical_published_files(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.validate(self.bundle(Path(directory)))
            main = manifest["wheels"][0]
            compat = manifest["compatibility"]["wheels"][0]

            def response(record):
                return io.BytesIO(json.dumps({"urls": [{"filename": record["name"],
                                   "digests": {"sha256": record["sha256"]}}]}).encode())

            with patch("urllib.request.urlopen", side_effect=[response(main), response(compat)]):
                check_pypi(manifest)
            for code in (404, 500):
                error = urllib.error.HTTPError("https://pypi.org/", code, "test", {}, None)
                with patch("urllib.request.urlopen", side_effect=error):
                    if code == 404:
                        check_pypi(manifest)
                    else:
                        with self.assertRaises(urllib.error.HTTPError):
                            check_pypi(manifest)
            for conflicting in ({"name": "old-native.whl", "sha256": "b" * 64},
                                dict(compat, sha256="b" * 64)):
                with patch("urllib.request.urlopen", side_effect=[response(main), response(conflicting)]):
                    with self.assertRaisesRegex(ValueError, "conflicting ascend-catlass-dsl"):
                        check_pypi(manifest)

    def make_main(self, folder, version, legacy=False):
        name = "ascend_catlass_dsl" if legacy else "ascend_catlass"
        wheel = folder / f"{name}-{version}-py3-none-any.whl"
        prefix = f"{name}-{version}.dist-info"
        with WheelFile(wheel, "w") as archive:
            archive.writestr("catlass/__init__.py", f"VERSION = {version!r}\n")
            archive.writestr(f"{prefix}/METADATA", "Metadata-Version: 2.1\n"
                             f"Name: {name.replace('_', '-')}\nVersion: {version}\n"
                             "Requires-Python: >=3.10,<3.14\n")
            archive.writestr(f"{prefix}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\n"
                             "Root-Is-Purelib: true\nTag: py3-none-any\n")
        return wheel

    def test_offline_install_exact_dependency_and_safe_legacy_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            links = root / "links"
            links.mkdir()
            shutil.copy2(self.wheel, links)
            self.make_main(links, "2.1.1")  # A newer version cannot satisfy the exact requirement.
            env_dir = root / "venv"
            venv.EnvBuilder(with_pip=True).create(env_dir)
            executable = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command = [str(executable), "-m", "pip", "--disable-pip-version-check"]

            def install(*args, check=True):
                return subprocess.run(command + ["install", "--no-index", "--find-links", str(links), *args],
                                      capture_output=True, text=True, check=check)

            self.assertNotEqual(install("ascend-catlass-dsl==2.1.0", check=False).returncode, 0)
            self.make_main(links, "2.1.0")
            install("ascend-catlass-dsl==2.1.0")
            subprocess.run([str(executable), "-c", "import catlass; assert catlass.VERSION == '2.1.0'"], check=True)
            subprocess.run(command + ["uninstall", "-y", "ascend-catlass-dsl", "ascend-catlass"],
                           capture_output=True, check=True)
            self.make_main(links, "2.0.0", legacy=True)
            install("ascend-catlass-dsl==2.0.0")
            # Older native legacy wheels own the same import tree: remove them first.
            subprocess.run(command + ["uninstall", "-y", "ascend-catlass-dsl"], capture_output=True, check=True)
            install("ascend-catlass-dsl==2.1.0")
            subprocess.run([str(executable), "-c", "import catlass; assert catlass.VERSION == '2.1.0'"], check=True)


class ReleaseWiringTests(unittest.TestCase):
    def test_ordered_pypi_publication_and_both_downloads_revalidate(self):
        config = yaml.safe_load((ROOT / ".github/workflows/release-dsl-wheel.yml").read_text(encoding="utf-8"))
        pypi = config["jobs"]["publish-pypi"]
        steps = pypi["steps"]
        publishers = [step for step in steps if step.get("uses", "").startswith("pypa/")]
        self.assertEqual([step["with"]["packages-dir"] for step in publishers],
                         ["release-bundle/wheels", "release-bundle/compat-wheels"])
        self.assertFalse(any(step.get("continue-on-error") or "if" in step for step in publishers))
        self.assertEqual(pypi["environment"]["name"], "pypi")
        for job in ("publish-pypi", "publish-atomgit"):
            steps = config["jobs"][job]["steps"]
            download = next(i for i, s in enumerate(steps) if s.get("uses") == "actions/download-artifact@v4")
            validator = next(i for i, s in enumerate(steps) if s.get("uses") == "./.github/actions/prepare-wheel-bundle")
            self.assertGreater(validator, download)
            self.assertEqual(steps[validator]["with"]["compatibility-package"], "true")
            self.assertIn("inputs.artifact_run_id", steps[download]["with"]["run-id"])
        self.assertEqual(config["jobs"]["prepare"]["steps"][-2]["with"]["compatibility-package"], "true")

    def test_nightly_never_builds_or_uploads_compatibility_package(self):
        config = yaml.safe_load((ROOT / ".github/workflows/nightly-dsl-wheel.yml").read_text(encoding="utf-8"))
        prepare_step = next(s for s in config["jobs"]["prepare"]["steps"]
                            if s.get("uses") == "./.github/actions/prepare-wheel-bundle")
        self.assertNotIn("compatibility-package", prepare_step["with"])
        text = (ROOT / ".github/workflows/nightly-dsl-wheel.yml").read_text(encoding="utf-8")
        self.assertNotIn("compat-wheels", text)
        self.assertNotIn("simple/ascend-catlass/", text)


if __name__ == "__main__":
    unittest.main()
