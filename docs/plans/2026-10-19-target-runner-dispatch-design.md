# Targeted dependency preparation

The existing NPUIR and CANN entry points prepare one worker per architecture.
Two replacement Ascend950PR hosts both use x86_64, so dispatching those defaults
cannot prepare both hosts reliably.

Add optional `runner_label` and `target_arch` inputs to the current NPUIR and
CANN workflows. A unique host label selects one matrix row, still requiring
Linux and the selected architecture. Empty labels retain the existing worker
pools and both architectures. Keep the historical 20260720 workflow unchanged.

A small shared Python data-shaping script generates the matrix and rejects
label lists, expressions and unsupported CPU architectures. Inputs enter the
script through environment variables. NPUIR dispatches to distinct host labels
can build concurrently; CANN retains its existing global installation lock.

Validate targeted x86/ARM routing, legacy defaults, invalid inputs, actual Actions
output serialization, main-only guards, unchanged archive contracts, bilingual
documentation and the complete documentation build. Merge before invoking the
new inputs on the two hosts. Verify actual runner assignments and installed
archive markers after the workflows finish.
