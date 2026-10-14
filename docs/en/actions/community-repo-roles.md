# Look up community maintainers and committers

[中文](../../zh/actions/community-repo-roles.md) · [English](../../en/actions/community-repo-roles.md)

`community-repo-roles`

## What it does

Reads an existing CANN community checkout to identify the SIGs, maintainers and declared committers responsible for a repository. It uses role declarations rather than guessing from display names.

## When to use it

Use it when routing an Issue or checking whether its author is already a declared project maintainer or committer.

## What happens

1. Read community configuration and personnel declarations for the repository.
2. Resolve repository and SIG role declarations.
3. Return account lists, SIGs and a JSON file containing source information.

## Before you run it

- A Linux runner with Git; the Action sets up Python 3.12 and installs PyYAML.
- Clone the community repository first and pass community-path. No GitCode token is needed.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- name: Download community declarations
  run: git clone --depth 1 https://atomgit.com/cann/community.git _issue-community
- id: action
  uses: ascend-catlass/actions/.github/actions/community-repo-roles@main
  with:
    repository: 'cann/catlass'
    community-path: '_issue-community'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `repository` | Yes | — | owner/repo or HTTPS GitCode/AtomGit repository URL |
| `community-path` | Yes | — | Path to an existing community checkout (relative to workspace or absolute) |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `maintainers` | JSON array of maintainer GitCode IDs |
| `committers` | JSON array of explicitly declared SIG and repository committer GitCode IDs |
| `sigs` | JSON array of SIG names managing the repository |
| `result` | JSON object with people details, scoped configurations and source files |
| `result-file` | Absolute path to the JSON result file |

## Notes and common questions

- Results reflect declarations in the selected checkout; they do not replace platform permission checks.
- The Issue workflow calls this before model analysis and routes a role-member Issue to author assignment.

## Implementation and callers

- [.github/actions/community-repo-roles/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/community-repo-roles/action.yml)
- [scripts/community_repo_roles.py](https://github.com/ascend-catlass/actions/blob/main/scripts/community_repo_roles.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
