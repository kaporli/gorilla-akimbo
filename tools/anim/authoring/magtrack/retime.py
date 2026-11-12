"""Local re-time (K-7 to K+7) of the arm clips whose hit lands outside [K-0.3, K+0.05] (contact against the SEATED
magazine). The pose at the measured contact is moved to the target frame; K-1 to K+1 keep their original speed (the hit
itself is not slowed), the shift is eased in over K-7 to K-1 and out over K+1 to K+7. Everything outside is unchanged.
Category clips: the window is fitted to all partner guns that touch (contact within K-1.5 to K+0.6); if they spread
wider than the window, the spread is centred on its middle.

usage: retime.py <in clips dir> <out clips dir> [--rows <contacts.json>] [--shifts <retime.json>] [--spec <spec.json>] [--dry]
  Reads <in>/<body>/<clip>.glb, writes the re-timed clips to <out>/<body>/ and <out>/retime.json. Clips that need no
  shift are not written. --rows: contact rows of mag_contacts.py for the in dir (measured here when left out).
  --shifts: apply the shifts of an earlier retime.json {"<body>/<clip>": [shift, ...]} instead of measuring.
"""
import os, sys, json, collections
import numpy as np
import mag_geom as g
import mag_contacts
from mag_geom import Glb, FPS
from mag_flight import GATES
from fk import slerp

LO, HI = -0.3, 0.05           # target window of the contact frame, relative to K


def bump(f, K):
    def ss(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)
    if f <= K - 7 or f >= K + 7: return 0.0
    if f < K - 1: return ss((f - (K - 7)) / 6)
    if f <= K + 1: return 1.0
    return 1 - ss((f - (K + 1)) / 6)


def shifts(rows, K=25):
    """{(body, clip): (shift in frames, first contact, last contact, touching guns)} of the clips to re-time"""
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['body'], r['clip'])].append(r)
    out = {}; lo, hi = K + LO, K + HI
    for (body, clip), rs in sorted(by.items()):
        cs = [r['contact'] for r in rs if r['contact'] is not None and K + GATES['touch'][0] <= r['contact'] <= K + GATES['touch'][1]]
        if not cs: continue
        lo_d, hi_d = lo - min(cs), hi - max(cs)
        if lo_d <= hi_d:
            d = 0.0 if lo_d <= 0 <= hi_d else (lo_d if lo_d > 0 else hi_d)
        else:
            d = (lo + hi) / 2 - (min(cs) + max(cs)) / 2
        if abs(d) > 1e-3:
            out[(body, clip)] = (round(d, 3), min(cs), max(cs), len(cs))
    return out


def sample(times, vals, t, rot):
    t = min(max(t, times[0]), times[-1]); i = int(np.searchsorted(times, t, side='right') - 1); i = min(i, len(times) - 2)
    a = (t - times[i]) / (times[i + 1] - times[i])
    v0, v1 = vals[i], vals[i + 1]
    if rot:
        if np.dot(v0, v1) < 0: v1 = -v1
        return slerp(v0, v1, a)
    return v0 * (1 - a) + v1 * a


def retime(path, d, out, K=25):
    """Output frame f shows the input at f - d * bump(f): the contact pose moves later by d."""
    gl = Glb(path); an = gl.j['animations'][0]
    for s in an['samplers']:
        ti = gl.acc(s['input']); vo = gl.acc(s['output'])
        if vo.ndim == 1 or len(ti) < 2: continue
        rot = vo.shape[1] == 4
        new = vo.copy()
        for k, t in enumerate(ti):
            f = t * FPS; w = bump(f, K)
            if w > 0: new[k] = sample(ti, vo, (f - d * w) / FPS, rot)
        # write back in place (same accessor size)
        a = gl.j['accessors'][s['output']]; v = gl.j['bufferViews'][a['bufferView']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        gl.bin[off:off + new.astype(np.float32).nbytes] = new.astype(np.float32).tobytes()
    gl.save(out)


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    spec = g.load_spec(opt(a, '--spec')); rows = opt(a, '--rows'); given = opt(a, '--shifts'); dry = '--dry' in a
    if dry: a.remove('--dry')
    if len(a) != 2: raise SystemExit(__doc__)
    src, dst = a
    if os.path.abspath(src) == os.path.abspath(dst): raise SystemExit('in and out folder are the same')
    Ks = {e['K'] for k in g.spec_keys(spec) for e in spec[k]}
    if len(Ks) != 1: raise SystemExit('the picks of the spec have different release frames')
    K = Ks.pop()
    if given:
        sh = {tuple(k.split('/')): tuple(v) for k, v in json.load(open(given)).items()}
    else:
        sh = shifts(json.load(open(rows)) if rows else mag_contacts.measure(spec, src, jobs=6), K)
    for (body, clip), (d, c0, c1, n) in sh.items():
        print(f'{body} {clip:36s} contacts {c0:6.2f}..{c1:6.2f} (n{n})  shift {d:+.3f} -> {c0 + d:6.2f}..{c1 + d:6.2f}')
    if not dry:
        for (body, clip), (d, c0, c1, n) in sh.items():
            os.makedirs(f'{dst}/{body}', exist_ok=True)
            retime(g.common.need(f'{src}/{body}/{clip}.glb'), d, f'{dst}/{body}/{clip}.glb', K)
        json.dump({f'{b}/{c}': v for (b, c), v in sh.items()}, open(dst + '/retime.json', 'w'), indent=1)
        print('wrote', len(sh), 'clips to', dst)
