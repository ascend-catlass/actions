# Prepare and validate CATLASS wheel bundles

[中文](../../zh/actions/prepare-wheel-bundle.md) · [English](../../en/actions/prepare-wheel-bundle.md)

## What it does

Validates eight `ascend-catlass` wheels (Python 3.10–3.13, x86_64 and aarch64), records checksums and source provenance, and optionally builds one stable `ascend-catlass-dsl` compatibility wheel. The compatibility wheel contains metadata only and requires exactly the same version of `ascend-catlass`.

## Example

Run after downloading the two architecture artifacts into `wheels/`:

```yaml
- uses: ascend-catlass/actions/.github/actions/prepare-wheel-bundle@main
  with:
    version: ${{ needs.preflight.outputs.version }}
    source-sha: ${{ needs.preflight.outputs.source_sha }}
    source-ref: ${{ needs.preflight.outputs.tag }}
    compatibility-package: 'true'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `operation` | No | `prepare` | prepare, validate, or validate-pypi (also check existing PyPI files) |
| `version` | Yes | — | Exact package version from the source resolution stage |
| `source-sha` | Yes | — | Exact CATLASS commit from the source resolution stage |
| `source-ref` | Yes | — | CATLASS source ref (master or the exact stable tag) |
| `input-dir` | No | `wheels` | Downloaded architecture wheel artifact directory |
| `bundle` | No | `release-bundle` | Output bundle for prepare, or existing bundle for validation |
| `compatibility-package` | No | `false` | Build or require the stable PyPI-only ascend-catlass-dsl compatibility wheel |

## Outputs

No Action output fields are defined. The prepared bundle contains `wheels/`, `SHA256SUMS`, `release-manifest.json` and release notes. Stable preparation additionally creates `compat-wheels/` and `compat-SHA256SUMS`. Compatibility files are for PyPI only and are excluded from the AtomGit assets.

## Validation and retries

Preparation installs the pinned tools from `requirements-release.txt` and runs `twine check`. Validation uses only the Python standard library and never rebuilds the compatibility wheel. A downloaded bundle must match the expected package name, version, source ref, commit, wheel matrix, metadata and hashes. Release publication requires the compatibility package; older bundles without it must be rebuilt.

`validate-pypi` also rejects conflicting files already published for either project/version, including a historical native legacy package. Partial retries accept only matching filenames and hashes. Publishers run only after validation succeeds. This Action does not upload distributions.
