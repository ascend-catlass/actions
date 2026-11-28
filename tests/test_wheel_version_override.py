"""Exercise the workflow's SCM override against real setuptools wheel metadata."""
import email.parser
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class WheelVersionOverrideTests(unittest.TestCase):
    def test_resolved_versions_reach_the_renamed_distribution(self):
        config = yaml.safe_load((ROOT / ".github/workflows/build-dsl-wheel.yml").read_text(encoding="utf-8"))
        step = next(s for s in config["jobs"]["build"]["steps"] if s.get("name") == "Build wheels")
        for version in ("2.3.0", "2.3.1.dev20261128", "2.3.1.dev20261128+pr2043.g599d72799014"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                (project / "metadata").mkdir()
                (project / "pyproject.toml").write_text(
                    '[build-system]\nrequires = ["setuptools>=77", "setuptools-scm>=8"]\n'
                    'build-backend = "setuptools.build_meta"\n'
                    '[project]\nname = "ascend-catlass"\ndynamic = ["version"]\n'
                    '[tool.setuptools]\npackages = []\n'
                    '[tool.setuptools_scm]\nfallback_version = "0.0.0"\n', encoding="utf-8",
                )
                environment = step["env"]["CIBW_ENVIRONMENT"].replace(
                    "${{ needs.resolve.outputs.package_version }}", version,
                )
                overrides = dict(item.split("=", 1) for item in shlex.split(environment)
                                 if item.startswith("SETUPTOOLS_SCM_"))
                env = {key: value for key, value in os.environ.items()
                       if not key.startswith(("SETUPTOOLS_SCM_", "GIT_CONFIG_"))}
                env.update(overrides)
                subprocess.run(
                    [sys.executable, "-c", "from setuptools.build_meta import prepare_metadata_for_build_wheel; "
                     "prepare_metadata_for_build_wheel('metadata')"],
                    cwd=project, env=env, check=True, capture_output=True, text=True,
                )
                metadata_path = next((project / "metadata").glob("*.dist-info/METADATA"))
                metadata = email.parser.BytesParser().parsebytes(metadata_path.read_bytes())
                self.assertEqual(metadata["Name"], "ascend-catlass")
                self.assertEqual(metadata["Version"], version)


if __name__ == "__main__":
    unittest.main()
