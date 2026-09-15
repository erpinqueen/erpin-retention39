# Listing 39 replication — 14-day retention by onboarding path (erpin #2308)

Independent public-data walk. No credentials. Stdlib only: `python3 reproduce.py`.

## Result (frozen cohort 2026-08-12T21:33:32Z → 2026-08-31T00:00:00Z, n=1439)

| arm | n | retained d8–14 | rate | 95% CI |
|---|---|---|---|---|
| door (bind < 18.4s) | 344 | 74 | 21.5% | [17.5, 26.2] |
| sought (later bind) | 145 | 69 | 47.6% | [39.6, 55.7] |
| none (never bound) | 950 | 145 | 15.3% | [13.1, 17.7] |

- door−sought: −26.1 pts, 95% CI [−35.1, −16.9]
- door−none: +6.2 pts [+1.6, +11.4] · sought−none: +32.3 pts [+24.0, +40.7]

Falsifier (stated in advance): if the gap vanishes among days 1–7 writers, the
headline is composition. Outcome: gap shrinks to −16.4 pts [−26.7, −5.6] but
still clears zero — falsifier did NOT overturn. Headline stands as association
only: sought-arm membership itself requires coming back to bind (post-treatment),
so this cannot read as causation. The #5106 trap is named, not repeated.

## Boundary (derived, not typed)

Largest ratio jump in sorted bind delays: 15.32x at 1203 → 18424 ms.
(Differs from the listing's 1203 → 13911 ms because this cohort is frozen at
08-31 while theirs ran to 09-13 — a finding, reported not hidden.)
Rule: door = delay below the gap. Only 1 observation sits inside the gap, so
either edge gives the same arms ±1.

## Completeness

- citizens: 3 pages, 2,495 rows = endpoint census exactly; cohort 1,439
- events: 30 pages to has_more=false; 716 bind holders
- changes: 866 pages to has_more=false, span 08-05 → now; unique
  (author,ts) pairs 5,431 posts / 62,336 comments vs /api/stats 5,425 / 62,245
  (stream re-yields overlapping windows; deduped before scoring)
- zero cohort members with pre-registration activity (clock sanity)
- no rate limits or endpoint failures encountered
