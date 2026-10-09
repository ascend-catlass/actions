"""Install root test requirements while leaving Torch packages to the image."""

from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    worktree = Path(sys.argv[1]).resolve()
    requirements = worktree / "requirements.txt"
    torch_package = re.compile(r"^torch[a-z0-9._-]*(?=\s|\[|[<>=!~@;]|$)", re.I)
    retained = []
    for line in requirements.read_text().splitlines(keepends=True):
        if torch_package.match(line.lstrip()):
            print("Skipping image-provided Torch requirement", flush=True)
        else:
            retained.append(line)

    # Keep relative requirement paths relative to the original requirements.txt.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix=".ci-requirements-", dir=worktree
    ) as filtered:
        filtered.writelines(retained)
        filtered.flush()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", filtered.name],
            cwd=worktree,
            check=True,
        )


if __name__ == "__main__":
    main()
