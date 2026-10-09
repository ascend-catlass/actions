# ascend-catlass/actions

Shared GitHub Actions automation for the `ascend-catlass` organization.

The workflows in `.github/workflows/` run from this repository's `main` branch:

- `sync-gitcode.yml` mirrors GitCode `master` and tags to
  `ascend-catlass/catlass` every day or on manual dispatch.
- `test-gitcode-pr.yml` manually validates a GitCode pull request on the
  `ascend950` runner. It checks `/.dockerenv` before other job steps: container
  runners use their current environment; host runners create a disposable
  Ascend container and remove it after testing, including on failure or
  cancellation. Documentation-only PRs skip container creation and testing.
  Code changes under `python/tla_dsl/`, `tests/run_dsl_test.sh`, or
  `tests/dsl_battery/` trigger DSL tests; other code changes trigger non-DSL
  tests. PRs touching both groups run both suites. Other files under `tests/`
  do not trigger DSL tests.
- `build-dsl-wheel.yml` is the reusable, build-only x86_64/aarch64 wheel
  workflow. Its `package_version` input accepts `dev` for an automatically
  derived nightly version or an exact stable version paired with its GitCode
  `vMAJOR.MINOR.PATCH` tag.
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

Host PR runners require Docker and the local image
`ascend-catlass-dsl:9.1.0-950-ubuntu22.04-py3.12`. The reusable
[`create-ascend-container`](.github/actions/create-ascend-container/README.md)
action accepts the image repository, tag, container name, and source mapping
as inputs. It mounts the merged worktree at `/workspace/catlass`, passes through
the NPU using `--privileged`, and mounts the host DCMI, `npu-smi`, driver libraries,
driver version, and installation information read-only. Runtime dependencies
come from the image; the workflow does not mount over `/root` or install or
activate CANN, Conda, or AscendNPU-IR inside the container.

Before either test suite, `prepare-ci-tests` installs the merged repository's
root `requirements.txt` using `python3 -m pip`, then runs the vendored
[`detect_npu.sh`](.github/actions/prepare-ci-tests/detect_npu.sh) from
MinghuasLab/flash-attention-npu inside the test environment. The upstream
selector supports 910B and 950 tables and sorts eligible cards by process count,
then card ID. Its default eligibility limits are free memory >1024 MB and
process count <4. The selected card is passed as `DEVICE_ID` to both suites and
`--device` to the DSL suite. No candidate fails preparation. Selection is a
snapshot, not an NPU reservation. The upstream source and BSD license are
recorded alongside the vendored script.
