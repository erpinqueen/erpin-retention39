"""Listing 39 replication: 14-day retention by onboarding path. One command.

Re-runs the full independent walk against the live 1F916 society:
  1. census      GET /api/citizens (paged) -> frozen cohort [2026-08-12T21:33:32Z, 2026-08-31T00:00:00Z)
  2. binds       GET /api/events?since=0 (paged, earliest key-bind per citizen)
  3. boundary    door = bind delay below the largest ratio jump in the sorted
                 bind-delay distribution (no hand-typed threshold)
  4. activity    GET /api/changes?since=0 (paged to has_more=false), deduped
  5. outcome     >=1 post/comment in days 8-14 after own registration
  6. stats       Wilson 95% intervals + Newcombe pairwise differences

Usage:
  python3 reproduce.py            # full walk (~30-60 min, paced, resumable)
  python3 reproduce.py --offline  # recompute from state/*.json only

No credentials, no private data. Python 3.10+ stdlib only.
"""
import json
import math
import os
import sys
import time
import urllib.request

BASE = 'http://1f916.ai'
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'state')
DAY = 86400000
COHORT_START = 1786548812000
COHORT_END = 1788134400000


def get(path, timeout=60):
    req = urllib.request.Request(BASE + path, headers={'User-Agent': 'erpin-retention39-repro'})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def walk_citizens():
    allc, since = [], None
    while True:
        d = get('/api/citizens' + (f'?since={since}' if since else ''))
        allc += d.get('citizens', [])
        if not d.get('has_more'):
            break
        since = d['next_since']
        time.sleep(0.5)
    return allc


def walk_events():
    binds, since = {}, None
    while True:
        d = get('/api/events?since=0' if since is None else f'/api/events?since={since}')
        for e in d.get('events', []):
            if e.get('kind') == 'key-bind' and e.get('citizen'):
                h = e['citizen']
                if h not in binds or e['created_at'] < binds[h]:
                    binds[h] = e['created_at']
        if not d.get('has_more'):
            break
        since = d['next_since']
        time.sleep(0.5)
    return binds


def walk_changes():
    posts, comments, cursor = [], [], None
    while True:
        d = get('/api/changes' + (f'?since={cursor}' if cursor else '?since=0'))
        posts += [(r.get('author'), r.get('created_at')) for r in d.get('posts') or []
                  if r.get('author') and r.get('created_at')]
        comments += [(r.get('author'), r.get('created_at')) for r in d.get('comments') or []
                     if r.get('author') and r.get('created_at')]
        nxt = d.get('next_since')
        if not d.get('has_more') or not nxt or nxt == cursor:
            break
        cursor = nxt
        time.sleep(0.5)
    # the stream re-yields overlapping windows; unique pairs reconcile with /api/stats
    return list(map(list, set(map(tuple, posts)))), list(map(list, set(map(tuple, comments))))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, max(0, (c - m) / d), min(1, (c + m) / d))


def newcombe(ka, na, kb, nb, z=1.96):
    pa, la, ua = wilson(ka, na, z)
    pb, lb, ub = wilson(kb, nb, z)
    d = pa - pb
    return (d, d - math.sqrt((pa - la) ** 2 + (ub - pb) ** 2),
            d + math.sqrt((ua - pa) ** 2 + (pb - lb) ** 2))


def analyze(citizens, binds, posts, comments):
    reg = {c['handle']: c['created_at'] for c in citizens
           if c.get('created_at') and COHORT_START <= c['created_at'] < COHORT_END}
    delays = sorted((binds[h] - reg[h], h) for h in reg if h in binds)
    gap = max(((delays[i][0] / delays[i - 1][0], delays[i - 1][0], delays[i][0])
               for i in range(1, len(delays)) if delays[i - 1][0] > 0))
    top = gap[2]
    acts = {}
    for a, t in posts + comments:
        acts.setdefault(a, []).append(t)
    arms = {h: ('none' if h not in binds else 'door' if binds[h] - r < top else 'sought')
            for h, r in reg.items()}

    def retained(h, d0=8 * DAY, d1=15 * DAY):
        r = reg[h]
        return any(r + d0 <= t < r + d1 for t in acts.get(h, []))

    out = {'cohort_n': len(reg), 'gap_ms': [gap[1], gap[2]], 'gap_ratio': gap[0], 'arms': {}}
    for arm in ('door', 'sought', 'none'):
        m = [h for h in reg if arms[h] == arm]
        k = sum(1 for h in m if retained(h))
        p, lo, hi = wilson(k, len(m))
        out['arms'][arm] = {'n': len(m), 'k': k, 'rate': p, 'ci': [lo, hi]}
    r = out['arms']
    for a, b in (('door', 'sought'), ('door', 'none'), ('sought', 'none')):
        d, lo, hi = newcombe(r[a]['k'], r[a]['n'], r[b]['k'], r[b]['n'])
        out[f'diff_{a}_{b}'] = {'d': d, 'ci': [lo, hi]}
    # falsifier cut: days 1-7 writers only
    early = {h for h in reg if any(reg[h] <= t < reg[h] + 7 * DAY for t in acts.get(h, []))}
    fc = {}
    for arm in ('door', 'sought'):
        m = [h for h in reg if arms[h] == arm and h in early]
        k = sum(1 for h in m if retained(h))
        p, lo, hi = wilson(k, len(m))
        fc[arm] = {'n': len(m), 'k': k, 'rate': p, 'ci': [lo, hi]}
    d, lo, hi = newcombe(fc['door']['k'], fc['door']['n'], fc['sought']['k'], fc['sought']['n'])
    out['falsifier_cut'] = {**fc, 'diff_door_sought': {'d': d, 'ci': [lo, hi]}}
    return out


def main():
    os.makedirs(STATE, exist_ok=True)
    if '--offline' in sys.argv:
        citizens = json.load(open(f'{STATE}/citizens_all.json'))
        binds = json.load(open(f'{STATE}/binds.json'))
        posts = json.load(open(f'{STATE}/activity_posts.json'))
        comments = json.load(open(f'{STATE}/activity_comments.json'))
    else:
        citizens = walk_citizens()
        json.dump(citizens, open(f'{STATE}/citizens_all.json', 'w'))
        binds = walk_events()
        json.dump(binds, open(f'{STATE}/binds.json', 'w'))
        posts, comments = walk_changes()
        json.dump(posts, open(f'{STATE}/activity_posts.json', 'w'))
        json.dump(comments, open(f'{STATE}/activity_comments.json', 'w'))
    res = analyze(citizens, binds, posts, comments)
    json.dump(res, open(f'{STATE}/results.json', 'w'), indent=1)
    for arm, v in res['arms'].items():
        print(f"{arm}: n={v['n']} k={v['k']} rate={v['rate']:.3f} CI [{v['ci'][0]:.3f},{v['ci'][1]:.3f}]")
    for k_, v in res.items():
        if k_.startswith('diff_'):
            print(f"{k_}: {v['d']:+.3f} CI [{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}]")
    fc = res['falsifier_cut']
    print('falsifier cut:', fc['diff_door_sought'])


if __name__ == '__main__':
    main()
