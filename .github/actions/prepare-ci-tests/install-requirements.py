"""Install CPU Torch 2.9 and matching Torch NPU before other test requirements."""

from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

PYPI_MIRROR = "https://mirror.nju.edu.cn/pypi/web/simple"


def torch_wheel_url():
    arch = platform.machine().lower()
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)
    if (
        sys.platform != "linux"
        or sys.implementation.name != "cpython"
        or sys.version_info[:2] not in ((3, 10), (3, 11), (3, 12))
        or arch not in ("x86_64", "aarch64")
    ):
        raise RuntimeError("Torch 2.9 CI requires Linux CPython 3.10-3.12 on x86_64/aarch64")
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    return (
        "https://mirror.nju.edu.cn/pytorch/whl/cpu/"
        f"torch-2.9.0%2Bcpu-{tag}-{tag}-manylinux_2_28_{arch}.whl"
    )


def main():
    wheel_url = torch_wheel_url()
    worktree = Path(sys.argv[1]).resolve()
    requirements = worktree / "requirements.txt"
    torch_package = re.compile(r"^torch[a-z0-9._-]*(?=\s|\[|[<>=!~@;]|$)", re.I)
    retained = []
    for line in requirements.read_text().splitlines(keepends=True):
        if torch_package.match(line.lstrip()):
            print("Skipping Torch requirement; CI installs a pinned CPU version", flush=True)
        else:
            retained.append(line)

    # Keep relative requirement paths relative to the original requirements.txt.
    pip = [sys.executable, "-m", "pip"]
    with tempfile.TemporaryDirectory(prefix="catlass-torch-") as download_dir, tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix=".ci-requirements-", dir=worktree
    ) as filtered:
        filtered.writelines(retained)
        filtered.flush()
        constraints = Path(download_dir) / "constraints.txt"
        constraints.write_text("torch==2.9.0+cpu\ntorch-npu==2.9.0\n")

        def run(*args):
            subprocess.run([*pip, *args], cwd=worktree, check=True)

        # Resolve/download both matching wheels before removing the installed pair.
        print(f"Installing CPU Torch from {wheel_url}", flush=True)
        run("download", "--no-deps", "--only-binary=:all:",
            "--index-url", PYPI_MIRROR, "--dest", download_dir,
            wheel_url, "torch-npu==2.9.0")
        wheels = sorted(str(path) for path in Path(download_dir).glob("*.whl"))
        if len(wheels) != 2:
            raise RuntimeError("Expected exactly one Torch and one Torch NPU wheel")
        run("uninstall", "-y", "torch", "torch-npu")
        run("install", "--index-url", PYPI_MIRROR, "-c", str(constraints), *wheels)
        run("install", "--index-url", PYPI_MIRROR,
            "-c", str(constraints), "-r", filtered.name)
        subprocess.run(
            [sys.executable, "-c", "import torch; from importlib.metadata import version; "
             "assert torch.__version__ == '2.9.0+cpu', torch.__version__; "
             "assert torch.version.cuda is None, torch.version.cuda; "
             "assert version('torch-npu') == '2.9.0', version('torch-npu'); "
             "print('Verified torch=2.9.0+cpu, torch-npu=2.9.0, CUDA=None')"],
            cwd=worktree, check=True,
        )


if __name__ == "__main__":
    main()
