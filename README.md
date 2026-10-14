# ascend-catlass/actions

Shared GitHub Actions automation for the `ascend-catlass` organization.

The workflows in `.github/workflows/` run from this repository's `main` branch:

- `install-cann-weekly.yml` scans the official CANN `software/master/` mirror
  daily at 02:00 Asia/Shanghai (18:00 UTC), or on manual dispatch. One pinned
  build and version are used by the two host workers selected with `self-hosted`, `Linux`,
  `bz`, and `X64`/`ARM64`. The worker detects its actual CPU and NPU chip family
  using `uname -m` and `lspci`: `d802` selects 910b, `d803` selects A3 and
  `d806` selects 950. It installs Toolkit plus matching ops into `/opt/cann_weekly/YYYYMMDD`, where
  the date comes from the mirror and package version. Root or passwordless
  `sudo` is required, along with curl, bash and pciutils.
  Driver, firmware and CANN's normal installation dependencies are prerequisites.
  Completed installations are skipped; failed managed attempts
  can be retried without overwriting a completed date. A single visible
  `installed-version.txt` records a successful installation.
  `/opt/cann_weekly/latest` points to the completed date directory and is
  refreshed after installation or when an already-installed build is reused.
  Existing host `/opt` symlinks are supported; installation arguments and the
  `latest` link retain the `/opt/cann_weekly` path.
  Conflicting builds on the same date and unknown PCI IDs fail explicitly. One worker's failure
  does not cancel the other. Installation logs are kept as
  workflow artifacts for 30 days. Historical installations and downloaded
  packages are retained locally. See the
  [design and operational limits](docs/plans/2026-10-13-cann-weekly-design.md).
  Select a completed version by sourcing its actual environment script, e.g.
  `/opt/cann_weekly/20261009/cann/set_env.sh` for the current package layout;
  the installer also accepts `ascend-toolkit/set_env.sh` layouts.
- `sync-gitcode.yml` mirrors GitCode `master` and tags to
  `ascend-catlass/catlass` every day or on manual dispatch.
- `test-gitcode-pr.yml` manually validates a GitCode pull request on the
  `ascend950` runner. It checks `/.dockerenv` before other job steps: container
  runners use their current environment; host runners create a disposable
  Ascend container and remove it after testing, including on failure or
  cancellation. PR changes are classified on a GitHub-hosted runner before
  scheduling Ascend 950 work. Documentation-only PRs finish successfully there
  and skip the Ascend 950 job entirely. Environment preparation and DSL/non-DSL
  tests run only on the Ascend 950 runner.
  Each job uses the target branch it fetches; target updates do not abort the
  run. The Ascend 950 job merges the PR into that target and fails on conflicts.
  Selective non-DSL tests use the actual pre-merge target SHA.
  Code changes under `python/tla_dsl/`, `tests/run_dsl_test.sh`, or
  `tests/dsl_battery/` trigger DSL tests; other code changes trigger non-DSL
  tests. PRs touching both groups run both suites. Other files under `tests/`
  do not trigger DSL tests.
  Non-DSL tests use the main CATLASS CI's reverse header dependency selector to
  run affected examples and trigger the corresponding test groups on Ascend 950.
  Example tests incrementally build their own targets; the action does not
  prebuild examples. The optest wheel and runtime tests use Ascend 950.
  Selection follows GitCode pre_smoke: unrelated paths do not force a full
  suite, and the unsupported tuner group is skipped on Ascend 950. Only
  explicitly shared build/test dependencies require the full 3510 suite. See the
  [selection rules and limits](.github/actions/run-ci-tests/SOURCE.md).
- Both `test-gitcode-pr.yml` and `test-gitcode-pr-cann-9-2-beta-2.yml` use the
  CANN 9.2.0 beta.2 image and the same test stages. The latter remains available
  as the version-named manual entrypoint.
  DSL changes first build in dev mode and run the upstream IR pytest suite and
  `check-tla-lit` target, sharing that build. The dev stage temporarily installs
  Lit from the package index without a version pin; the image's LLVM Lit source
  installation will replace this later.
  The existing Release wheel build and device battery run afterwards.
  Test failures do not suppress the other
  suites, and any failure still fails the job; a failed dev build skips its
  dependent suites.
- `build-dsl-wheel.yml` is the reusable, build-only x86_64/aarch64 wheel
  workflow. Its `package_version` input accepts `dev` for an automatically
  derived nightly version or an exact stable version paired with its GitCode
  `vMAJOR.MINOR.PATCH` tag.
  All manual, nightly and release wheel builds use host CANN 9.2.0 beta.2
  (`/usr/local/Ascend/cann-9.2.0-beta.2`) and the `20261013` NPUIR preparation
  workflow/archive baseline. NPUIR source revisions still follow the selected
  CATLASS commit's exact gitlink, including builds of older release tags.
- `nightly-dsl-wheel.yml` runs the build workflow every day at 01:00
  Asia/Shanghai and publishes the validated wheels to the GitHub Release-backed
  package index.
