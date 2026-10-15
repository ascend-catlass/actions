# Run a TRAE CN analysis task

[中文](../../zh/actions/trae-cn.md) · [English](../../en/actions/trae-cn.md)

`trae-cn`

## What it does

Runs a repository task through the official China TRAE CLI 2.0 and returns files containing the final answer, execution events and status. Execution defaults to read-only.

## When to use it

Use it as the model execution step in Issue analysis or reuse it for repository analysis in another workflow.

## What happens

1. Validate inputs, CLI version and required interfaces, then create temporary login directories.
2. Log in with an enterprise PAT and pass the prompt through stdin to a noninteractive task.
3. Save the response, JSONL events, stderr and result.json; return status and clean up temporary login state.

## Before you run it

- A Linux runner with Python 3.9+, Git, a checked-out repository and the preinstalled official China CLI 2.0. This Action does not install the CLI.
- An enterprise PAT with CLI entitlement. Supply exactly one of prompt and prompt-file.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/trae-cn@main
  with:
    trae-pat: ${{ secrets.TRAE_CN_PAT }}
    prompt: 'Summarize the repository structure and list the relevant source files.'
    sandbox: 'read-only'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `trae-pat` | Yes | — | Enterprise TRAE CN personal access token (use an Actions secret) |
| `prompt` | No | `""` | Literal prompt; provide exactly one of prompt or prompt-file |
| `prompt-file` | No | `""` | UTF-8 prompt file inside working-directory, relative to that directory |
| `working-directory` | No | `.` | Checked-out Git repository, relative to GITHUB_WORKSPACE |
| `cli-path` | No | `traecli` | Preinstalled official TRAE CN CLI 2.0 executable (not trae-cli from trae-agent) |
| `expected-version` | No | `""` | Optional exact numeric CLI version to enforce before login |
| `model` | No | `""` | Optional model; empty uses the enterprise account default |
| `host` | No | `""` | Optional HTTPS enterprise API domain; empty uses the TRAE CN CLI default |
| `sandbox` | No | `read-only` | read-only for analysis or workspace-write for code changes |
| `output-schema-file` | No | `""` | Optional JSON Schema file inside working-directory for the final response |
| `timeout-seconds` | No | `900` | Total subprocess budget including version check, login and execution |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `result-directory` | Unique directory containing final response, JSONL events, stderr and result.json |
| `response-file` | Final answer path (consume only when status is success) |
| `events-file` | CLI stdout JSONL file |
| `stderr-file` | CLI stderr log |
| `result-file` | Machine-readable stage status and CLI version |
| `status` | success, failed, timeout or cancelled |
| `exit-code` | Stage exit code (124 on timeout; nonzero fails the action) |

## Notes and common questions

- Consume a response only when status=success. Failure, timeout or cancellation returns a nonzero exit status. The caller needs always() to upload failure logs.
- The work directory must be inside GITHUB_WORKSPACE. Prompt and schema files must remain within that repository. Code changes require explicitly choosing workspace-write instead of read-only.
- The PAT goes only to login; model execution does not inherit a GitHub token. CLI read-only mode does not replace host isolation. External tasks should use disposable workers without host credentials.
- It does not publish comments or push code. The existing Issue workflow installs a pinned CLI separately and uses gitcode-issue for publication.

## Implementation and callers

- [.github/actions/trae-cn/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/trae-cn/action.yml)
- [.github/actions/trae-cn/run.py](https://github.com/ascend-catlass/actions/blob/main/.github/actions/trae-cn/run.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
