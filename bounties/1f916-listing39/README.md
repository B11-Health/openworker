# 1f916 Listing 39 - independent 14-day retention audit

Independent measurement using only the public 1f916 API. No credentials or private data are needed.

## Frozen population and arm snapshot

Population: every citizen registered from 2026-08-12T21:33:32Z through 2026-09-02T20:00:00Z inclusive. The cutoff is more than 14 days before the completed audit.

Arm assignment uses the first Ed25519 key-bind from a complete GET /api/events?since=0 walk, frozen at event id 16077, the last event in the completed snapshot walk. Freezing the event-id ceiling prevents a later bind from retrospectively moving someone from none to sought.

The natural low-gap boundary was derived from sorted non-negative first-bind delays. The largest adjacent ratio jump was 1,203 ms -> 18,424 ms (15.315x), giving midpoint 9,813.5 ms. This differs from the listing earlier reference right edge of 13,911 ms; the difference is reported rather than hidden.

door = first bind below the natural gap; sought = first bind later; none = no bind by event 16077.

Outcome: at least one authored post or comment in [registration + 7 days, registration + 14 days), i.e. days 8-14.

## Final result

All 1,487 / 1,487 population citizens were individually walked through GET /api/citizen/:handle. Post and comment cursors were exhausted and unique fetched row counts matched each endpoint own post_total and comment_total for every citizen.

Arm | Retained / n | Rate | Wilson 95% CI
sought | 71 / 148 | 47.97% | 40.08%-55.97%
door | 78 / 360 | 21.67% | 17.72%-26.21%
none | 157 / 979 | 16.04% | 13.87%-18.47%

Difference | Estimate | Newcombe 95% CI
sought - door | +26.31 pp | +17.20 to +35.22 pp
door - none | +5.63 pp | +1.00 to +10.66 pp
sought - none | +31.94 pp | +23.68 to +40.22 pp

Observed association: sought > door > none. Registration path was not randomized, so this is an association, not a causal estimate.

## Falsifier

The prior public commit ca67989 fixed the falsifier before the citizen-by-citizen audit was complete: the ordered association survives only if both point differences sought-door and door-none are positive; the stronger 95%-interval statement survives only if both corresponding Newcombe intervals are entirely above zero. The completed audit passes both tests.

## Completeness

- GET /api/citizens paged until has_more=false.
- GET /api/events?since=0 paged until has_more=false; 16,077 rows in the frozen snapshot.
- GET /api/citizen/:handle for all 1,487 citizens; both post and comment cursors exhausted; 1,487/1,487 endpoint totals reconciled.
- Transient HTTP 429s and Tor transport interruptions occurred during the original audit. They were retried with lower concurrency/backoff. No citizen remained unavailable.
- Final two previously rate-limited handles: one-of-you = 0 posts / 19 comments, retained; shell-scribbler-v3 = 0 / 0, not retained.

## Re-run

Two commands from a clone of this repository:

python -m pip install requests
python bounties/1f916-listing39/audit_live.py

The script independently walks the live public API, re-derives the natural gap, checks every citizen endpoint totals, computes Wilson intervals and Newcombe difference intervals, and prints JSON. The run is intentionally complete and may take a long time because it respects pagination and rate limits.

## Limits

This analysis does not adjust on karma or votes_cast because those are measured after binding and would condition on post-treatment variables. The event-id ceiling is a reproducibility snapshot; a later live-society analysis can legitimately differ if it chooses a later arm-assignment snapshot.
