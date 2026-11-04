"""Validate manual wheel selections and generate the reusable build matrix."""
import argparse
import json
import os
from pathlib import Path
import re

PYTHONS = ("3.10", "3.11", "3.12", "3.13")
ARCHES = {"x86_64": "X64", "aarch64": "ARM64"}


def validate_pr(value):
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        raise ValueError("pr_number must be a positive PR number")
    return value


def checkbox(value):
    if value not in {"true", "false"}:
        raise ValueError("Checkbox values must be true or false")
    return value == "true"


def dispatch_selection(env):
    pr = env.get("PR_NUMBER", "")
    if pr:
        validate_pr(pr)
    versions = [v for v in PYTHONS if checkbox(env["PYTHON_" + v.replace(".", "")])]
    arches = [a for a in ARCHES if checkbox(env["ARCH_" + a.upper()])]
    if not versions or not arches:
        raise ValueError("Select at least one Python version and one CPU architecture")
    return {"pr_number": pr, "python_versions": json.dumps(versions),
            "matrix": json.dumps({"include": [{"target_arch": a} for a in arches]})}


def build_selection(versions_json, target_arch):
    versions = json.loads(versions_json)
    if (not isinstance(versions, list) or not versions
            or any(not isinstance(v, str) or v not in PYTHONS for v in versions)
            or len(set(versions)) != len(versions)):
        raise ValueError("python_versions must be a nonempty unique list of supported versions")
    if target_arch and target_arch not in ARCHES:
        raise ValueError("target_arch must be x86_64, aarch64, or empty for both")
    arches = [target_arch] if target_arch else list(ARCHES)
    return {"cibw_build": " ".join("cp" + v.replace(".", "") + "-*" for v in versions),
            "python_versions": json.dumps(versions),
            "build_matrix": json.dumps({"include": [
                {"target_arch": a, "runner_arch": ARCHES[a]} for a in arches]})}


def verify_wheels(paths, versions_json):
    selection = build_selection(versions_json, "")
    expected = {"cp" + v.replace(".", "") for v in json.loads(selection["python_versions"])}
    found = []
    for path in paths:
        fields = Path(path).name.removesuffix(".whl").split("-")
        if len(fields) not in {5, 6} or not path.endswith(".whl"):
            raise ValueError("Invalid wheel filename: " + path)
        found.append(fields[-3])
    if set(found) != expected or len(found) != len(expected):
        raise ValueError(f"Expected one wheel per selected Python: {sorted(expected)}; got {sorted(found)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["dispatch", "build", "verify"])
    parser.add_argument("wheels", nargs="*")
    args = parser.parse_args()
    versions = os.environ.get("PYTHON_VERSIONS", json.dumps(PYTHONS))
    try:
        if args.mode == "verify":
            verify_wheels(args.wheels, versions)
            return
        result = (dispatch_selection(os.environ) if args.mode == "dispatch" else
                  build_selection(versions, os.environ.get("TARGET_ARCH", "")))
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key, value in result.items():
                output.write(f"{key}={value}\n")
    except (ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
