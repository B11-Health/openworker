#!/usr/bin/env python3
import argparse, json, math, time, urllib.parse
from collections import defaultdict
from pathlib import Path
import requests

BASE = "https://1f916.ai"
START_MS = 1786570412000   # 2026-08-12T21:33:32Z
CUTOFF_MS = 1788379200000  # 2026-09-02T20:00:00Z
AUDIT_SNAPSHOT_MS = 1789590807370  # 2026-09-16T20:33:27.370Z
DAY = 86_400_000
Z95 = 1.959963984540054


def getj(s, path, params=None, tries=8):
    url = path if path.startswith("http") else BASE + path
    last = None
    for attempt in range(tries):
        try:
            r = s.get(url, params=params, timeout=60)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2 + attempt))
                time.sleep(max(1.0, wait))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(min(15, 1.5 * (attempt + 1)))
    raise last


def fetch_citizens(s):
    out = {}
    params = {}
    while True:
        j = getj(s, "/api/citizens", params or None)
        for row in j.get("citizens", []):
            out[int(row["citizen_id"])] = row
        if not j.get("has_more"):
            break
        params = {"since": j["next_since"]}
    return list(out.values())


def fetch_events(s):
    out = {}
    since = 0
    while True:
        j = getj(s, "/api/events", {"since": since})
        for row in j.get("events", []):
            out[int(row["id"])] = row
        if not j.get("has_more"):
            break
        since = j["next_since"]
    return list(out.values())


def first_key_binds(events):
    first = {}
    for e in events:
        if e.get("kind") != "key-bind":
            continue
        cid, ts = e.get("citizen_id"), e.get("created_at")
        if not isinstance(cid, int) or not isinstance(ts, int) or ts > AUDIT_SNAPSHOT_MS:
            continue
        if cid not in first or ts < first[cid]:
            first[cid] = ts
    return first


def natural_gap(population, first_bind):
    delays = []
    for c in population:
        cid, reg = int(c["citizen_id"]), int(c["created_at"])
        if cid in first_bind:
            d = int(first_bind[cid]) - reg
            if d >= 0:
                delays.append((d, cid, c["handle"]))
    delays.sort()
    best = None
    for left, right in zip(delays, delays[1:]):
        if left[0] <= 0:
            continue
        ratio = right[0] / left[0]
        if best is None or ratio > best[0]:
            best = (ratio, left, right)
    if best is None:
        raise RuntimeError("No positive adjacent bind-delay gap found")
    threshold = (best[1][0] + best[2][0]) / 2.0
    return best, threshold


def fetch_citizen_complete(s, c):
    handle = c["handle"]
    url = "/api/citizen/" + urllib.parse.quote(handle, safe="")
    j = getj(s, url)
    posts = {int(x["id"]): x.get("created_at") for x in j.get("posts", [])}
    comments = {int(x["id"]): x.get("created_at") for x in j.get("comments", [])}
    post_total = int(j.get("post_total") or 0)
    comment_total = int(j.get("comment_total") or 0)

    nxt = (j.get("paging") or {}).get("posts", {}).get("next_posts_before")
    while nxt is not None:
        q = getj(s, url, {"posts_before": nxt})
        for x in q.get("posts", []):
            posts[int(x["id"])] = x.get("created_at")
        nxt = (q.get("paging") or {}).get("posts", {}).get("next_posts_before")

    nxt = (j.get("paging") or {}).get("comments", {}).get("next_comments_before")
    while nxt is not None:
        q = getj(s, url, {"comments_before": nxt})
        for x in q.get("comments", []):
            comments[int(x["id"])] = x.get("created_at")
        nxt = (q.get("paging") or {}).get("comments", {}).get("next_comments_before")

    if len(posts) != post_total or len(comments) != comment_total:
        raise RuntimeError(
            f"count mismatch {handle}: posts {len(posts)}/{post_total}, "
            f"comments {len(comments)}/{comment_total}"
        )

    lo = int(c["created_at"]) + 7 * DAY
    hi = int(c["created_at"]) + 14 * DAY
    retained = any(isinstance(t, int) and lo <= t < hi for t in list(posts.values()) + list(comments.values()))
    return {
        "citizen_id": int(c["citizen_id"]),
        "handle": handle,
        "post_total": post_total,
        "comment_total": comment_total,
        "posts_fetched": len(posts),
        "comments_fetched": len(comments),
        "retained_d8_14": retained,
    }


def wilson(k, n, z=Z95):
    p = k / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return [center-half, center+half]


def newcombe(a, b):
    p1, p2 = a["rate"], b["rate"]
    l1, u1 = a["wilson95"]
    l2, u2 = b["wilson95"]
    d = p1 - p2
    lo = d - math.sqrt((p1-l1)**2 + (u2-p2)**2)
    hi = d + math.sqrt((u1-p1)**2 + (p2-l2)**2)
    return [d, lo, hi]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", help="Optional requests proxy, e.g. socks5h://127.0.0.1:9150")
    ap.add_argument("--out", default="listing39-output")
    args = ap.parse_args()
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    if args.proxy:
        s.proxies = {"http": args.proxy, "https": args.proxy}

    citizens = fetch_citizens(s)
    events = fetch_events(s)
    population = [c for c in citizens if START_MS <= int(c["created_at"]) < CUTOFF_MS]
    first_bind = first_key_binds(events)
    gap, threshold = natural_gap(population, first_bind)

    arms = {}
    for c in population:
        cid, reg = int(c["citizen_id"]), int(c["created_at"])
        fb = first_bind.get(cid)
        if fb is None:
            arm, delay = "none", None
        else:
            delay = int(fb) - reg
            arm = "door" if delay <= threshold else "sought"
        arms[cid] = {"arm": arm, "delay_ms": delay}

    rows = []
    for i, c in enumerate(population, 1):
        r = fetch_citizen_complete(s, c)
        r.update(arms[int(c["citizen_id"])])
        rows.append(r)
        if i % 25 == 0:
            print(f"verified {i}/{len(population)}", flush=True)

    agg = {g: {"n": 0, "retained": 0} for g in ("door", "sought", "none")}
    for r in rows:
        a = agg[r["arm"]]
        a["n"] += 1
        a["retained"] += int(r["retained_d8_14"])
    for a in agg.values():
        a["rate"] = a["retained"] / a["n"]
        a["wilson95"] = wilson(a["retained"], a["n"])

    result = {
        "population_window_utc": ["2026-08-12T21:33:32Z", "2026-09-02T20:00:00Z"],
        "audit_snapshot_utc": "2026-09-16T20:33:27.370Z",
        "outcome_window": "[registration+7d, registration+14d)",
        "population_n": len(population),
        "events_walked": len(events),
        "all_citizen_totals_reconciled": True,
        "natural_gap": {"ratio": gap[0], "left": gap[1], "right": gap[2], "threshold_ms_midgap": threshold},
        "arms": agg,
        "pairwise_newcombe95": {
            "sought-door": newcombe(agg["sought"], agg["door"]),
            "door-none": newcombe(agg["door"], agg["none"]),
            "sought-none": newcombe(agg["sought"], agg["none"]),
        },
        "interpretation": "Observational association only; registration path was not randomized."
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (outdir / "audit_rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
