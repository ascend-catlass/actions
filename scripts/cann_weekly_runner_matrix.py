"""Schedule every managed weekly CANN host, or one explicitly selected host."""
import json
import os

from dependency_runner_matrix import select_matrix

HOSTS = (
    ("179-223-2-2", "x86_64"),
    ("179-228-2-2", "x86_64"),
    ("179-182-2-2", "aarch64"),
    ("179-162-5-2", "aarch64"),
    ("179-176-2-2", "aarch64"),
    ("179-178-1-2", "aarch64"),
    ("179-182-2-3", "aarch64"),
    ("179-182-2-4", "aarch64"),
    ("179-184-3-2", "aarch64"),
    ("179-183-2-2", "aarch64"),
    ("179-167-4-2", "aarch64"),
)


def select_weekly_matrix(runner_label="", target_arch="x86_64"):
    if runner_label:
        matrix = select_matrix(runner_label, target_arch, "bz")
        matrix["include"][0]["host_id"] = runner_label
        for host, cpu in HOSTS:
            if runner_label == "host-" + host:
                if target_arch != cpu:
                    raise ValueError("target_arch does not match the managed host")
                if cpu == "aarch64":
                    matrix["include"][0].update(transport="ssh", ssh_host=host.replace("-", "."),
                                                runs_on=["self-hosted", "Linux", "bz", "X64"])
                else:
                    matrix["include"][0]["transport"] = "local"
                break
        return matrix
    rows = []
    for host, cpu in HOSTS:
        label = "host-" + host
        row = select_matrix(label, cpu, "bz")["include"][0]
        row["host_id"] = label
        if cpu == "aarch64":
            row["transport"] = "ssh"
            row["ssh_host"] = host.replace("-", ".")
            row["runs_on"] = ["self-hosted", "Linux", "bz", "X64"]
        else:
            row["transport"] = "local"
        rows.append(row)
    return {"include": rows}


if __name__ == "__main__":
    matrix = select_weekly_matrix(
        os.environ.get("TARGET_RUNNER_LABEL", ""),
        os.environ.get("TARGET_ARCH", "x86_64"),
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("matrix=" + json.dumps(matrix, separators=(",", ":")) + "\n")
