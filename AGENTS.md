# Working on actions

- Functional changes go on `codex/` branches and are submitted as PRs. Do not push directly to main or deploy unmerged features.
- Keep the four community entry points separate from build, release, environment and reusable component workflows.
- dev decides automatic trigger eligibility from native event labels and author role accounts; Actions execute the task and recheck stale state before publication.
- Keep TRAE CN model steps free of GitCode/GitHub publishing tokens. Manual fix/review entries must stay manual.
- Preserve the historical NPUIR 20260720 workflow for diagnosis.
- Run relevant behavior tests and bilingual documentation checks before submitting.
