# New Issue Classification

Add Community 5 independently of the existing four community entries. The hook
dispatches every new public Issue, without the reply workflow's author-role gate.
Reopen/update events retain their existing behavior and never auto-classify.

The project composite prepares live Issue context and the intersection of existing
repository labels with the CATLASS Issue-kind vocabulary. The existing catlass-ai
stage produces one schema-validated label and reason without publishing credentials.
Publication consumes that successful stage's response and provenance, rechecks live
Issue content/state/labels and candidate existence, appends one label and verifies
the result. Existing classifications and unrelated labels are preserved.

Actions must merge before the hook change deploys. Tests cover all-author dispatch,
deduplication, stale input, removed labels, invalid model output and additive writes.
Manual dispatch with publish=false supports validation without mutations.
