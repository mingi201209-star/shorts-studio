# Independent visual review and autonomous strategy routing

The previous controller evaluated four numeric video metrics. A genuine improvement to auxiliary-label readability could therefore tie every metric and be held. This change adds an opt-in independent comparison of actual rendered frames while preserving all existing QA, exact-head CI and numeric non-regression gates.

## Visual evidence and decisions

Set SHORTS_QUALITATIVE_REVIEW=1 on the trusted review command. A separate subscription-backed Codex session receives four blinded A/B contact sheets, covering twelve fixed timestamps from each matched-duration portrait video. The editor does not select the frames or write the reviewer directory. The reviewer runs read-only with the user home and source repositories hidden, except the existing Codex login and its dedicated evidence folder. API/GitHub token environment variables are forbidden. This uses the existing subscription login, not a metered API key; the actual CLI-selected model is retained in runtime logs.

The response schema scores readability, explanation, progression and truthful presentation. A metric tie can qualify only with high-confidence improvement of at least one criterion, concrete matching observations at two distinct supplied times, no contradictory observation and no qualitative or metric regression. A numeric metric gain also requires the independent comparison to show no visual regression. Missing, mismatched, low-confidence or malformed evidence holds the candidate. Identical sampled pixels cannot qualify as qualitative improvement.

Video hashes, image hashes, randomized label mapping, supplied timestamps and the response binding are retained. Input media and image hashes are checked again after evaluation. The private label mapping is outside the reviewer's visible folder. Sampled-frame review does not certify audio, continuous playback, historical facts, legal rights or user approval. Those limits remain explicit.

## Feedback and strategy changes

Set autonomous_strategy_enabled=true in the trusted adapter configuration. Two actual no-edit or rejected-review outcomes move to the next substantive objective: mobile readability, causal explanation, opening storyboard, then new-material research. Each attempt retains its context, baseline, strategy, instruction and completed failures. The strategy changes the requested evidence and artifact, rather than merely resetting counters or relabeling an exhausted input. A successful new baseline naturally starts a new set of objectives.

Bounded time-specific observations and next actions from up to four recent independent reviews become data in the next editor prompt. They do not override factual, source, permission or QA rules. External research still requires actual source/author/license/subject evidence; unverified material must not be integrated. Explicitly allowlisted optional owned asset paths can now be created without git attempting to stage other nonexistent paths.

Reviewer unavailability is infrastructure failure, not a failed creative strategy: the controller waits thirty minutes before another expensive editing/render attempt. If all four strategies exhaust, the last verified video is preserved and the exact evidence/resource need remains visible. No implementation can guarantee endlessly improving artifacts without usable evidence; exhausted counters are not silently reset.

The worker remains resident when a campaign is blocked, checking its state without re-executing unsafe work. Explicit user approval of the current verified SHA still terminates the worker. No automatic human approval, upload or merge was added.

## Verification

Focused checks cover qualitative acceptance on numeric ties, non-regression, wrong bindings, unsupplied timestamps, insufficient/contradictory evidence, unavailable reviewers, substantive strategy changes, exhaustion, bounded feedback, and resident blocked monitoring. The real former attempt 116 was independently re-evaluated against the verified Terra revision. It remains HOLD: the reviewer recognized clearer explanatory qualifications but found crowding and insufficient causal progression, and returned concrete next actions. Its medium confidence was not promoted into a pass. An actual identical-video control must remain unchanged without invoking the model.
