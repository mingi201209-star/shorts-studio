# Repeated no-edit input guard

Two consecutive trusted no-edit outcomes bound to the same configuration,
candidate source commit, video identity, adapter code and input revision suppress
another editor invocation. The adapter returns deferred before budget reservation,
workspace creation or model execution. The worker keeps polling and the current
verified video remains available for exact-SHA approval.

This is input deduplication, not a daily quota. A different source candidate,
task/configuration, adapter implementation or operator research revision permits
a new attempt. Configuration policy changes still require the normal policy
migration; never reset the ledger to resume.

After adding genuinely new reviewed research, record its identity in
<campaign evidence root>/input-revision.txt (regular file, at most 1024 bytes).
The reference is appended to the editor prompt as context; it does not override
quality gates. The marker file is read-only to the editor sandbox. Do not change it just to replay an
exhausted prompt. Existing records without input signatures do not suppress work:
two new signed outcomes must first be collected.

This does not invent new work, perform source research, or guarantee an improved
video. Deferred status means the current editing task needs new input. QA/CI and
paid-execution restrictions remain mandatory for every actual candidate.
