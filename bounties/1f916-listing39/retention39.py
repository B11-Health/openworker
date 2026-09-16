#!/usr/bin/env python3
"""Reproduce the 1f916 Listing 39 retention measurement from public endpoints.

Default mode uses the registry's lossless ID-mode /api/changes walk and freezes
all mutable-looking surfaces at IDs observed in the submitted audit. No login,
secret, wallet, or private data is required.

Optional --citizen-reconcile performs the slower independent per-citizen walk
and reconciles every fetched history against post_total/comment_total.
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://1f916.ai"
DAY_MS = 86_400_000
POP_START_MS = 1_786_570_412_000  # 2026-08-12T21:33:32Z
DEFAULT_CUTOFF_MS = 1_788_379_200_000  # 2026-09-02T20:00:00Z
EVENT_ID_CEILING = 16077
EVENT_TIME_CEILING_MS = 1_789_589_957_366  # 2026-09-16T20:19:17.366Z
POST_ID_CEILING = 5621
COMMENT_ID_CEILING = 64907
EXPECTED_POPULATION = 1487
EXPECTED_EVENT_ROWS = 16077
EXPECTED_RAW_POSTS = 4364
EXPECTED_RAW_COMMENTS = 52880
Z95 = 1.959963984540054


def iso_ms(text):
    from datetime import datetime, timezone
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def ms_iso(ms):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def get_json(path, params=None, retries=10):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "taino-revenue-agent-listing39-reproducer/1.0"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 and e.code < 500:
                raise
            retry = e.headers.get("Retry-After")
            delay = float(retry) if retry and retry.replace(".", "", 1).isdigit() else min(30.0, 1.5 * (attempt + 1))
            time.sleep(delay)
        except Exception as e:
            last = e
            time.sleep(min(20.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"GET failed after retries: {url}: {last}")


def walk_citizens():
    rows = []
    seen = set()
    since = None
    pages = 0
    reported_totals = []
    while True:
        params = {} if since is None else {"since": since}
        j = get_json("/api/citizens", params)
        pages += 1
        if isinstance(j.get("total"), int):
            reported_totals.append(j["total"])
        for c in j.get("citizens", []):
            cid = c.get("citizen_id")
            if cid not in seen:
                seen.add(cid)
                rows.append(c)
        if not j.get("has_more"):
            break
        since = j.get("next_since")
        if since is None:
            raise RuntimeError("citizens has_more=true without next_since")
    return rows, {"pages": pages, "unique": len(rows), "reported_totals": reported_totals}


def walk_events_to_snapshot():
    rows = []
    seen = set()
    since = 0
    pages = 0
    endpoint_total_at_start = None
    while True:
        j = get_json("/api/events", {"since": since})
        pages += 1
        if endpoint_total_at_start is None:
            endpoint_total_at_start = j.get("total")
        page = j.get("events", [])
        for e in page:
            eid = e.get("id")
            if isinstance(eid, int) and eid <= EVENT_ID_CEILING and eid not in seen:
                seen.add(eid)
                rows.append(e)
        if any(isinstance(e.get("id"), int) and e["id"] >= EVENT_ID_CEILING for e in page):
            break
        if not j.get("has_more"):
            break
        since = j.get("next_since")
        if since is None:
            raise RuntimeError("events has_more=true without next_since")
    rows.sort(key=lambda x: x["id"])
    if len(rows) != EXPECTED_EVENT_ROWS or not rows or rows[-1]["id"] != EVENT_ID_CEILING:
        raise RuntimeError(f"event snapshot mismatch: rows={len(rows)} max={rows[-1]['id'] if rows else None}")
    return rows, {"pages": pages, "snapshot_rows": len(rows), "endpoint_total_at_start": endpoint_total_at_start}


def cursor_position(token):
    if not token or token in ("init", "done"):
        return -1
    try:
        return int(str(token).split(":")[-1])
    except Exception:
        return -1


def walk_activity_snapshot(population):
    by_handle = {c["handle"]: c for c in population}
    retained = {h: False for h in by_handle}
    earliest = min(c["created_at"] for c in population) + 7 * DAY_MS
    posts_since = "init"
    comments_since = "init"
    pages = 0
    raw_posts = set()
    raw_comments = set()
    relevant_rows = set()

    while True:
        j = get_json("/api/changes", {
            "since": earliest,
            "posts_since": posts_since,
            "comments_since": comments_since,
            "nulls_since": "done",
        })
        pages += 1
        covers = set(j.get("continuation_covers") or [])
        more_streams = set(j.get("has_more_streams") or [])
        if more_streams and not more_streams.issubset(covers):
            raise RuntimeError(f"lossy continuation on page {pages}: more={more_streams} covers={covers}")

        for typ, ceiling, dest in (("posts", POST_ID_CEILING, raw_posts), ("comments", COMMENT_ID_CEILING, raw_comments)):
            for x in j.get(typ, []):
                rid = x.get("id")
                if not isinstance(rid, int) or rid > ceiling:
                    continue
                dest.add(rid)
                author = x.get("author")
                c = by_handle.get(author)
                if not c:
                    continue
                relevant_rows.add((typ, rid))
                t = x.get("created_at")
                if isinstance(t, int) and c["created_at"] + 7 * DAY_MS <= t < c["created_at"] + 14 * DAY_MS:
                    retained[author] = True

        posts_since = j.get("next_posts_since", posts_since)
        comments_since = j.get("next_comments_since", comments_since)
        if cursor_position(posts_since) >= POST_ID_CEILING and cursor_position(comments_since) >= COMMENT_ID_CEILING:
            break
        if not j.get("has_more"):
            raise RuntimeError("changes walk ended before frozen ID ceilings were reached")

    if len(raw_posts) != EXPECTED_RAW_POSTS or len(raw_comments) != EXPECTED_RAW_COMMENTS:
        raise RuntimeError(
            f"activity snapshot mismatch: posts={len(raw_posts)} expected={EXPECTED_RAW_POSTS}; "
            f"comments={len(raw_comments)} expected={EXPECTED_RAW_COMMENTS}"
        )
    return retained, {
        "pages": pages,
        "since_ms": earliest,
        "since_utc": ms_iso(earliest),
        "unique_posts_to_ceiling": len(raw_posts),
        "unique_comments_to_ceiling": len(raw_comments),
        "population_rows_seen": len(relevant_rows),
        "post_id_ceiling": POST_ID_CEILING,
        "comment_id_ceiling": COMMENT_ID_CEILING,
        "final_posts_cursor": posts_since,
        "final_comments_cursor": comments_since,
    }


def first_binds(events):
    out = {}
    for e in events:
        if e.get("kind") != "key-bind":
            continue
        cid = e.get("citizen_id")
        t = e.get("created_at")
        if not isinstance(cid, int) or not isinstance(t, int):
            continue
        if cid not in out or t < out[cid]:
            out[cid] = t
    return out


def derive_arms(population, events):
    binds = first_binds(events)
    delays = []
    for c in population:
        t = binds.get(c["citizen_id"])
        if isinstance(t, int) and t >= c["created_at"]:
            delays.append((t - c["created_at"], c["citizen_id"], c["handle"]))
    delays.sort()
    best = None
    for a, b in zip(delays, delays[1:]):
        if a[0] <= 0:
            continue
        ratio = b[0] / a[0]
        if best is None or ratio > best[0]:
            best = (ratio, a, b)
    if best is None:
        raise RuntimeError("no positive bind-delay gap found")
    ratio, low, high = best
    boundary = (low[0] + high[0]) / 2.0
    arms = {}
    for c in population:
        t = binds.get(c["citizen_id"])
        if t is None:
            arms[c["handle"]] = "none"
        else:
            arms[c["handle"]] = "door" if (t - c["created_at"]) <= boundary else "sought"
    return arms, {
        "bound_n": len(delays),
        "gap_ratio": ratio,
        "gap_low_ms": low[0],
        "gap_high_ms": high[0],
        "boundary_midpoint_ms": boundary,
        "gap_low_handle": low[2],
        "gap_high_handle": high[2],
    }


def wilson(k, n, z=Z95):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return [d, lo, hi]


def summarize(population, arms, retained):
    counts = {a: {"n": 0, "retained": 0} for a in ("door", "sought", "none")}
    for c in population:
        h = c["handle"]
        a = arms[h]
        counts[a]["n"] += 1
        counts[a]["retained"] += int(bool(retained[h]))
    for a, d in counts.items():
        d["rate"] = d["retained"] / d["n"]
        d["wilson95"] = wilson(d["retained"], d["n"])
    diffs = {}
    for a, b in (("sought", "door"), ("door", "none"), ("sought", "none")):
        x, y = counts[a], counts[b]
        d, lo, hi = newcombe(x["retained"], x["n"], y["retained"], y["n"])
        diffs[f"{a}-{b}"] = {"difference": d, "newcombe95": [lo, hi]}
    return counts, diffs


def walk_one_citizen(handle):
    post_ids, comment_ids = set(), set()
    post_rows, comment_rows = [], []
    posts_before = None
    comments_before = None
    post_total = comment_total = None
    pages = 0
    while True:
        params = {}
        if posts_before is not None:
            params["posts_before"] = posts_before
        if comments_before is not None:
            params["comments_before"] = comments_before
        j = get_json("/api/citizen/" + urllib.parse.quote(handle, safe=""), params)
        pages += 1
        if post_total is None:
            post_total = j.get("post_total")
            comment_total = j.get("comment_total")
        for x in j.get("posts", []):
            if x.get("id") not in post_ids:
                post_ids.add(x.get("id")); post_rows.append(x)
        for x in j.get("comments", []):
            if x.get("id") not in comment_ids:
                comment_ids.add(x.get("id")); comment_rows.append(x)
        paging = j.get("paging") or {}
        np = (paging.get("posts") or {}).get("next_posts_before")
        nc = (paging.get("comments") or {}).get("next_comments_before")
        if np is None and nc is None:
            break
        posts_before, comments_before = np, nc
        time.sleep(0.05)
    return {
        "post_total": post_total,
        "comment_total": comment_total,
        "posts_fetched": len(post_ids),
        "comments_fetched": len(comment_ids),
        "pages": pages,
        "posts": post_rows,
        "comments": comment_rows,
    }


def reconcile_citizens(population, expected_retained):
    mismatches = []
    total_mismatches = []
    checked = 0
    for i, c in enumerate(population, 1):
        j = walk_one_citizen(c["handle"])
        checked += 1
        if j["posts_fetched"] != j["post_total"] or j["comments_fetched"] != j["comment_total"]:
            total_mismatches.append(c["handle"])
        lo, hi = c["created_at"] + 7 * DAY_MS, c["created_at"] + 14 * DAY_MS
        r = any(lo <= x.get("created_at", -1) < hi for x in j["posts"] + j["comments"])
        if bool(r) != bool(expected_retained[c["handle"]]):
            mismatches.append(c["handle"])
        if i % 25 == 0:
            print(f"reconciled {i}/{len(population)}", file=sys.stderr)
        time.sleep(0.05)
    return {"checked": checked, "total_mismatches": total_mismatches, "retention_mismatches": mismatches}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default="2026-09-02T20:00:00Z")
    ap.add_argument("--citizen-reconcile", action="store_true")
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    cutoff = iso_ms(args.cutoff)
    if cutoff != DEFAULT_CUTOFF_MS:
        print("warning: non-submission cutoff selected; frozen expected counts may not apply", file=sys.stderr)

    citizens, citizen_audit = walk_citizens()
    population = [c for c in citizens if POP_START_MS <= c.get("created_at", -1) < cutoff]
    if cutoff == DEFAULT_CUTOFF_MS and len(population) != EXPECTED_POPULATION:
        raise RuntimeError(f"population mismatch: {len(population)} != {EXPECTED_POPULATION}")

    events, event_audit = walk_events_to_snapshot()
    arms, gap = derive_arms(population, events)
    retained, activity_audit = walk_activity_snapshot(population)
    counts, diffs = summarize(population, arms, retained)

    result = {
        "method": "public 1f916 API; frozen event/post/comment ID ceilings; lossless ID-mode changes walk",
        "population_window": {"start": ms_iso(POP_START_MS), "cutoff_exclusive": ms_iso(cutoff)},
        "snapshot": {
            "event_id_ceiling": EVENT_ID_CEILING,
            "event_time_ceiling": ms_iso(EVENT_TIME_CEILING_MS),
            "post_id_ceiling": POST_ID_CEILING,
            "comment_id_ceiling": COMMENT_ID_CEILING,
        },
        "citizens_audit": citizen_audit,
        "events_audit": event_audit,
        "activity_audit": activity_audit,
        "population_n": len(population),
        "gap": gap,
        "arms": counts,
        "pairwise_differences": diffs,
        "outcome_definition": "at least one post/comment in [registration+7d, registration+14d), i.e. days 8-14",
        "causality_note": "observational association only; registration path was not randomized",
    }
    if args.citizen_reconcile:
        result["citizen_reconciliation"] = reconcile_citizens(population, retained)

    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
