#!/usr/bin/python3
"""Forced SSH command: accept only a validated weekly CANN installation request."""
import os
import re
import shlex
import sys


def install_arguments(command):
    args = shlex.split(command)
    if len(args) != 4 or args[0] != "install-weekly":
        raise ValueError("Only install-weekly BUILD VERSION ARCH is permitted")
    build, version, arch = args[1:]
    match = re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+~weekly\.([0-9]{8})\.[0-9]+", version)
    if not re.fullmatch(r"[0-9]{17}", build) or not match or match[1] != build[:8]:
        raise ValueError("Invalid weekly build or version")
    if arch not in {"aarch64", "x86_64"}:
        raise ValueError("Invalid CPU architecture")
    return [build, version, arch]


if __name__ == "__main__":
    try:
        args = install_arguments(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
    os.execv("/usr/bin/sudo", ["sudo", "-n", "/usr/bin/bash",
             "/usr/local/libexec/cann-weekly/install.sh", *args])
