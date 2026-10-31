"""Exercise the workflow checkout against mirrors that advertise no refs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-ascendnpu-ir-20261013.yml"


@unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "git and bash required")
class PinnedSubmoduleTests(unittest.TestCase):
    def test_fetches_exact_gitlinks_from_mirrors_without_visible_refs(self):
        env = dict(os.environ, GIT_ALLOW_PROTOCOL="file", GIT_AUTHOR_NAME="Test",
                   GIT_AUTHOR_EMAIL="test@example.invalid", GIT_COMMITTER_NAME="Test",
                   GIT_COMMITTER_EMAIL="test@example.invalid")
        with tempfile.TemporaryDirectory(prefix="npuir pinned ") as temp:
            base = Path(temp)
            work = base / "work tree"
            work.mkdir()

            def git(*args, cwd=None):
                return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                                      text=True, capture_output=True).stdout.strip()

            git("init", "-q", str(work))
            pins = {}
            modules = []
            for name in ["llvm-project", "torch-mlir"]:
                remote = base / (name + ".git")
                source = base / (name + " source")
                git("init", "--bare", "-q", str(remote))
                git("init", "-q", str(source))
                (source / "content").write_text("pinned")
                if name == "torch-mlir":
                    # A recursive checkout would try an unavailable, unused remote.
                    nested = "externals/llvm-project"
                    (source / ".gitmodules").write_text(
                        f'[submodule "{nested}"]\n path = {nested}\n'
                        f' url = {(base / "unavailable-nested.git").as_uri()}\n')
                    git("add", ".gitmodules", cwd=source)
                    git("update-index", "--add", "--cacheinfo",
                        "160000," + pins["third-party/llvm-project"] + "," + nested, cwd=source)
                git("add", "content", cwd=source)
                git("commit", "-qm", "pinned", cwd=source)
                pin = git("rev-parse", "HEAD", cwd=source)
                (source / "content").write_text("newer")
                git("add", "content", cwd=source)
                git("commit", "-qm", "newer", cwd=source)
                git("push", "-q", remote.as_uri(), "HEAD:refs/heads/hidden", cwd=source)
                git("config", "uploadpack.hideRefs", "refs/heads", cwd=remote)
                git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=remote)
                git("symbolic-ref", "HEAD", "refs/heads/unborn", cwd=remote)
                self.assertEqual(git("ls-remote", remote.as_uri()), "")
                path = "third-party/" + name
                modules.append(f'[submodule "{path}"]\n path = {path}\n url = {remote.as_uri()}\n')
                git("update-index", "--add", "--cacheinfo", "160000," + pin + "," + path, cwd=work)
                pins[path] = pin
            (work / ".gitmodules").write_text("".join(modules))
            git("add", ".gitmodules", cwd=work)
            git("commit", "-qm", "pin dependencies", cwd=work)

            lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
            start = next(i for i, line in enumerate(lines)
                         if line.strip() == "for submodule in third-party/llvm-project third-party/torch-mlir; do")
            end = next(i for i in range(start + 1, len(lines)) if lines[i] == "          done")
            script = "set -euo pipefail\n" + "\n".join(line[10:] for line in lines[start:end + 1])
            result = subprocess.run(["bash", "-c", script], env=dict(env, WORK_PATH=str(work)),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            update = next(line.strip() for line in lines
                          if 'git -C "${WORK_PATH}" submodule update' in line)
            result = subprocess.run(["bash", "-c", "set -euo pipefail\n" + update],
                                    env=dict(env, WORK_PATH=str(work)), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((work / "third-party/torch-mlir/externals/llvm-project/.git").exists())
            for path, pin in pins.items():
                self.assertEqual(git("rev-parse", "HEAD", cwd=work / path), pin)
                self.assertEqual((work / path / "content").read_text(), "pinned")
                self.assertFalse((work / path / ".git").is_dir())


if __name__ == "__main__":
    unittest.main()
