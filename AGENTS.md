# Working on actions

- Functional changes go on `codex/` branches and are submitted as PRs. Do not push directly to main or deploy unmerged features.
- Keep the four community entry points separate from build, release, environment and reusable component workflows.
- Actions recheck current labels, author roles and stale state before publication.
- Consume public components from yuantao313/actions; maintain only CATLASS policies and hardware stages here.
- Keep TRAE CN model steps free of AtomGit/GitHub publishing tokens. Manual fix/review entries must stay manual.
- Preserve the historical NPUIR 20260720 workflow for diagnosis.
- Run relevant behavior tests and bilingual documentation checks before submitting.
- Prefer established Actions for GitHub transport and infrastructure. Put reusable business steps behind composite Actions; keep workflows focused on wiring inputs and outputs. Small standalone scripts are appropriate for prompt preparation, data shaping and comment assembly. Do not replace one script language with another or inline implementation merely to avoid scripts.
- Preserve credential compatibility: prefer ATOMGIT_TOKEN and fall back to GITCODE_TOKEN when empty; keep existing deployment environment identifiers.
