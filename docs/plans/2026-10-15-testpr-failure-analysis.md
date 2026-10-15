# TestPR failure analysis plan

Goal: Append a concise TRAE CN / DeepSeek-V4.1-Flash diagnosis to the existing RDV failure comment.

1. Use actions/github-script and its authenticated Octokit client to collect current-attempt job logs and failed-step metadata. Bound and scrub the prompt excerpt without executing PR code. Do not add Python API/transport scripts. Actions read permission is scoped to the diagnostic job.
2. Run the existing pinned TRAE CN stage on a GitHub-hosted runner only after the test job fails. Accept a bounded structured diagnosis; keep evidence and uncertainty clear.
3. Preserve RDV reporting in a separate always-running report job. Analysis timeout, unavailable logs, invalid output or missing artifacts produce the normal failure comment with an unavailable-analysis note.
4. Add an optional failure-analysis-file input to rdv-status; append it only for failure, retaining the original link, label transitions and success/cancellation behavior.
5. Execute the inline github-script bodies with Node test doubles; test attempt isolation, redaction, output bounds, fallback and the actual Bash comment payload. Update bilingual Action/workflow guides.
6. Review changes, submit a feature PR, wait for CI, merge through the PR and verify the main workflow is published. No dev deployment is needed.
