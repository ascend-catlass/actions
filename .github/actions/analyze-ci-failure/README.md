# Analyze a failed CI run

[中文手册](../../../docs/zh/actions/analyze-ci-failure.md) · [English guide](../../../docs/en/actions/analyze-ci-failure.md)

A reusable failure-analysis stage for any GitHub workflow in the caller repository.
It accepts a run ID and attempt, reads failed job logs through the official GitHub
client, reuses `setup-trae-cn` and `trae-cn`, and returns a Markdown attachment.
It does not know PR numbers, RDV labels or comment APIs. Callers own publication.
A small local script prepares bounded prompts and formats comments without network access.
