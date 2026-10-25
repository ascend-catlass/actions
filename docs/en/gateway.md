# Webhook gateway

[中文](../zh/gateway.md) · [English](gateway.md)

`gateway/`

## What it does

Receives AtomGit (GitCode) webhook events, checks who triggered them, and dispatches to the matching workflow. It is the entry point for the community pipelines: AtomGit points at one webhook URL, and the gateway decides which pipeline runs.

## When to use it

When an AtomGit project needs to trigger workflows in this repository automatically. The gateway runs as a long-lived service, not inside a workflow.

## Processing

1. Check `X-GitCode-Token`; a mismatch with `WEBHOOK_PASSWORD` returns 401.
2. Match the event to a route by `object_kind` and event fields; unmatched events return `{"ok":true,"ignored":true}`.
3. Check whether the triggering user is on the allow list. Users off the list are dropped without dispatching.
4. Dispatch the workflow with a GitHub token, then look up the resulting run and record the event.

Rejection happens in the gateway, so requests off the allow list consume no Actions minutes.

## Routes

| Event condition | Workflow | Inputs |
| --- | --- | --- |
| Comment body is `rdvcompile`, target branch `master`, PR open | `test-atomgit-pr.yml` | `pr_number` |
| PR gains the `ci-pipeline-passed` label, PR open | `reply-atomgit-ci-passed.yml` | `pr_number` |
| Issue opened or reopened, not confidential | `reply-atomgit-issue.yml` | `issue_url`, `publish` |

## Multiple repositories

One gateway can serve several repositories, declared through `REPOS`:

```
REPOS=cann/catlass:catlass,cann/ops-nn:ops-nn,cann/ops-basic:ops-basic:develop
```

Each entry is `path:SIG[:branch]`. The branch falls back to `TARGET_BRANCH` when omitted. Rosters are fetched per SIG, and each repository keeps its own allow list.

The console has a repository selector at the top and shows only that repository's events and allow list. With a single managed repository the selector is hidden.

## How issues are handled

Issues are classified by **content**, not by who opened them:

| Content | Treatment |
| --- | --- |
| Reports a problem with this repository (bug, crash, suggestion, usage question) | Runs AI analysis and replies |
| Anything else (meeting notes, announcements, design discussion) | Posts a fixed reminder to close the loop; also assigns the author when they are a committer or maintainer |

Type labels are checked first; new issues usually have none, so the wording of the body decides. A minimum body length keeps empty issues from counting as feedback.

## Where the allow list applies

The list constrains PR routes only; issue analysis does not check it:

| Route | Checks list | Why |
| --- | --- | --- |
| `pr/comment/rdvcompile` | yes | Keeps arbitrary users from triggering CI |
| `pr/label/cipassed` | yes | Maintainer action |
| `issue/open` | no | Issue analysis is open to all authors |

Role differences — which authors get a reply — are decided by the downstream workflow, not by the gateway.

## Allow list

The list mixes role references and explicit names, comma separated:

| Form | Meaning |
| --- | --- |
| `@maintainer` | SIG maintainers, effective for every repository in that SIG |
| `@committer` | Committers of that repository only |
| `@committer:<path>` | Committers of that subdirectory only |
| `alice` | Explicit name, for people who need to trigger without committer rights |

Role data comes from the `cann/community` repository — `CANN/org-info.yaml` for maintainers and `CANN/sigs/<sig>/sig-info.yaml` for committers — refreshed on a TTL and cached locally. When fetching fails it falls back to the cache; if no cache exists it allows the request and leaves the decision to the downstream workflow.

The list can be edited in the admin UI. It lives in a config file and takes effect immediately.

## Test mode

Sending `X-Dry-Run: 1` runs the full authentication, routing and allow-list checks without calling GitHub, recorded as `dry_run`. The response reports `would_dispatch` and `inputs` so you can see what would happen.

## Admin UI

Overview, trigger log and allow-list editing. Source links jump straight to the AtomGit PR or issue, and the target column links to the exact GitHub Actions run.

## Deployment

A long-lived service listening on `8000` inside the container, mapped to `127.0.0.1:1109` on the host and exposed through cloudflared. The data directory sits on a mounted volume so container recreation keeps it.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `WEBHOOK_PASSWORD` | yes | Inbound password, must match the AtomGit webhook; also unlocks list editing |
| `GITHUB_ACTIONS_TOKEN` | yes | GitHub credential allowed to dispatch workflows here |
| `ALLOW_LIST` | | Initial list; once the config file exists, the file wins |
| `ALLOW_FILE` | | Path to the allow-list config file |
| `SIG_NAME` | | Which SIG roster to use, default `catlass` |
| `GITHUB_REPO` | | Target repository |
| `GITHUB_REF_BRANCH` | | Ref for the workflows |
| `REPOS` | | Managed repositories, `owner/repo:sig[:branch]`, comma separated; optional for a single repo |
| `TARGET_BRANCH` | | Target branch required by `rdvcompile` |
| `CI_PASSED_LABEL` | | Label that triggers the CI reminder |
| `ATOMGIT_WEB` | | AtomGit web domain, default `atomgit.com`; used for source links and the Issue URL passed to workflows |
| `DATA_DIR` | | Data directory holding the event DB and allow-list config |

## Running locally

```text
python -m pip install -r gateway/requirements.txt
WEBHOOK_PASSWORD=dev GITHUB_ACTIONS_TOKEN=... python -m uvicorn gateway.gateway:api --port 1109
```

Tests run offline against fixed roster samples:

```text
python gateway/tests/test_routes.py
python gateway/tests/test_roster.py
```