- `release-dsl-wheel.yml` verifies that an exact GitCode tag exists before it
  starts a build, then publishes the same validated wheels to PyPI and the
  corresponding GitCode Release.

Composite actions and their scripts live under `.github/actions/`. The
workflows require the `GITCODE_TOKEN` and `CATLASS_DEPLOY_KEY` repository
secrets. Stable releases use the existing `GITCODE_TOKEN`, which must have
Release write access, and require a PyPI Trusted Publisher bound to the `pypi`
environment and `release-dsl-wheel.yml`.

NPUIR builds on each publish worker share complete source/build/install trees at
`/opt/AscendNPU-IR/<YYYYMMDD>/AscendNPU-IR`. The date is the workflow's
`NPUIR_BASELINE_DATE` (currently `20260720` or `20261013`), not the run date.
The archive action provisions the root with passwordless `sudo` when necessary;
the runner account must have write access to it. Published trees grant all local
users read and directory traversal access, preserving executable bits.
Each worker stores its native CPU architecture; dates cannot be reused for a
different commit, architecture, or build contract.

`/opt/AscendNPU-IR/latest` points directly to the completed
`<YYYYMMDD>/AscendNPU-IR` tree. Publication and cache reuse create this link if
missing and advance it only for a strictly newer date. A worker-local file lock
serializes the date comparison and atomic symlink replacement. Failed builds
remain under `.building-*` for inspection and never become `latest`.
Validated archives from the previous runner-local `_npuir-pipeline` directory
are copied into the shared layout when requested; originals remain available
to existing consumers. Wheel builds continue selecting the exact dated archive
and validating its gitlink and build contract.

To migrate a previously completed cache manually, run as the CI runner account
from an updated checkout of this repository on each build worker:

Alternatively, dispatch `migrate-npuir-cache.yml` with version `20261013`
(default) or `20260720`. It migrates on both the x86_64 and aarch64 publish
workers using their existing cache location next to `RUNNER_TEMP`. A missing
matching cache fails that worker's job; the migration workflow never compiles.

```bash
bash scripts/migrate-npuir-cache.sh /path/to/runner/_work/_npuir-pipeline
```

The default migrates commit `693abf31f3d88d13d30d9578fcf6513b90c0ee33`
to version `20261013`, accepting both the old content-keyed cache and the legacy
`20260930` cache. It validates the build, copies the complete tree, fixes submodule
Git paths, preserves original build provenance, and updates `latest` under the
same lock used by CI. The original cache remains intact. Missing or conflicting
caches fail without starting a compilation. For the older version:

```bash
bash scripts/migrate-npuir-cache.sh /path/to/runner/_work/_npuir-pipeline \
  20260720 a07821269ede7a5e683ac02c8a2d291608083741 20260720
```

Local users can select the default installation with:

```bash
export CATLASS_DSL_PREBUILT_ASCENDNPU_IR=/opt/AscendNPU-IR/latest
export CATLASS_DSL_ASCENDNPU_IR_ROOT=/opt/AscendNPU-IR/latest
export CATLASS_DSL_ASCENDNPU_IR_INSTALL_DIR=/opt/AscendNPU-IR/latest/build/install
export PATH=/opt/AscendNPU-IR/latest/build/install/bin:$PATH
```

Host PR runners require Docker and the local image
`ascend-catlass-dsl:9.2.0-beta.2-950-ubuntu22.04-py3.12`. The reusable
[`create-ascend-container`](.github/actions/create-ascend-container/README.md)
action accepts the image repository, tag, container name, and source mapping
as inputs. It mounts the merged worktree at `/workspace/catlass`, passes through
the NPU using `--privileged`, and mounts the host DCMI, `npu-smi`, driver libraries,
driver version, and installation information read-only. Runtime dependencies
come from the image; the workflow does not mount over `/root` or install or
activate CANN, Conda, or AscendNPU-IR inside the container.

Torch and Torch NPU come from the image. `prepare-ci-tests` filters Lit, Torch
and Torch NPU from the root `requirements.txt` and directly installs the remaining
packages with `pip install -r`. This avoids direct installation requests for
the filtered packages; pip still resolves transitive dependencies normally.
The repository requirements file remains unchanged. The dev stage can still
install Lit when the image lacks it.
Preparation then runs the vendored
[`detect_npu.sh`](.github/actions/prepare-ci-tests/detect_npu.sh) from
MinghuasLab/flash-attention-npu inside the test environment. The upstream
selector supports 910B and 950 tables and sorts eligible cards by process count,
then card ID. Its default eligibility limits are free memory >1024 MB and
process count <4. The selected card is passed as `DEVICE_ID` to both suites and
`--device` to the DSL suite. No candidate fails preparation. Selection is a
snapshot, not an NPU reservation. The upstream source and BSD license are
recorded alongside the vendored script.

Before container tests, the action registers the mounted checkout and submodule
paths from `.gitmodules` as Git safe directories, including uninitialized
submodules such as googletest. Existing nested submodules are handled recursively.
Paths outside the checkout are rejected; repeated stages do not duplicate entries.
