# Community automation implementation plan

**Goal:** Four community workflows: automatic Issue analysis, automatic CI-passed reminders, manual simple-Issue fixes, and manual inline PR review.

**Architecture:** Actions own analysis, fixes and publication, with a final stale-state and author-role check. Existing build, nightly, release and historical NPUIR workflows remain available. All changes go through feature PRs.

**Tech stack:** Cloudflare Workers JavaScript, GitHub Actions, Python, TRAE CN CLI 0.209.1, MkDocs.

1. Add regression cases for running CI and stale label payloads; require the passed label in the event before dispatch.
2. Add Issue-open/reopen handler. Read the Issue author and community role declarations; skip declared committers and maintainers. Recheck in Action before publishing.
3. Reuse the existing Issue analysis and TRAE stages; extract the pinned CLI installer for all three model workflows.
4. Implement manual Issue fix preparation, bounded changes, explicit validation, fork branch push, PR creation and one compile comment; preserve retry evidence.
5. Implement manual PR review with pinned base/head, structured findings, changed-line validation, stale-head rejection, owned comment deduplication and read-back.
6. Rewrite Chinese/English entry points and workflow guides by purpose; preserve detailed build setup in an operations page.
7. Add PR-only validation without secrets or publication, run local tests and strict docs build, review diffs, push feature branches and open feature PRs. Do not merge or deploy unmerged changes.
