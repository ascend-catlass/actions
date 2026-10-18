"""Select existing dependency-worker defaults or one explicitly labelled host."""
import json
import os
import re


def select_matrix(runner_label, target_arch, default_label):
    if target_arch not in {"x86_64", "aarch64"}:
        raise ValueError("target_arch must be x86_64 or aarch64")
    if runner_label and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", runner_label):
        raise ValueError("runner_label must be a single runner label")
    rows = []
    for cpu, arch in [("x86_64", "X64"), ("aarch64", "ARM64")]:
        if runner_label and cpu != target_arch:
            continue
        rows.append({
            "cpu": cpu,
            "target_arch": cpu,
            "runner_arch": arch,
            "container_image": f"quay.io/pypa/manylinux_2_28_{cpu}",
            "use_all_cores": cpu == "aarch64",
            "runs_on": ["self-hosted", "Linux", runner_label or default_label, arch],
        })
    return {"include": rows}


if __name__ == "__main__":
    matrix = select_matrix(
        os.environ.get("TARGET_RUNNER_LABEL", ""),
        os.environ.get("TARGET_ARCH", "x86_64"),
        os.environ["DEFAULT_RUNNER_LABEL"],
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("matrix=" + json.dumps(matrix, separators=(",", ":")) + "\n")
