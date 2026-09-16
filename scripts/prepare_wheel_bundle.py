#!/usr/bin/env python3
"""Validate both architecture builds and prepare one immutable release bundle."""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path


PACKAGE_NAME = "ascend-catlass-dsl"
WHEEL_PREFIX = "ascend_catlass_dsl"
PYTHON_TAGS = ("cp310", "cp311", "cp312", "cp313")
ARCHITECTURES = ("x86_64", "aarch64")


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wheel_identity(path: Path, version: str) -> tuple[str, str]:
    pattern = re.compile(
        rf"^{WHEEL_PREFIX}-{re.escape(version)}-"
        rf"(?P<python>{'|'.join(PYTHON_TAGS)})-(?P=python)-.+_"
        rf"(?P<arch>{'|'.join(ARCHITECTURES)})\.whl$"
    )
    match = pattern.fullmatch(path.name)
    if match is None:
        fail(f"Unexpected wheel filename: {path.name}")
    return match.group("python"), match.group("arch")


def validate_wheel_metadata(path: Path, version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            fail(f"{path.name} contains {len(metadata_names)} METADATA files")
        metadata = email.parser.BytesParser().parsebytes(
            archive.read(metadata_names[0]), headersonly=True
        )
    if metadata["Name"] != PACKAGE_NAME:
        fail(f"{path.name} has package name {metadata['Name']!r}")
    if metadata["Version"] != version:
        fail(f"{path.name} has version {metadata['Version']!r}, expected {version}")


def read_build_metadata(input_dir: Path, version: str, source_sha: str) -> list[dict]:
    paths = sorted(input_dir.glob("release-metadata-*.json"))
    if len(paths) != len(ARCHITECTURES):
        fail(f"Expected {len(ARCHITECTURES)} build metadata files, found {len(paths)}")
    result = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("package_version") != version:
            fail(f"{path.name} has a different package version")
        if value.get("source_sha") != source_sha:
            fail(f"{path.name} has a different CATLASS commit")
        result.append(value)
    return result


def prepare(input_dir: Path, output_dir: Path, version: str, source_sha: str, source_ref: str) -> None:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\.dev[0-9]{8})?", version):
        fail(f"Invalid package version: {version}")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        fail(f"Invalid CATLASS commit: {source_sha}")
    if output_dir.exists() and any(output_dir.iterdir()):
        fail(f"Output directory is not empty: {output_dir}")

    build_metadata = read_build_metadata(input_dir, version, source_sha)
    note_paths = sorted(input_dir.glob("npuir-metadata-*.md"))
    if len(note_paths) != len(ARCHITECTURES):
        fail(f"Expected {len(ARCHITECTURES)} NPUIR note files, found {len(note_paths)}")

    wheels = sorted(input_dir.glob("*.whl"))
    expected_count = len(PYTHON_TAGS) * len(ARCHITECTURES)
    if len(wheels) != expected_count:
        fail(f"Expected {expected_count} wheels, found {len(wheels)}")

    combinations: set[tuple[str, str]] = set()
    wheel_records = []
    wheel_dir = output_dir / "wheels"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    for wheel in wheels:
        identity = wheel_identity(wheel, version)
        if identity in combinations:
            fail(f"Duplicate wheel for Python/architecture pair: {identity}")
        combinations.add(identity)
        validate_wheel_metadata(wheel, version)
        destination = wheel_dir / wheel.name
        shutil.copy2(wheel, destination)
        wheel_records.append(
            {
                "name": wheel.name,
                "python_tag": identity[0],
                "architecture": identity[1],
                "size": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    expected = {(python, arch) for python in PYTHON_TAGS for arch in ARCHITECTURES}
    if combinations != expected:
        fail(f"Incomplete wheel matrix: expected {sorted(expected)}, got {sorted(combinations)}")

    checksum_lines = [f"{record['sha256']}  {record['name']}" for record in wheel_records]
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    manifest = {
        "package": PACKAGE_NAME,
        "version": version,
        "source_ref": source_ref,
        "source_sha": source_sha,
        "builds": build_metadata,
        "wheels": wheel_records,
    }
    (output_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    notes = [
        "# ascend-catlass-dsl wheels",
        "",
        f"- Package version: {version}",
        f"- CATLASS ref: {source_ref}",
        f"- CATLASS commit: {source_sha}",
        "- Python: 3.10, 3.11, 3.12, 3.13",
        "- Architectures: x86_64, aarch64",
        "",
        "## AscendNPU-IR by architecture",
        "",
    ]
    for path in note_paths:
        notes.append(path.read_text(encoding="utf-8").rstrip())
        notes.append("")
    notes.extend(["## SHA256", "", "```", *checksum_lines, "```", ""])
    (output_dir / "release-notes.md").write_text("\n".join(notes), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-ref", required=True)
    args = parser.parse_args()
    try:
        prepare(
            args.input_dir,
            args.output_dir,
            args.version,
            args.source_sha,
            args.source_ref,
        )
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
