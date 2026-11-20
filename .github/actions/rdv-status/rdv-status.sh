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
            # AtomGit caps a comment body at 65536 characters. The collector
            # already bounds its excerpt well below that, so this only guards
            # against a caller passing something oversized.
            limit=${RDV_COMMENT_CHAR_LIMIT:-65536}
            prefix_chars=$(printf '%s' "${comment_body}" | wc -m)
            excerpt_chars=$(wc -m < "${RDV_FAILURE_ANALYSIS_FILE}")
            if (( prefix_chars + excerpt_chars > limit )); then
                echo 'Failure excerpt would exceed the comment limit; publishing the original RDV result' >&2
            else
                comment_body+=$'\n\n'"$(cat -- "${RDV_FAILURE_ANALYSIS_FILE}")"
            fi
        fi
        ;;
    *) echo 'phase must be start or finish' >&2; exit 1 ;;
esac
directory=$(mktemp -d "${RUNNER_TEMP:?}/rdv-comment.XXXXXX")
printf '%s' "$comment_body" > "$directory/comment.md"
echo "body-file=$directory/comment.md" >> "$GITHUB_OUTPUT"
