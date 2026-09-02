# ascend-catlass/actions

Shared GitHub Actions automation for the `ascend-catlass` organization.

The workflows in `.github/workflows/` run from this repository's `main` branch:

- `sync-gitcode.yml` mirrors GitCode `master` and tags to
  `ascend-catlass/catlass` every day or on manual dispatch.
- `test-gitcode-pr.yml` manually validates a GitCode pull request on the
  `ascend950` runner.

Composite actions and their scripts live under `.github/actions/`. The
workflows require the `GITCODE_TOKEN` and `CATLASS_DEPLOY_KEY` repository
secrets.
