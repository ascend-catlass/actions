# TestPR failure analysis plan

Goal: Append a concise TRAE CN / DeepSeek-V4.1-Flash diagnosis to the existing RDV failure comment.

1. Expose a generic analyze-ci-failure composite Action accepting run ID and attempt and returning an analysis file/status. Use official actions/github-script and its authenticated Octokit client for GitHub transport. Keep prompt preparation and comment formatting in a small standalone script, without executing PR code.
2. Extract setup-trae-cn and reuse it across Issue analysis, Issue fixes, PR review and failure analysis. Compose it with the existing trae-cn model Action; accept a bounded structured diagnosis on a GitHub-hosted runner after preparation or tests fail.
3. Preserve RDV reporting in a separate always-running report job. Analysis timeout, unavailable logs, invalid output or missing artifacts produce the normal failure comment with an unavailable-analysis note.
4. Add an optional failure-analysis-file input to rdv-status; append it only for failure, retaining the original link, label transitions and success/cancellation behavior.
5. Test prompt redaction and bounds, raw-evidence removal, structured output validation, fallback and the actual Bash comment payload. Check shared component wiring and document both new Actions in Chinese and English.
6. Review changes, submit a feature PR, wait for CI, merge through the PR and verify the main workflow is published. No dev deployment is needed.
