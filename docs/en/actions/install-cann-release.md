# Install a CANN release

[中文](../../zh/actions/install-cann-release.md) · [English](../../en/actions/install-cann-release.md)

`install-cann-release` maintains host environments separately from community, build and software publication workflows.

## Behavior

`resolve` selects one version from the [official release mirror](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/) and requires Toolkit and 910b/A3/950 ops for both CPUs. Missing packages fail the run without silently falling back. `install` installs that Toolkit and the matching ops on a host under `/opt/cann/<version>`.

## Version precedence

Compare numeric major, minor and patch components, then SemVer prerelease identifiers. A final release outranks every prerelease of the same base version. Numeric prerelease identifiers compare numerically and sort below text identifiers. For example: `9.2.0-beta.2 < 9.2.0-beta.10 < 9.2.0-rc.1 < 9.2.0 < 9.2.1 < 9.10.0`. Candidates include beta/rc releases in this mirror, excluding weekly builds; a higher base version's beta can outrank a lower final release. Modification dates and listing order do not affect selection.

## Prerequisites

Hosts need root or passwordless sudo, Python 3, Bash, curl, pciutils, the usual CANN dependencies and working drivers/firmware. CPU detection uses `uname -m`; NPU detection uses `lspci -n -D | grep -o '19e5:d[0-9a-f]\{3\}' | head -n1 | cut -d: -f2`: d802=910b, d803=A3, d806=950. The first device is used, assuming one NPU family per host; unknown IDs fail. No npu-smi dependency.

## Example

```yaml
- id: release
  uses: ascend-catlass/actions/.github/actions/install-cann-release@main
  with:
    operation: resolve
```

On the host, invoke `operation: install` with the coordinator's pinned `version` and native `expected-cpu`. The workflow wires these stages and uses existing artifact transport so hosts do not fetch GitHub source.

## Inputs

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| `operation` | Yes | — | `resolve` or `install`. |
| `version` | No | `""` | Required for install; the exact resolve output. |
| `expected-cpu` | No | `""` | Required for install: x86_64 or aarch64. |

## Outputs

| Field | Description |
| --- | --- |
| `version` | Full version selected by resolve. |

## Installation and retries

Download and `--check` both packages before installing Toolkit followed by ops. Keep the complete version directory, such as `/opt/cann/9.2.0`, supporting existing `/opt` symlinks. Write one visible `installed-version.txt` only after checking the target environment, compiler and OPP directory. Completed versions skip installation; incomplete directories retry with `--force`. Cache downloads in `/opt/cann/packages`. Reserve this root for the workflow. Retain history and caches; do not update drivers/firmware. These checks validate installation and the compiler, not on-device operator execution.

`/opt/cann/latest` points to a completed version directory and is checked on cache reuse. The same precedence rules advance it without downgrading. Existing regular files are not replaced. Failed installs do not update latest.

## Scheduling

`install-cann-release.yml` runs Monday at 03:00 Asia/Shanghai (Sunday 19:00 UTC), or manually on main. Default routing selects both `bz` hosts (X64 and ARM64); optional `runner_label` and `target_arch` select one unique host. It shares the weekly workflow concurrency group to serialize global CANN registration changes. Retain host logs for 30 days; one host's failure does not cancel the other. PRs and unmerged branches cannot install.
