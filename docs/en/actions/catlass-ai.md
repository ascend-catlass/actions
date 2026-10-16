# Run a CATLASS AI task

[中文](../../zh/actions/catlass-ai.md) · [English](../../en/actions/catlass-ai.md)

Issue analysis, Issue fixes, PR review and failure diagnosis share this execution
policy. It selects DeepSeek-V4.1-Flash once, reads the optional TRAE_CN_HOST variable,
prepares the read-only sandbox and composes the public setup-traecn and traecn
Actions. CLI version checks use the setup output. Publishing tokens are not inputs.

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pat` | Yes | — | TRAE CN enterprise PAT. |
| `working-directory` | Yes | — | Prepared Git directory inside GITHUB_WORKSPACE. |
| `prompt-file` | Yes | — | Trusted prompt relative to that directory. |
| `output-schema-file` | No | `""` | Optional response schema relative to that directory. |
| `timeout-seconds` | No | `900` | Model execution budget. |

## Outputs

| Output | Meaning |
| --- | --- |
| `result-directory` | response.md and result.json from the same execution. |
| `status` | success, failed, timeout or cancelled. |

## Example

Requires Linux, sudo for installing bubblewrap when absent, and a prepared Git
checkout containing the prompt. Callers provide publication and stale-state checks.

```yaml
- id: ai
  uses: ascend-catlass/actions/.github/actions/catlass-ai@main
  with:
    pat: ${{ secrets.TRAE_CN_PAT }}
    working-directory: _task-source
    prompt-file: .automation-context/prompt.md
```

Pass the result-directory to the publisher. Do not pass another model ID.
