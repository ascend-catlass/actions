# Prepare and reply to a CATLASS AtomGit Issue

[中文](../../zh/actions/atomgit-issue.md) · [English](../../en/actions/atomgit-issue.md)

`atomgit-issue`

## What it does

Composes the public Issue context and comment Actions with CATLASS role eligibility, reply prose and legacy-comment policies. The Action itself does not run a model.

## When to use it

Use it to compose Issue analysis or separate context preparation from comment publication.

## What happens

1. prepare: clone source when needed, read the Issue and discussion, and create context using a trusted prompt template.
2. Run model analysis separately through the public traecn Action.
3. publish: recheck Issue and discussion changes, publish or update the reply, then read it back.

## Before you run it

- A Linux runner with Python 3, Git and a token allowed to read Issues and write comments.
- prepare needs a trusted prompt-template file. publish needs the earlier context directory and TRAE execution result directory. Role routing uses community-repo-roles output.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- uses: actions/checkout@v4
  with:
    repository: ascend-catlass/actions
    ref: main
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-issue@main
  with:
    operation: 'prepare'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
    issue-url: 'https://atomgit.com/cann/catlass/issues/739'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `operation` | Yes | — | prepare or publish |
| `token` | Yes | — | AtomGit token from an Actions secret |
| `issue-url` | No | `""` | Required for prepare; publish reads the Issue from its context instead. |
| `worktree` | No | `_issue-source` | Source checkout path; prepare clones here if absent |
| `prompt-template` | No | `.github/prompts/atomgit-issue-reply.md` | Trusted UTF-8 prompt template for prepare |
| `result-directory` | No | `_issue-result` | Directory for context metadata and publication evidence |
| `stage-result` | No | `""` | Required for publish: TRAE result-directory containing response.md and result.json from the same execution. |
| `roles-file` | No | `""` | Optional community repository role JSON; rechecks author eligibility before analysis or publication |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `comment-url` | URL of the posted or reused comment; absent when the operation posts no comment. |
| `result-directory` | Context/publication evidence directory |

## Notes and common questions

- Publication accepts one analysis result directory. Body and attribution come from the same successful execution; the model is selected only at execution. An unspecified model omits attribution rather than guessing the account default.
- The workflow checks the author before analysis. Publication checks the current author and discussion again using roles-file.
- Existing owned legacy replies migrate to the public comment marker after those checks; retries update the same comment.
- The workflow is manually dispatched. `publish=false` generates an analysis without publishing.

## Implementation and callers

- [.github/actions/atomgit-issue/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-issue/action.yml)
- [scripts/issue_reply_policy.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_policy.py)
- [scripts/issue_reply_eligibility.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_eligibility.py)
- [.github/workflows/reply-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-issue.yml)

Context collection and comment publication use `yuantao313/actions/atomgit-issue-context` and `atomgit-issue-comment`. This adapter keeps CATLASS author-role and prose rules. Existing owned replies migrate to the shared marker only after stale-state and role checks. Check out the pinned shared helpers into `shared_actions` before using this project adapter.
