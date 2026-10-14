# Call the GitCode API

[中文](../../zh/actions/gitcode-api.md) · [English](../../en/actions/gitcode-api.md)

`gitcode-api`

## What it does

Wraps GitCode authentication, request encoding and JSON response storage in one step. A caller supplies an API path and optional request file; subsequent steps read the response file.

## When to use it

Use it to read Issues, pull requests or other GitCode data, or to add API operations to a workflow.

## What happens

1. Validate the token, HTTP method and relative API path.
2. Send the request to the fixed GitCode v5 API root.
3. Save the JSON response under RUNNER_TEMP and return its path.

## Before you run it

- A Linux runner with Python 3 and access to api.gitcode.com.
- Pass the token through an Actions secret. body-file must contain a JSON object without credentials.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-api@main
  with:
    token: ${{ secrets.GITCODE_TOKEN }}
    method: 'GET'
    path: '/repos/cann/catlass/pulls/123'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `token` | Yes | — | GitCode token from an Actions secret |
| `method` | No | `GET` | GET, POST, PATCH, PUT or DELETE |
| `path` | Yes | — | API path beginning with /, relative to the fixed GitCode v5 root |
| `body-file` | No | `""` | Optional JSON object file containing request fields, never credentials |
| `body-encoding` | No | `form` | form or json |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `response-file` | UTF-8 JSON response file in RUNNER_TEMP |

## Notes and common questions

- Supports GET, POST, PATCH, PUT and DELETE. This generic Action does not validate the business outcome.
- An empty successful response, as returned by some PATCH or DELETE calls, becomes {}. A business step should read back a comment or label when it needs to confirm the change.

## Implementation and callers

- [.github/actions/gitcode-api/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-api/action.yml)
- [scripts/gitcode_api.py](https://github.com/ascend-catlass/actions/blob/main/scripts/gitcode_api.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
