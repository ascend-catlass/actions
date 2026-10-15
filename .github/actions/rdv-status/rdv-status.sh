#!/usr/bin/env bash
# CATLASS comment assembly only; AtomGit transport and labels are public Actions.
set -euo pipefail
case "${RDV_PHASE}" in
    start) comment_body="🚀 RDV Started: ${RDV_RESULT_URL}" ;;
    finish)
        if [[ "${RDV_RESULT}" == success ]]; then
            comment_body="✅ RDV Succeeded: ${RDV_RESULT_URL}"
        else
            comment_body="❌ RDV Failed: ${RDV_RESULT_URL}"
        fi
        if [[ "${RDV_RESULT}" == failure && -n "${RDV_FAILURE_ANALYSIS_FILE:-}" && -s "${RDV_FAILURE_ANALYSIS_FILE}" ]]; then
            if [[ "$(wc -c < "$RDV_FAILURE_ANALYSIS_FILE")" -le 8192 ]]; then
                comment_body+=$'\n\n'"$(cat -- "$RDV_FAILURE_ANALYSIS_FILE")"
            else
                echo 'Failure analysis exceeds 8 KiB; publishing the original RDV result' >&2
            fi
        fi
        ;;
    *) echo 'phase must be start or finish' >&2; exit 1 ;;
esac
directory=$(mktemp -d "${RUNNER_TEMP:?}/rdv-comment.XXXXXX")
jq -cn --arg body "$comment_body" '{body: $body}' > "$directory/comment.json"
echo "body-file=$directory/comment.json" >> "$GITHUB_OUTPUT"
