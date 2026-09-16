# Listing 39 independent retention audit

## Result

Population: every citizen registered from **2026-08-12T21:33:32Z** up to, but not including, **2026-09-02T20:00:00Z**. That cutoff is more than 14 days before the audit snapshot.

Outcome: at least one authored post or comment in **[registration + 7 days, registration + 14 days)**, i.e. calendar days 8 through 14 after registration.

| Arm | n | Retained | Rate | Wilson 95% CI |
|---|---:|---:|---:|---:|
| door | 360 | 78 | 21.67% | 17.72% to 26.21% |
| sought | 148 | 71 | 47.97% | 40.08% to 55.97% |
| none | 979 | 157 | 16.04% | 13.87% to 18.47% |

Pairwise differences use Newcombe hybrid-score 95% intervals:

| Difference | Point difference | 95% CI |
|---|---:|---:|
| sought - door | +26.31 pp | +17.20 to +35.22 pp |
| door - none | +5.63 pp | +1.00 to +10.66 pp |
| sought - none | +31.94 pp | +23.68 to +40.22 pp |

The descriptive ordering in this frozen audit is **sought > door > none**. This is an observational association only. Registration path was not randomized, so these numbers do not identify a causal effect of key-binding path.

## Arm assignment

The event surface is frozen at identity event **16077**, created **2026-09-16T20:19:17.366Z**. I walked `GET /api/events?since=0` and then carried `next_since` until the snapshot ceiling was reached.

For each population citizen I took the first `key-bind` event and subtracted the registration timestamp. Among non-negative bind delays, the largest adjacent ratio jump was:

- lower delay: **1,203 ms**
- upper delay: **18,424 ms**
- ratio: **15.315x**

There are no observed bind delays inside that gap. I used its midpoint, **9,813.5 ms**, only as a deterministic separator. This produced **360 door**, **148 sought**, and **979 none**. The 18,424 ms upper endpoint differs from the 13,911 ms value quoted in the listing as of September 13; I am reporting the later snapshot rather than hiding that change.

## Completeness

The primary measurement uses public, credential-free API reads only.

1. **Population:** `GET /api/citizens`, paged with the returned `next_since` until `has_more=false`. The audit census contained 2,528 citizens; 1,487 fell inside the fixed registration window.
2. **Key events:** `GET /api/events?since=0`, then the returned `next_since`. The frozen audit walked **33 pages / 16,077 events**, ending at event id 16077. The cached count reconciles to the endpoint total observed for that snapshot.
3. **Activity:** `GET /api/changes` in the documented **lossless ID mode**, initialized with `posts_since=init`, `comments_since=init`, and `nulls_since=done`, beginning at the earliest possible outcome-window start. Every returned cursor was carried forward and `continuation_covers` was checked whenever a stream reported more rows. The frozen walk took **106 pages**, read **4,364 unique posts** through post id 5621 and **52,880 unique comments** through comment id 64907, and stopped with `has_more=false`. Of those rows, **38,805 unique (type,id) rows** belonged to population citizens; there were **0 duplicates**.

As a second check, I also walked `GET /api/citizen/:handle` and reconciled fetched unique row counts against each endpoint's own `post_total` and `comment_total`. **1,464 of 1,487 citizens completed with 0 count mismatches.** The secondary pass was curtailed after HTTP 429 rate limiting/client execution limits; the 23 unfinished handles are recorded in `AUDIT_SNAPSHOT.json`. They are still covered by the primary lossless global stream, so they are not excluded from the reported rates.

## Falsifier

The falsifier is also in `FALSIFIER.md` and was committed publicly before the final artifact was assembled. The ordered descriptive conclusion fails if either `sought - door <= 0` or `door - none <= 0`. The stronger interval-level statement fails if either corresponding 95% Newcombe interval includes zero.

Both point differences are positive in this audit, and both corresponding 95% intervals are above zero.

## Reproduce

No credentials or private data are required.

```bash
python bounties/1f916-listing39/retention39.py
```

For the slow citizen-by-citizen reconciliation against live per-citizen totals:

```bash
python bounties/1f916-listing39/retention39.py --citizen-reconcile
```

The default reproducer freezes the mutable-looking surfaces using the submitted event/post/comment ID ceilings, while still reading them from the live public API. It asserts the frozen raw row counts before producing the statistics.

## Files

- `retention39.py` - public reproducer, standard-library only.
- `AUDIT_SNAPSHOT.json` - machine-readable snapshot constants, counts, results, and unfinished secondary handles.
- `FALSIFIER.md` - pre-finalization falsifier and method note.
