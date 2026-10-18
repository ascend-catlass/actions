# Rebuild the DSL environment without a CANN image

[中文](../zh/dsl-environment.md)

The experimental recipe separates the operating system and Python packages from
CANN and NPUIR. It does not clone or compile LLVM/NPUIR inside Docker. Use the
CANN installation workflow and the current NPUIR preparation workflow to provision
those dependencies once, then bind-mount the exact version directories read-only.

This is an opt-in experiment. It does not change the image or scheduling used by
the production PR, wheel, release or community workflows. The historical NPUIR
20260720 workflow remains unchanged.

## Measured baseline

Measurements on an Ubuntu 24.04 x86_64 Ascend 950PR worker on 2026-10-19:

| Item | Result |
| --- | --- |
| CATLASS revision | `dd8b8b4c0611af965fb57df9818d3b819db67489` |
| NPUIR revision | `693abf31f3d88d13d30d9578fcf6513b90c0ee33` |
| CANN | `9.3.0~weekly.20261014.01`, build `20261014093543763` |
| Python / compiler | Python 3.12; Ubuntu clang 19.1.1; cached NPUIR built with clang/lld 19.1.7 |
| PyTorch / TorchNPU | `2.9.0+cpu` / `2.9.0.post9` |
| Host Python environment, cold downloads | 458 seconds, excluding source transfer |
| Host editable DSL build | 19 seconds, 32 build jobs |
| Host IR tests | 2725 passed, 19 skipped; 31.20 seconds |
| Host Lit tests | 191 passed; 3.11 seconds for tests, excluding build |
| Host Release wheel and NPU battery | 304 passed; 96.26 seconds for tests, 130 seconds including wheel build/install |
| Thin image cold build | 434 seconds, including dependency downloads and image export |
| Thin image size | 3.1 GB reported by `docker image ls` after export and unpack completed |
| Container editable DSL build | 21 seconds |
| Container IR / Lit tests | 2739 passed, 5 skipped / 191 passed |
| Container Release wheel and NPU battery | 304 passed; 115.58 seconds for tests, 171 seconds including wheel build/install |

The NPUIR install tree alone occupies 4.7 GiB and remains outside the image.
Network download time dominates environment preparation; these times do not
include provisioning CANN or building a missing NPUIR archive. Repeated image
builds reuse Docker layers. This recipe is currently validated only on x86_64;
it does not replace the manylinux wheel publication job.

The first host IR run preceded the TorchNPU installation; 14 additional optional
tests ran in the fully provisioned container. CANN occupies approximately 15 GiB
on the host and is also excluded from the image.

## Host virtual environment

Install binary system packages first, using the host administrator's package
policy. The Ubuntu 24.04 package set is:

```bash
sudo apt-get install --no-install-recommends \
  ca-certificates clang-19 lld-19 git build-essential python3-dev \
  python3-venv zlib1g-dev libxml2-dev
bash scripts/dsl-env/prepare-python.sh /path/to/catlass /path/to/new-venv
```

The helper refuses to overwrite an existing environment and records the resolved
Python packages in `requirements-resolved.txt`. CPU-only PyTorch is installed
before TorchNPU so the resolver does not download CUDA dependencies. Build tools
and CANN Python dependencies come from the checked-out CATLASS manifests.

Run upstream build/test commands through the environment wrapper:

```bash
SOURCE=/path/to/catlass
VENV=/path/to/new-venv
CANN=/opt/cann_weekly/20261014/cann-9.3.0
NPUIR=/opt/AscendNPU-IR/20261013/AscendNPU-IR
bash scripts/dsl-env/run.sh "$SOURCE" "$VENV" "$CANN" "$NPUIR" -- \
  bash -c 'cd python/tla_dsl && bash build.sh && python -m pytest -q tests -p no:randomly && cmake --build csrc/mlir/build --target check-tla-lit'
```

`run.sh` checks the NPUIR source SHA against the CATLASS gitlink, the host
architecture and the archive build contract before executing the command. For a
source archive without Git metadata, set `CATLASS_DSL_EXPECTED_NPUIR_SHA` from the
trusted source revision. The wrapper also selects the virtual environment's Lit:
the cached `llvm-lit` script may reference a Python interpreter that only exists
inside its producer container.

For NPU validation, select an idle device, provide an isolated writable `TMPDIR`
and `CATLASS_DSL_CACHE_DIR`, and run `bash tests/run_dsl_test.sh --device ID` through
the same wrapper. That upstream entry builds and tests the Release wheel.
When running individual examples instead, initialize bitcode first with
`python -m catlass.bc_compile` in the same Python environment and cache.

## Thin container

```bash
bash scripts/dsl-env/build-image.sh /path/to/catlass catlass-dsl-light:ubuntu24-py312
bash scripts/dsl-env/run-container.sh /path/to/separate-catlass-worktree \
  catlass-dsl-light:ubuntu24-py312 "$CANN" "$NPUIR" -- \
  bash -c 'cd python/tla_dsl && bash build.sh && python -m pytest -q tests -p no:randomly && cmake --build csrc/mlir/build --target check-tla-lit'
```

`BASE_IMAGE` can select a trusted mirror or a pinned Ubuntu 24.04 digest. The
measured experiment used `docker.m.daocloud.io/library/ubuntu:24.04`. No CANN,
NPUIR, repository history or full source checkout enters the build context:
only the Dockerfile and the two Python dependency manifests are copied.

At runtime, mount a separate CATLASS worktree read-write, CANN and NPUIR read-only
at their original absolute paths, and the installed Ascend driver paths read-only.
Provide device access as required by the runner's existing Ascend container
policy. The experiment's `run-container.sh` follows the existing privileged Ascend
container policy, mounts `run.sh` read-only, and invokes it with `/opt/dsl-venv` as
the Python environment. Only use it for source code trusted to run on the worker.
The container runs the same upstream
build, IR, Lit and NPU test commands as the host environment.
The wrapper resolves the real CANN installation behind `ascend-toolkit/set_env.sh`
so a directory containing sibling symlinks does not become an incomplete mount.

Use separate source/build directories for host and container experiments: CMake
caches contain absolute paths. A Linux checkout must use LF line endings;
Windows-exported CRLF shell and Lit fixture files can fail before testing the
environment. Pin a tested base digest and resolved Python requirements before
adopting the recipe as the production baseline.
