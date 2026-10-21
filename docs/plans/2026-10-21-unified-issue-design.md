# Unified Issue Analysis and Classification

Community 1 owns both tasks. The hook dispatches it once for public open/reopen
events regardless of author. Updates remain ignored. Manual fix/review entries
remain separate and manual. The separate Community 5 entry is removed.

Prepare the existing label candidates for every author and source/discussion
context only for reply-eligible contributors. Compose one prompt and strict JSON
schema. One catlass-ai execution returns label, reason and Markdown reply; disabled
tasks must return null/empty fields. Already categorized Issues may still receive
analysis; role authors may still receive labels without an automated comment.

Project validated fields into publisher stage directories while retaining the
original successful execution record and a hash of the original response. Keep
the original result as evidence. Existing components enforce stale state, current
roles, manual category preservation, additive label writes, owned comment dedup
and read-back. Label failure must not suppress an otherwise valid reply.

Validate all task combinations, malformed output, provenance, one model call and
one dispatch; run behavior tests and bilingual documentation checks. Merge Actions
before switching the production hook. Verify a real read-only combined analysis
before deployment, and verify the deployed bundle against the merged revision.
