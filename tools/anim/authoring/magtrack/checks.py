"""Checks on the WRITTEN magazine sets (glb from tools/anim/magtrack.py, read back through FK, not the generator) with
the arm clips that play them (male and female, all partner guns / categories). Per pick:
  still        magazine gun-local displacement before release (must be 0)
  scale        scale 1 until hidden, the hidden scale after
  first_move   first moving frame = K + 1
  exit, eye, rise, accel, reversal, reappear, hidden_by, restrike, screen_exit, screen_motion, size: the flight gates
               (mag_flight.py)
  insert_visible, seated_by: the vanilla insertion stays off screen, the magazine is seated again in time
  empty_same, empty_tail: the empty variants equal the reload track and stay seated to the end
  contact      contact frame of the arm clips against the seated magazine vs the release frame K (f20-32)
  touch_gap    clips in which no partner gun touches the magazine: gap of the closest gun at its closest (f20-30)

run(spec, sets_glb_dir, clips_dir=None, bodies=None, thresholds=None) -> [{check, item, value, threshold, unit, ok, note}]

usage: checks.py [--spec <spec.json>] [--clips <dir>] [--sets <dir>] [--bodies pma,pwa] [--baseline]
                 [--baseline-file <file>] [--json <out>] [-v] [<set>_<pick> ...]
  Without --sets the six sets are built from the spec into <authoring work>/magtrack/sets first.
  --clips: read <body>/<file> of every spec clip from that folder (build and checks).
  --baseline: accept the recorded worst values of baseline.json for the items listed there (marked in the note);
  --baseline-file <file>: the same from another file.
  Prints one line per check: pass/fail, worst value, threshold, worst item. Exit code 1 when a check fails.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import mag_geom as g
import mag_flight as fl
from mag_geom import app, onscreen_frac, G0, MAGS, MT, Glb
from mag_contacts import signed

# name: (default, unit, sense). max: value <= threshold, min: value >= threshold, eq: value == threshold.
CHECKS = {
    'still':          (1e-9, 'm', 'max'),
    'scale':          (1e-6, 'scale', 'max'),
    'first_move':     (1, 'frames after K', 'eq'),
    'exit':           (fl.GATES['exit_deg'], 'deg', 'max'),
    'eye':            (fl.GATES['eye_cm'], 'cm', 'min'),
    'rise':           (fl.GATES['rise_cm'], 'cm', 'max'),
    'accel':          (fl.GATES['ay_mm_f2'], 'mm/frame^2', 'max'),
    'reversal':       (0, 'frames', 'max'),
    'reappear':       (0, 'frames', 'max'),
    'hidden_by':      (fl.GATES['hide_after'], 'frames after K', 'max'),
    'restrike':       (fl.GATES['restrike_mm'], 'mm', 'max'),
    'screen_exit':    (fl.GATES['screen_exit_deg'], 'deg', 'max'),
    'screen_motion':  (0, 'clips', 'max'),
    'size':           (fl.GATES['size_ratio'], 'ratio', 'max'),
    'insert_visible': (0, 'screen fraction', 'max'),
    'seated_by':      (g.FRAMES['seated'] + 2, 'frame', 'max'),
    'empty_same':     (1e-5, 'm', 'max'),
    'empty_tail':     (1e-9, 'm', 'max'),
    'contact':        (0.5, 'frames from K', 'max'),
    'touch_gap':      (0, 'mm', 'max'),
}
THRESHOLDS = {k: v[0] for k, v in CHECKS.items()}
BASELINE = os.path.join(g.HERE, 'baseline.json')


def passes(check, value, thr):
    sense = CHECKS[check][2]
    return bool(value <= thr if sense == 'max' else value >= thr if sense == 'min' else value == thr)


def load_baseline(path=None):
    """{(check, item): accepted worst value} of baseline.json, in the form run() takes as thresholds"""
    d = json.load(open(path or BASELINE, encoding='utf-8'))
    return {(c, i): v for c, items in d.items() if not c.startswith('_') for i, v in items.items()}


def run(spec, sets_glb_dir, clips_dir=None, bodies=None, thresholds=None, picks=None):
    """spec: dict or file. thresholds: {check: value} over THRESHOLDS; {(check, item): value} accepts a known worst
    value for one item (the note says so). picks: [(set key, pick index)] to limit."""
    if not isinstance(spec, dict):
        spec = g.load_spec(spec)
    thr = dict(THRESHOLDS)
    over = {k: v for k, v in (thresholds or {}).items() if isinstance(k, tuple)}
    thr.update({k: v for k, v in (thresholds or {}).items() if not isinstance(k, tuple)})
    out = []

    def add(check, item, value, note=''):
        t = thr[check]
        if (check, item) in over and not passes(check, value, t):
            note = (note + '; ' if note else '') + f'baseline, gate {t}'; t = over[(check, item)]
        out.append(dict(check=check, item=item, value=value, threshold=t, unit=CHECKS[check][1],
                        ok=passes(check, value, t), note=note))

    def worst(rs, field, fn=max):
        r = fn(rs, key=lambda r: r[field]); return r[field], f"{r['body']}/{r['clip']}"

    for key in g.spec_keys(spec):
        gl = None
        for pi, e in enumerate(spec[key]):
            if picks and (key, pi) not in picks: continue
            gl = gl or Glb(g.common.need(g.set_glb(sets_glb_dir, key)))
            item = g.pick_id(key, e); K = e['K']; n96 = g.FRAMES['length']
            G, S, n = g.read_track(gl, g.NAMES[pi]); Ge, Se, ne = g.read_track(gl, g.EMPTY[pi])
            add('still', item, float(max(np.abs(G[f] - G0).max() for f in range(0, K + 1))))
            H = max(f for f in range(K, MT.INSERT + 1) if S[f] > 0.5)         # last full-size frame of the flight
            dev = max([abs(S[f] - 1) for f in range(0, H + 1)] + [abs(S[f] - MT.SMALL) for f in range(H + 1, MT.INSERT + 1)]
                      + [abs(S[f] - 1) for f in range(MT.INSERT + 1, n)])
            add('scale', item, float(dev), f'full size to f{H}, {MT.SMALL} to f{MT.INSERT}')
            moving = next((f for f in range(n96) if np.abs(G[f] - G0).max() > 1e-6), n96)
            add('first_move', item, moving - K, f'f{moving}')
            cs = fl.cases(spec, key, pi, clips_dir, bodies)
            rs = fl.evaluate(cs, G, S, full=True)
            for check, field, fn in (('exit', 'exit_deg', max), ('eye', 'eye_cm', min), ('rise', 'rise_cm', max),
                                     ('restrike', 'restrike_mm', max), ('screen_exit', 'screen_exit_deg', max),
                                     ('size', 'size_ratio_max', max)):
                add(check, item, *worst(rs, field, fn))
            ay = [r for r in rs if r['max_ay_mm_f2'] is not None]
            if ay: add('accel', item, *worst(ay, 'max_ay_mm_f2'))
            for check, field in (('reversal', 'rev'), ('reappear', 'reappear')):
                r = max(rs, key=lambda r: len(r[field]))
                add(check, item, len(r[field]), f"{r['body']}/{r['clip']} {r[field][:3]}" if r[field] else '')
            add('hidden_by', item, H - K, f'last full-size frame f{H}' + (f', not before f{fl.GATES["hide_before"]}'
                                                                           if H >= fl.GATES['hide_before'] else ''))
            if H >= fl.GATES['hide_before']: out[-1]['ok'] = False
            mo = [f"{r['body']}/{r['clip']}" for r in rs if r['screen_down_up'] or r['screen_upacc'] or r['screen_hrev']]
            add('screen_motion', item, len(mo), ' '.join(mo[:3]))
            ins, seat = [], []
            for c in cs:
                ins.append((max(onscreen_frac(app(c.W[f] @ G[f], MAGS)) if S[f] > 0.5 else 0.0
                                for f in range(MT.INSERT + 1, g.FRAMES['seated'] + 1)), f'{c.body}/{c.name}'))
            v, who = max(ins); add('insert_visible', item, round(float(v), 3), who if v > 0 else '')
            sb = next((f for f in range(MT.INSERT + 1, n96) if all(np.abs(G[k] - G0).max() < 1e-4 for k in range(f, n96))), n96)
            add('seated_by', item, sb)
            add('empty_same', item, float(max(max(np.abs(G[f] - Ge[f]).max() for f in range(n96)),
                                              max(abs(S[f] - Se[f]) for f in range(n96)))))
            add('empty_tail', item, float(max(np.abs(Ge[f] - G0).max() for f in range(n96, ne))) if ne > n96 else 0.0,
                f'{ne} frames')
            # contact of each clip's partner guns against the seated magazine
            cont = [(abs(v - K), v, f'{c.body}/{c.name}/{k}') for c in cs for k, v in c.contacts.items() if v is not None]
            miss = sum(1 for c in cs for v in c.contacts.values() if v is None)
            if cont:
                d, v, who = max(cont)
                add('contact', item, round(float(d), 2), f'{who} at f{v:.2f}' + (f'; {miss} of {miss + len(cont)} partner guns never touch' if miss else ''))
            gaps = []
            for c in cs:
                if any(v is not None for v in c.contacts.values()): continue
                gap, k = min((-max(signed(c.arm, c.sh, c.st, g.partner_pts(k), f)[0] for f in np.arange(20, 30.01, 0.25)), k)
                             for k in c.contacts)
                gaps.append((round(float(gap) * 1000, 1), f'{c.body}/{c.name}/{k}'))
            v, who = max(gaps) if gaps else (0.0, '')
            add('touch_gap', item, v, f'{len(gaps)} of {len(cs)} clips have no touching gun, widest: {who}' if gaps else '')
    return out


def summary(rows):
    """[(check, ok, worst value, threshold, unit, worst item, note, failed items)] in CHECKS order"""
    out = []
    for check, (_, unit, sense) in CHECKS.items():
        rs = [r for r in rows if r['check'] == check]
        if not rs: continue
        bad = [r for r in rs if not r['ok']]
        pool = bad or rs
        if sense == 'min': w = min(pool, key=lambda r: r['value'])
        elif sense == 'max': w = max(pool, key=lambda r: r['value'])
        else: w = pool[0]
        out.append((check, not bad, w['value'], w['threshold'], unit, w['item'], w['note'], [r['item'] for r in bad]))
    return out


def build_sets(spec, out, clips_dir=None):
    """Write the sets with the build step (tools/anim/magtrack.py) from the spec, clips resolved to files."""
    os.makedirs(out, exist_ok=True)
    p = out + '/spec_resolved.json'
    json.dump(g.resolved(spec, clips_dir), open(p, 'w'), indent=1)
    r = subprocess.run([sys.executable, os.path.join(g.common.ANIM, 'magtrack.py'), p, out], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f'magtrack.py failed:\n{r.stdout}\n{r.stderr}')
    return out


if __name__ == '__main__':
    a = sys.argv[1:]; opt = g.common.opt
    verbose = '-v' in a
    if verbose: a.remove('-v')
    base = None
    if '--baseline' in a:
        a.remove('--baseline'); base = BASELINE
    base = opt(a, '--baseline-file', base)
    spec = g.load_spec(opt(a, '--spec')); cdir = opt(a, '--clips'); sets = opt(a, '--sets')
    bodies = g.common.body_list(opt(a, '--bodies')); js = opt(a, '--json')
    if not sets:
        sets = build_sets(spec, g.common.work('magtrack', 'sets'), cdir); print('built', sets)
    rows = run(spec, sets, cdir, bodies, load_baseline(base) if base else None, [g.find_pick(spec, x) for x in a])
    if js: json.dump(rows, open(js, 'w'), indent=1)
    if verbose:
        for r in rows:
            print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['check']:14s} {r['item']:22s} {r['value']:<10.4g} "
                  f"(threshold {r['threshold']} {r['unit']}) {r['note']}")
    fail = 0
    for check, good, v, t, unit, item, note, bad in summary(rows):
        fail += not good
        print(f"{'pass' if good else 'FAIL'} {check:14s} worst {v:<10.4g} threshold {t:<6g} {unit:16s} {item}"
              + (f' ({note})' if note else '') + (f' | fails: {" ".join(bad)}' if bad else ''))
    sys.exit(1 if fail else 0)
