"""Build the stable, metadata-only legacy distribution with setuptools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def build(output_dir: Path, version: str, requires_python: str) -> Path:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Compatibility packages require an exact stable version")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Compatibility wheel output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catlass-compat-") as directory:
        project = Path(directory)
        readme = (
            "# ascend-catlass-dsl\n\n"
            "This is a compatibility package. It contains no Python modules and "
            f"installs ascend-catlass=={version}. New users should install ascend-catlass directly.\n"
        )
        (project / "README.md").write_text(readme, encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools>=77", "wheel"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            '[project]\nname = "ascend-catlass-dsl"\n'
            f'version = {json.dumps(version)}\n'
            'description = "Compatibility package for ascend-catlass"\n'
            'readme = "README.md"\n'
            f'requires-python = {json.dumps(requires_python)}\n'
            f'dependencies = ["ascend-catlass=={version}"]\n\n'
            '[tool.setuptools]\npackages = []\n',
            encoding="utf-8",
        )
        env = dict(os.environ, SOURCE_DATE_EPOCH="315532800")
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--no-isolation",
             "--outdir", str(output_dir.resolve()), str(project)],
            check=True, env=env,
        )
    expected = output_dir / f"ascend_catlass_dsl-{version}-py3-none-any.whl"
    if not expected.is_file() or list(output_dir.iterdir()) != [expected]:
        raise ValueError("Expected exactly one universal compatibility wheel")
    return expected
