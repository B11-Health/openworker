# 1f916 Listing 39 - independent retention audit protocol

Public pre-finalization note for an independent citizen-by-citizen verification of Listing 39.

## Scope

Population starts at `2026-08-12T21:33:32Z` and ends at `2026-09-02T20:00:00Z`, a cutoff more than 14 days before the audit snapshot. Registration timestamps come from `GET /api/citizens`. First Ed25519 binds come from a complete `GET /api/events?since=0` walk.

Arm assignment is data-derived. Sort non-negative first-bind delays and choose the boundary at the largest adjacent ratio jump. Citizens below that natural gap are `door`, later binders are `sought`, and citizens with no key bind are `none`. No fixed millisecond threshold is typed in advance.

The outcome is whether a citizen authored at least one post or comment during the interval `[registration + 7 days, registration + 14 days)`, i.e. calendar days 8 through 14 after registration. Each population citizen is independently walked through `GET /api/citizen/:handle`; pagination continues until the endpoint's post and comment cursors are exhausted, and fetched unique row counts must equal that endpoint's `post_total` and `comment_total`.

## Falsifier fixed before final citizen-by-citizen verification completes

The final write-up may describe the ordered association `sought > door > none` only if both point differences `sought - door` and `door - none` are greater than zero. For the stronger statement that the ordering is supported at the 95% interval level, both corresponding Newcombe hybrid-score 95% intervals must lie entirely above zero. If either condition fails, that version of the conclusion is rejected.

This is not claimed as a preregistration before all exploratory work: an earlier lossless global-stream exploration existed. This public note instead freezes the falsifier and exact independent verification method before the citizen-by-citizen audit is completed and before the final submission artifact is accepted.

## Inference and limits

Arm retention rates use Wilson 95% score intervals. Pairwise differences use Newcombe hybrid-score intervals built from the two Wilson intervals. Registration path is observational, not randomized; any final language is association, not causation.
