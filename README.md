# ascend-catlass/actions

Shared GitHub Actions automation for the `ascend-catlass` organization.

The workflows in `.github/workflows/` run from this repository's `main` branch:

- `sync-gitcode.yml` mirrors GitCode `master` and tags to
  `ascend-catlass/catlass` every day or on manual dispatch.
- `test-gitcode-pr.yml` manually validates a GitCode pull request on the
  `ascend950` runner.
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
