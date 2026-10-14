# Prepare, reply to or assign a GitCode Issue

[中文](../../zh/actions/gitcode-issue.md) · [English](../../en/actions/gitcode-issue.md)

`gitcode-issue`

## What it does

Provides three Issue operations: prepare collects Issue and source context; publish creates or updates an automation reply owned by the current account; assign posts an assignment-command comment for an eligible role-member author. The Action itself does not call a model.

## When to use it

Use it to compose Issue analysis or separate context preparation from comment publication.

## What happens

1. prepare: clone source when needed, read the Issue and discussion, and create context using a trusted prompt template.
2. Run model analysis separately through the trae-cn Action.
3. publish: recheck Issue and discussion changes, publish or update the reply, then read it back. assign: check roles and open state and reuse an identical assignment comment.

## Before you run it

- A Linux runner with Python 3, Git and a token allowed to read Issues and write comments.
- prepare needs a trusted prompt-template file. publish needs the earlier result directory and model response file. Role routing uses community-repo-roles output.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- uses: actions/checkout@v4
  with:
    repository: ascend-catlass/actions
    ref: main
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-issue@main
  with:
    operation: 'prepare'
    token: ${{ secrets.GITCODE_TOKEN }}
    issue-url: 'https://gitcode.com/cann/catlass/issues/739'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `operation` | Yes | — | prepare, publish or assign (comment /assign @author for a role member) |
| `token` | Yes | — | GitCode token from an Actions secret |
| `issue-url` | Yes | — | GitCode Issue URL |
| `worktree` | No | `_issue-source` | Source checkout path; prepare clones here if absent |
| `prompt-template` | No | `.github/prompts/gitcode-issue-reply.md` | Trusted UTF-8 prompt template for prepare |
| `result-directory` | No | `_issue-result` | Directory for context metadata and publication evidence |
| `response-file` | No | `""` | Final model answer for publish |
| `model` | No | `DeepSeek-V4.1-Flash` | Actual model name for the single final By line |
| `roles-file` | No | `""` | Optional community repository role JSON; rechecks author eligibility before analysis or publication |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `comment-url` | URL of the posted or reused comment; absent when the operation posts no comment. |
| `result-directory` | Context/publication evidence directory |

## Notes and common questions

- roles-file is optional at the interface. The existing Issue workflow supplies it and rechecks author eligibility during preparation and publication. assign requires role data.
- A changed Issue or discussion blocks a stale reply. Role-member Issues skip analysis and receive /assign @author-login using the platform account. GitCode processes the command comment.
- reply-gitcode-issue.yml defaults publish to true. Set it to false to analyze without posting replies or assignment comments. The workflow currently runs on manual dispatch.

## Implementation and callers

- [.github/actions/gitcode-issue/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-issue/action.yml)
- [scripts/gitcode_issue_reply.py](https://github.com/ascend-catlass/actions/blob/main/scripts/gitcode_issue_reply.py)
- [scripts/issue_reply_eligibility.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_eligibility.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
