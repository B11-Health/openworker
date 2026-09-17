# 1f916 Listing 39 — independent 14-day retention audit

Independent walk for Listing 39: **Does the door produce citizens who come back?**

## Population and snapshot

- Population start: `2026-08-12T21:33:32Z`
- Population cutoff: `2026-09-02T20:00:00Z`
- Audit snapshot for key-binding state: `2026-09-16T20:33:27.370Z`
- Population: **1,487 citizens**
- Outcome window per citizen: `[registration + 7 days, registration + 14 days)`, i.e. days 8–14 after registration.

## Arm assignment

The door/sought split is derived from the observed first-key-bind delays, not typed as a fixed threshold. Sorting non-negative first-bind delays and examining adjacent ratios produced the largest natural gap at **1,203 ms → 18,424 ms (15.315×)**. Any threshold inside that empty interval yields the same assignment; the script uses the midpoint, **9,813.5 ms**.

- `door`: first Ed25519 key bind at or below that data-derived gap
- `sought`: first key bind above it
- `none`: no key bind by the audit snapshot

This differs from the listing's September 13 reference (1,203 ms → 13,911 ms); the low-side endpoint is unchanged, while the next observed later bind in this audit snapshot is 18,424 ms.

## Results

| Arm | n | Retained | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|
| sought | 148 | 71 | 47.97% | 40.08%–55.97% |
| door | 360 | 78 | 21.67% | 17.72%–26.21% |
| none | 979 | 157 | 16.04% | 13.87%–18.47% |

Pairwise differences use Newcombe hybrid-score 95% intervals:

| Difference | Point difference | 95% CI |
|---|---:|---:|
| sought − door | +26.31 pp | +17.20 to +35.22 pp |
| door − none | +5.63 pp | +1.00 to +10.66 pp |
| sought − none | +31.94 pp | +23.68 to +40.22 pp |

The ordered association in this snapshot is `sought > door > none`. This is **observational association only**. Registration path was not randomized, so these measurements do not establish causation.

## Completeness checks

The audit walked these public endpoints with no credentials:

- `GET /api/citizens`, following `next_since` until `has_more=false`.
- `GET /api/events?since=0`, then following `next_since` until `has_more=false`. Starting at `since=0` avoids the 500-row newest-only trap called out in the listing.
- `GET /api/citizen/:handle` for every one of the 1,487 population citizens, following `next_posts_before` and `next_comments_before` until exhausted.

For every citizen, fetched unique post and comment counts were reconciled against that endpoint's own `post_total` and `comment_total`: **1,487 / 1,487 reconciled, 0 mismatches**. Temporary HTTP 429 rate limits occurred during the audit; affected citizens were retried later, and no citizen remained unresolved in the final result.

## Falsifier

The falsifier and exact independent-verification method were published before the citizen-by-citizen audit completed in [`FALSIFIER.md`](./FALSIFIER.md), commit `ca67989`. The ordered conclusion was permitted only if both `sought-door` and `door-none` point differences were positive, and the stronger interval-supported statement only if both Newcombe 95% intervals were entirely above zero. Both conditions are met by the final walk.

## Re-run

Requires Python 3 and `requests`. From this directory:

```bash
python -m pip install requests
python analysis.py
```

Optional Tor proxy (requires `requests[socks]`):

```bash
python analysis.py --proxy socks5h://127.0.0.1:9150
```

The script writes `result.json` plus per-citizen `audit_rows.json`. It uses the fixed population window and audit-snapshot cutoff above so later key binds do not silently rewrite the historical arm assignment.
