"""Contact frame of every arm clip of the spec against the SEATED magazine (the tracks hold it seated until release).
Contact = first (fractional) frame where a surface sample of the partner gun enters the magazine box.
Per clip and partner gun: contact frame, closest approach over f20-30 against the seated magazine and against the
vanilla 'reload' pose of that frame (mm, + = penetration), depth at f24-27.

usage: mag_contacts.py [--spec <spec.json>] [--clips <dir>] [--out <rows.json>] [--jobs n] [<set>_<pick> ...]
  --clips: read <body>/<file> of every spec clip from that folder.
  default out: <authoring work>/magtrack/contacts.json
"""
import os, sys, json, collections
import numpy as np
import mag_geom as g
from mag_geom import app, box_signed, partner_pts, G0


def signed(arm, sh, st, P, f, Gm=None):
    """deepest sample of the striker's points P in the magazine box at frame f: (depth m, index)"""
    M = np.linalg.inv(arm.W(sh, f) @ (G0 if Gm is None else Gm)) @ arm.W(st, f)
    d = box_signed(app(M, P)); k = int(np.argmax(d)); return d[k], k


def contact(arm, sh, st, P, lo=14, hi=36):
    """(first frame with a sample inside the box, its index), or (None, None)"""
    prev = None
    for f in range(lo, hi + 1):
        d, k = signed(arm, sh, st, P, f)
        if d >= 0:
            if prev is None: return float(f), k
            a, b = f - 1.0, float(f)
            for _ in range(14):
                m = (a + b) / 2
                if signed(arm, sh, st, P, m)[0] >= 0: b = m
                else: a = m
            return b, signed(arm, sh, st, P, b)[1]
        prev = d
    return None, None


def rows(job):
    key, pi, pick, (path, body, sh, st, keys) = job
    arm = g.Arm(path); out = []
    for k in keys:
        P = partner_pts(k)
        fs = np.arange(20, 30.01, 0.25)
        seat = [signed(arm, sh, st, P, f)[0] for f in fs]
        van = [signed(arm, sh, st, P, f, g.vanilla_G('reload', int(round(f))))[0] for f in fs]
        c, _ = contact(arm, sh, st, P, lo=20, hi=32)
        out.append(dict(set=key, pick=pi, name=pick, clip=os.path.basename(path)[:-4], body=body, partner=k,
                        seat_mm=round(max(seat) * 1000, 1), seat_f=float(fs[int(np.argmax(seat))]),
                        van_mm=round(max(van) * 1000, 1), van_f=float(fs[int(np.argmax(van))]), contact=c,
                        depth_mm={f: round(float(signed(arm, sh, st, P, f)[0]) * 1000, 1) for f in (24, 25, 26, 27)}))
    return out


def measure(spec, clips_dir=None, picks=None, jobs=1):
    """rows of every clip and partner gun of the spec (picks: [(set key, pick index)] to limit)"""
    todo = [(k, pi, g.pick_name(e), c) for k in g.spec_keys(spec) for pi, e in enumerate(spec[k])
            if not picks or (k, pi) in picks for c in g.spec_cases(spec, k, pi, clips_dir)]
    if jobs > 1:
        from multiprocessing import Pool
        with Pool(jobs) as pool: res = pool.map(rows, todo)
    else:
        res = [rows(j) for j in todo]
    return [r for rs in res for r in rs]


def by_clip(rs):
    """{(body, clip): {partner: row}}"""
    out = collections.defaultdict(dict)
    for r in rs: out[(r['body'], r['clip'])][r['partner']] = r
    return out


def report(rs, K=25):
    grp = collections.defaultdict(list)
    for r in rs: grp[(r['set'], r['name'])].append(r)
    for (key, name), v in grp.items():
        cs = [r['contact'] for r in v if r['contact'] is not None]
        miss = [r['clip'] + '/' + r['partner'] for r in v if r['contact'] is None]
        rng = f'{min(cs):6.2f} max {max(cs):6.2f}' if cs else '     - max      -'
        print(f'{key:11s} {name:10s} n{len(v):3d} contact min {rng}  miss {len(miss)} {miss[:4]}')
        for r in v:
            if r['contact'] is not None and abs(r['contact'] - K) > 0.5:
                print(f"      off: {r['body']} {r['clip']:36s} {r['partner']:12s} {r['contact']:6.2f} depth {r['depth_mm']}")


if __name__ == '__main__':
    a = sys.argv[1:]
    spec = g.load_spec(g.common.opt(a, '--spec')); cdir = g.common.opt(a, '--clips')
    out = g.common.opt(a, '--out') or g.common.work('magtrack') + '/contacts.json'
    jobs = int(g.common.opt(a, '--jobs', 6))
    rs = measure(spec, cdir, [g.find_pick(spec, x) for x in a], jobs)
    json.dump(rs, open(out, 'w'), indent=1)
    for r in rs:
        print(f"{r['set']:11s} {r['clip']:36s} {r['body']} {r['partner']:13s} seated {r['seat_mm']:6.1f}@{r['seat_f']:5.2f}  "
              f"vanilla {r['van_mm']:6.1f}@{r['van_f']:5.2f}  contact {r['contact']}")
    report(rs)
    print('wrote', out)
