# Install the official TRAE CN CLI

[中文](../../zh/actions/setup-trae-cn.md) · [English](../../en/actions/setup-trae-cn.md)

## What it does

Installs official China enterprise CLI 0.209.1, verifies both release SHA256 checksums and adds it to PATH. It does not log in, analyze source or publish comments.

## When to use it

Shared by Issue analysis, manual fixes, PR review and CI failure diagnosis, before the existing trae-cn Action. Requires Linux x64, Bash, curl, gzip and sha256sum. Missing bubblewrap is installed through apt with sudo.

## Example

```yaml
- uses: ascend-catlass/actions/.github/actions/setup-trae-cn@main
```

## Inputs

None. Version and checksums are maintained centrally.

## Outputs

No named outputs. Subsequent steps can execute `traecli`; model authentication remains a separate Secret input to trae-cn.
