"""Revalidate CATLASS bundle identity and contents before any publication."""
from __future__ import annotations

import argparse
import email.parser
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
import zipfile

from scripts.prepare_wheel_bundle import (
    ARCHITECTURES, PACKAGE_NAME, PYTHON_TAGS, sha256, validate_wheel_metadata, wheel_identity,
)


def python_spec(value: str) -> list[str]:
    return sorted(value.replace(" ", "").split(","))


def validate_records(folder: Path, records: list, checksum_file: Path) -> list[Path]:
    files = sorted(folder.iterdir()) if folder.is_dir() else []
    if (not records or any(not p.is_file() or p.is_symlink() or p.suffix != ".whl" for p in files)
            or sorted(record["name"] for record in records) != [p.name for p in files]):
        raise ValueError(f"Wheel inventory differs from manifest: {folder.name}")
    checksums = []
    for record in sorted(records, key=lambda value: value["name"]):
        path = folder / record["name"]
        digest = sha256(path)
        if record["sha256"] != digest or record["size"] != path.stat().st_size:
            raise ValueError(f"Wheel checksum or size mismatch: {path.name}")
        checksums.append(f"{digest}  {path.name}\n")
    if checksum_file.read_text(encoding="utf-8") != "".join(checksums):
        raise ValueError(f"Checksum file differs from manifest: {checksum_file.name}")
    return files


def validate_compat(path: Path, version: str, requires_python: str) -> None:
    prefix = f"ascend_catlass_dsl-{version}.dist-info/"
    if path.name != f"ascend_catlass_dsl-{version}-py3-none-any.whl":
        raise ValueError("Unexpected compatibility wheel filename")
    with zipfile.ZipFile(path) as archive:
        allowed = {prefix + name for name in ("METADATA", "WHEEL", "RECORD", "top_level.txt")}
        if (not set(archive.namelist()) <= allowed
                or len(set(archive.namelist())) != len(archive.namelist())):
            raise ValueError("Compatibility wheel must contain only distribution metadata")
        parser = email.parser.BytesParser()
        metadata = parser.parsebytes(archive.read(prefix + "METADATA"), headersonly=True)
        wheel = parser.parsebytes(archive.read(prefix + "WHEEL"), headersonly=True)
        dependencies = [re.sub(r"[\s()]", "", value)
                        for value in metadata.get_all("Requires-Dist", [])]
        if (metadata["Name"] != "ascend-catlass-dsl" or metadata["Version"] != version
                or dependencies != [f"{PACKAGE_NAME}=={version}"]
                or python_spec(metadata["Requires-Python"] or "") != python_spec(requires_python)
                or wheel.get_all("Tag") != ["py3-none-any"]
                or wheel["Root-Is-Purelib"] != "true"):
            raise ValueError("Compatibility package identity, dependency or Python range mismatch")
        if prefix + "top_level.txt" in archive.namelist():
            if archive.read(prefix + "top_level.txt").strip():
                raise ValueError("Compatibility package must not export import packages")


def validate(bundle: Path, version: str, source_sha: str, source_ref: str,
             require_compat: bool = False) -> dict:
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    expected = {"package": PACKAGE_NAME, "version": version,
                "source_sha": source_sha, "source_ref": source_ref}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Release bundle package/version/source identity mismatch; rebuild the bundle")
    files = validate_records(bundle / "wheels", manifest["wheels"], bundle / "SHA256SUMS")
    combinations = [wheel_identity(path, version) for path in files]
    matrix = {(python, arch) for python in PYTHON_TAGS for arch in ARCHITECTURES}
    if len(combinations) != len(matrix) or set(combinations) != matrix:
        raise ValueError("Release bundle must contain the complete eight-wheel matrix")
    requires_python = None
    for path in files:
        metadata = validate_wheel_metadata(path, version)
        if requires_python is None:
            requires_python = metadata["Requires-Python"]
        elif python_spec(metadata["Requires-Python"]) != python_spec(requires_python):
            raise ValueError("Main wheels have inconsistent Python requirements")
    for record, identity in zip(sorted(manifest["wheels"], key=lambda r: r["name"]), combinations):
        if (record["python_tag"], record["architecture"]) != identity:
            raise ValueError("Wheel matrix provenance differs from filename")
    builds = manifest["builds"]
    if len(builds) != len(ARCHITECTURES) or any(
        value.get("package_version") != version or value.get("source_sha") != source_sha
        for value in builds
    ):
        raise ValueError("Build provenance differs from release identity")
    build_files = [name for value in builds for name in value["wheel_files"].split(",")]
    if sorted(build_files) != [path.name for path in files]:
        raise ValueError("Build provenance differs from wheel inventory")
    compatibility = manifest.get("compatibility")
    if require_compat and not compatibility:
        raise ValueError("Release bundle has no compatibility package; rebuild with the new workflow")
    if compatibility:
        expected_compat = {"package": "ascend-catlass-dsl", "version": version,
                           "requires_dist": f"{PACKAGE_NAME}=={version}"}
        if (any(compatibility.get(key) != value for key, value in expected_compat.items())
                or python_spec(compatibility["requires_python"]) != python_spec(requires_python)
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)):
            raise ValueError("Compatibility manifest identity mismatch")
        compat_files = validate_records(bundle / "compat-wheels", compatibility["wheels"],
                                        bundle / "compat-SHA256SUMS")
        if len(compat_files) != 1:
            raise ValueError("Expected exactly one compatibility wheel")
        validate_compat(compat_files[0], version, requires_python)
    elif (bundle / "compat-wheels").exists():
        raise ValueError("Unrecorded compatibility files in release bundle")
    return manifest


def check_pypi(manifest: dict) -> None:
    """Allow partial retries only when already published files match this bundle."""
    for package in (manifest, manifest["compatibility"]):
        name, version = package["package"], package["version"]
        request = urllib.request.Request(f"https://pypi.org/pypi/{name}/{version}/json",
                                         headers={"User-Agent": "catlass-release-validation"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                remote = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        expected = {record["name"]: record["sha256"] for record in package["wheels"]}
        for record in remote["urls"]:
            if (record["filename"] not in expected
                    or record["digests"]["sha256"] != expected[record["filename"]]):
                raise ValueError(f"PyPI already contains a conflicting {name} {version} file; "
                                 "use a new release version")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--require-compat", action="store_true")
    parser.add_argument("--check-pypi", action="store_true")
    args = parser.parse_args()
    manifest = validate(args.bundle, args.version, args.source_sha, args.source_ref,
                        require_compat=args.require_compat or args.check_pypi)
    if args.check_pypi:
        check_pypi(manifest)
    print("Validated CATLASS release bundle identity, wheel metadata and checksums")


if __name__ == "__main__":
    main()
