#!/usr/bin/env bash
# Verify the image's build environment without a package index or cached wheels.
set -euo pipefail
probe=$(mktemp -d)
trap 'rm -rf -- "$probe"' EXIT
cat > "$probe/pyproject.toml" <<'TOML'
[build-system]
requires = ["setuptools>=68", "wheel", "cmake>=3.28,<4.0", "ninja>=1.12", "pybind11==2.13.6", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"
[project]
name = "catlass-ci-build-probe"
version = "0.0.0"
TOML
python -m pip wheel --no-deps --no-index --no-cache-dir "$probe" -w "$probe/dist"
# An incompatible source requirement must fail instead of using the wrong tool.
sed -i 's/pybind11==2.13.6/pybind11==0.0.0/' "$probe/pyproject.toml"
if python -m pip wheel --no-deps --no-index --no-cache-dir "$probe" -w "$probe/dist" > "$probe/rejected.log" 2>&1; then
    echo 'Incompatible build requirement was accepted' >&2
    exit 1
fi
grep -q 'pybind11==0.0.0' "$probe/rejected.log"
echo 'Preinstalled Python build tools passed offline and incompatible-requirement checks.'
