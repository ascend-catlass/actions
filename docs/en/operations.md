# Build and runner operations

[���Ĺ�����](../zh/workflows.md) �� [English workflows](workflows.md)

- `install-cann-weekly.yml` scans the official CANN `software/master/` mirror
  daily at 02:00 Asia/Shanghai (18:00 UTC), or on manual dispatch. One pinned
  build and version are used by all 11 managed hosts: the two X64 hosts
  `179.223.2.2` and `179.228.2.2`, plus nine ARM64 hosts. Each job identifies one host with
  `host-<IP-with-hyphens>`. The two online X64 `bz` runners install locally or
  use SSH to install on the nine ARM64 hosts, which do not need GitHub access.
  Manual `runner_label` and `target_arch` inputs select one managed host, or
  an existing runner for a local installation. Managed host architecture must match.
  Each executor has its own `~/.ssh/cann_weekly_dispatch` key and pinned
  `~/.ssh/cann_weekly_known_hosts`. Dedicated `~/.ssh/cann_weekly_ssh_config`
  routes isolated targets through `179.182.2.2` and their data-network addresses,
  retaining the management IP as `HostKeyAlias`. The jump key permits only
  TCP forwarding to the listed target SSH ports; target keys use `restrict` and
  the root-owned `/usr/local/libexec/cann-weekly/ssh-entry.py` forced command.
  It accepts only validated `install-weekly BUILD VERSION ARCH` requests and
  invokes the deployed root-owned installer. No GitHub token is sent to targets.
  These infrastructure files must be provisioned before the first dispatch. The worker detects its actual CPU and NPU chip family
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
  `/opt` links to `/home/opt`; the installer requires the real installation
  root to be `/home/opt/cann_weekly` on the separately mounted LVM `/home`.
  Packages and extraction files also stay on that filesystem. Installation
  arguments and the `latest` link retain the `/opt/cann_weekly` path.
  Conflicting builds on the same date and unknown PCI IDs fail explicitly. One host's failure
  does not cancel the other hosts; log artifacts have unique host names. Installation logs are kept as
  workflow artifacts for 30 days. Historical installations and downloaded
  packages are retained locally. See the
  [design and operational limits](https://github.com/ascend-catlass/actions/blob/main/docs/plans/2026-10-13-cann-weekly-design.md).
  Select a completed version by sourcing its actual environment script, e.g.
  `/opt/cann_weekly/20261009/cann/set_env.sh` for the current package layout;
  the installer also accepts `ascend-toolkit/set_env.sh` layouts.
- `sync-atomgit.yml` mirrors AtomGit `master` and tags to
  `ascend-catlass/catlass` every day or on manual dispatch.
- `test-atomgit-pr.yml` manually validates an AtomGit pull request on the
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
  Selection follows AtomGit pre_smoke: unrelated paths do not force a full
  suite, and the unsupported tuner group is skipped on Ascend 950. Only
  explicitly shared build/test dependencies require the full 3510 suite. See the
  [selection rules and limits](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md).
  PR testing uses the CANN 9.2.0 beta.2 image.
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
  derived nightly version or an exact stable version paired with its AtomGit
  `vMAJOR.MINOR.PATCH` tag.
  Manual, nightly and release wheel builds require no host CANN installation.
  They use the `20261013` NPUIR preparation workflow/archive baseline.
  The legacy `ASCEND_HOME_PATH` is defined as empty only to satisfy upstream
  CMake; CANN-dependent bitcode compilation happens at runtime. NPUIR source revisions still follow the selected
  CATLASS commit's exact gitlink, including builds of older release tags.
- `nightly-dsl-wheel.yml` runs the build workflow every day at 01:00
  Asia/Shanghai and publishes the validated wheels to the GitHub Release-backed
  package index.
- `release-dsl-wheel.yml` verifies that an exact AtomGit tag exists before it
  starts a build, then publishes the same validated wheels to PyPI and the
  corresponding AtomGit Release.

Composite actions and their scripts live under `.github/actions/`.
The
[`community-repo-roles`](https://github.com/ascend-catlass/actions/blob/main/.github/actions/community-repo-roles/README.md) action
reads an existing CANN community checkout to return a repository's maintainer
and declared committer IDs, personnel details, SIGs, and scoped configurations.
It requires no AtomGit token.

The workflows prefer `ATOMGIT_TOKEN` and fall back to the existing `GITCODE_TOKEN`
when it is empty. The selected token must have Release write access for stable
releases. The existing `gitcode-release` environment and `CATLASS_DEPLOY_KEY`
configuration remain in use. PyPI publishing also requires a Trusted Publisher bound to the `pypi`
environment and `release-dsl-wheel.yml`.

The DSL build pool consists of machines 124 and 125. Assign the custom
`ascend-catlass-dsl-build` label only to their host runners, keeping the default
`self-hosted`, `Linux` and native `X64`/`ARM64` labels. Both
`build-dsl-wheel.yml` and `build-ascendnpu-ir-20261013.yml` select this pool by
label and architecture, so dependency preparation and wheel compilation use the
same worker-local archives. Keep one eligible host per architecture; adding
more requires shared archives or explicit worker affinity. Verify both runners
are online and have Git, patch, Docker, Python >= 3.11 and archive access before merging the
routing change. Nightly and release builds inherit this selection. The
historical NPUIR 20260720 workflow and AtomGit publishing retain `publish`.
Build workers use the latest Git release to fetch sources and submodules.

NPUIR builds on each worker share complete source/build/install trees at
`/opt/AscendNPU-IR/<YYYYMMDD>/AscendNPU-IR`. The date is the workflow's
`NPUIR_BASELINE_DATE` (currently `20260720` or `20261013`), not the run date.
The archive action provisions the root with passwordless `sudo` when necessary;
the runner account must have write access to it. Published trees grant all local
users read and directory traversal access, preserving executable bits.
Each worker stores its native CPU architecture; dates cannot be reused for a
different commit, architecture, or build contract.

`/opt/AscendNPU-IR/latest` points to the completed
`<YYYYMMDD>` directory, matching the dated directory layout. Publication and cache reuse create this link if
missing and advance it only for a strictly newer date. A worker-local file lock
serializes the date comparison and atomic symlink replacement. Failed builds
remain under `.building-*` for inspection and never become `latest`.
Validated archives from the previous runner-local `_npuir-pipeline` directory
are copied into the shared layout when requested; originals remain available
to existing consumers. Wheel builds continue selecting the exact dated archive
and validating its gitlink and build contract.

Local users can select the default installation with:

```bash
export CATLASS_DSL_PREBUILT_ASCENDNPU_IR=/opt/AscendNPU-IR/latest/AscendNPU-IR
export CATLASS_DSL_ASCENDNPU_IR_ROOT=/opt/AscendNPU-IR/latest/AscendNPU-IR
export CATLASS_DSL_ASCENDNPU_IR_INSTALL_DIR=/opt/AscendNPU-IR/latest/AscendNPU-IR/build/install
export PATH=/opt/AscendNPU-IR/latest/AscendNPU-IR/build/install/bin:$PATH
```

Host PR runners require Docker and the local image
`ascend-catlass-dsl:9.2.0-beta.2-950-ubuntu22.04-py3.12`. The reusable
[`create-ascend-container`](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/README.md)
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
[`detect_npu.sh`](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/detect_npu.sh) from
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
