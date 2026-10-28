# Repeated-rejection loop correction

Observed on 2026-10-29 KST: the original strategy selector counted only two rejection messages. Source-scope violations and other failures did not consume a strategy attempt. The editor was also told to use an allowlist without receiving the exact filenames. It produced assets/comet-terra-opening/* while permission was for assets/autonomous/*, and the opening strategy repeated thirty times. These rejected files never became the verified candidate.

Corrections:
- Every rejected outcome counts toward that strategy's two-attempt limit, except recognized subscription/reviewer outages.
- History is scoped to the unchanged verified candidate within the immutable campaign configuration, not the controller-code hash. A controller update cannot erase causal failure history.
- Complete retained history is checked; failures do not expire behind a 128-entry window.
- The editor receives the exact editable path list and instructions to keep helper scripts/scratch files under /tmp.
- Scope rejection records retain the offending paths as bounded data for the next prompt. The permission boundary itself is unchanged.

Validation: 105 focused checks pass, including formerly uncounted error labels, unknown future rejection reasons, changed controller context, older-than-128 history and exact-path feedback. Replaying the actual retained campaign history selects new_material_research instead of repeating opening_storyboard. The previous video and all rejected attempts remain preserved. Rejected paths were not retroactively approved, budgets/iteration counters were not reset, and user acceptance remains unset.

The logs also contained actual failed CLI subscription-quota errors. They are recognized only from failed invocation evidence and explicit ERROR lines, not harmless telemetry. Provider recovery uses increasing 30-minute-to-6-hour backoff without consuming creative-strategy attempts; retained legacy quota logs are recognized without rewriting their result files. This respects provider limits rather than bypassing them.
