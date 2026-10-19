# Rejected UNKNOWN candidate, retained for review

[Original run](https://github.com/mohammadisina1988-jpg/cross-ledger/actions/runs/39313139269), source revision `b82ce0ef76f82d52928fabda6cf6a0ccfede64cc`, contract SHA-256 `d58e663e131b561659fcd60db33565fad27244868d472cc82fb0225d7e03ceee`.

Deployment and the first lot's BLOCKED assessment succeeded. The second lot's admission transaction `0x7f2ed137f9b22a1ebce6cae7523f80e3a238e95b70aff916fa5eec932d68ba15` finalized MAJORITY_DISAGREE after three rotations. The final leader's `eq_outputs[0]`, decoded after its successful-result prefix byte, contains decisions `[UNKNOWN, PASS]` and anchors `[[], [0]]`. The complete source explicitly leaves transfer permission unspecified and states that the units never expire. The final votes are zero agree, three disagree and two idle. This rejected transaction is not a successful admission proof.

The original schema permitted empty UNKNOWN anchors, while the extraction prompt mentioned silence and the audit prompt left this case implicit. The revised prompts explicitly permit empty UNKNOWN anchors, including explicit unspecified facts, while still requiring independent full-source evaluation, exact decision agreement and a substantive audit for every criterion. The public receipt does not expose validators' individual audit answers, so this instruction mismatch is the diagnosed liveness concern, not a claim that their precise internal reasoning is known. New direct regressions cover both acceptance and substantive rejection of an empty-anchor UNKNOWN.

The original source is retained in Git history. Final proof markets are redeployed on the revised source, and this attempt is excluded from their receipt count.
