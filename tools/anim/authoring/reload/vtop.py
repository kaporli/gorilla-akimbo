"""SMG TOP family, round 6 (vanilla): one-handed reload drafts translated from the game's own reloads. Warden, take B, right hand, male V, empty reload.

Sources (vref.REFS): the Lexington dual-wield reloads (one-handed in the game itself) and the Warden's own two-handed ones. What a vanilla clip gives
(measured, vref.py): the gun's path (WeaponRight, per frame), when the magazine leaves (out), when the fresh one is home (seated), when the cocking
device moves, the magazine's exit axis and speed. Nothing else: the game's fresh magazine appears in the left hand, which never goes to a pouch.

Translation rule (see README "Vanilla reloads"):
  time      one budget per take (77 frames): the clip's beats map by the same ratio, (0, out, seated, last) to (0, rel, seat, 76); rel >= 18 (wind-up room from the lowered
            pose), seat - rel >= 16, hit - seat >= 14, hit <= 61, back = hit + 2, idle = hit + 9 (the take B beats of r3lib).
  path      the gun's world increments from the clip's first frame, applied to the Warden's idle (rotation about its own origin, the hand's attach point).
  strip     the left hand pulled the magazine. If the kept path alone frees it by the well model within STRIP_FREE frames of the release (no left hand needed), it stays.
            Else the arm substitutes the inertia release of ST38 to ST63: the wind-up, then a drive along the exit axis of D = n v / 1.875 metres (n frames, v = the clip's
            exit speed per retimed frame, 1.875 = peak over mean of the drive profile), stopped dead on the release frame at the clip's own pose of the gun on that frame.
  insert    the left hand brought the fresh magazine. One-handed source: the gun's own path goes to the place it was reloaded at and the magazine waits there (still).
            Two-handed source: the game has no magazine source, so the belt rig of the lowered standard (belt_tl), as ST54.
  rack      the left hand worked a part. The part's measured direction in gun axes picks the standard rack: backward motion, the start of the gun's move throws it (yank);
            else the dead stop does (upper).

pvan2 (2026-11-24, owner feedback on SV10/SV13/SV14): options in vsolve_<id>.json as a dict (OPTS): roll 0 = the gun is not turned over at the rig (the hidden spin and its unroll are dropped), dx dy dz and pitch move
  the rig, sa advances the seat, ms is the share of the rise-to-held span at which the gun reaches the mid pose (slower rise), lift raises the stop for the discard; wait is no longer used (0): the gun
  goes down as soon as it has stopped and the magazine falls in view. Rules measured by checks/reloadrules.py (speed caps, dead pause, hidden-phase spin, two-gun clearance).

usage: vtop.py list | build [ids] [--jobs n] | stats | gates
"""
import os, sys, math, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r3lib, r2lib as R2, author, prod, top3, top4, top5, vref, lowover
from r3lib import seat, PUNCH
from r3lib import rack
from top3 import mag, AXES
from fk import qmul, qinv, slerp

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'SV'
STATIONS = dict(top4.STATIONS)
PARAMS = {}
N = 77
STRIP_FREE = 6        # frames after the release in which the kept path must free the magazine (well model) for the vanilla motion to count as the release
DRIVE_N = 6           # frames of the arm's drive
PEAK_OVER_MEAN = 1.875
_cur = {}
AFR = 0.55           # the approach to the rig arrives this share of the way from the release to the seat (the shipped beats: 0.59)
SOLVE_GRID = [(1.0, 1.0, 0.55), (1.1, 1.0, 0.55), (1.0, 1.0, 0.45), (1.1, 1.2, 0.45), (1.2, 1.3, 0.45), (1.2, 1.3, 0.35), (1.3, 1.5, 0.35), (1.45, 1.5, 0.35)]     # (amplitude of the kept path, drive length, approach share) tried in order by `solve`


def _file(rid):
    try: return json.load(open(f'{renv.OUT}/vsolve_{rid}.json'))
    except (OSError, ValueError): return None


def _solve(rid):
    """(amp, drive scale, approach share) of a draft: 1, 1, AFR unless `solve` (R8 and R5 floors are minimums on speed and path: the travel is lengthened and the approach made quicker, never shortened) wrote another.
    vsolve_<id>.json is a list (amp, drive, approach, stop lift in metres, frames the gun waits at the stop) or a dict with those keys (amp, drive, afr, lift, wait) and the options of _opts."""
    j = _file(rid)
    if j is None: return (1.0, 1.0, AFR, 0.0, 0.0)
    if isinstance(j, dict): return (j.get('amp', 1.0), j.get('drive', 1.0), j.get('afr', AFR), j.get('lift', 0.0), j.get('wait', 0.0))
    v = tuple(j); return v + (0.0,) * (5 - len(v))


OPTS = {'roll': 180.0, 'dy': 0.0, 'dx': 0.0, 'dz': 0.0, 'sa': 0, 'pitch': -40.0, 'ms': 0.5}


def _opts(rid):
    """Options of the pvan2 round (vsolve_<id>.json as a dict): roll and pitch (deg) of the belt station (180 and -40: the gun upside down at the rig, as shipped; roll 0: no flip, the hidden spin is dropped),
    dx dy dz (m) the station moved, sa: frames the seat is advanced from the vanilla timing (the second half gets them), ms: share of the rise-to-held span at which the gun reaches the mid pose (0.5: as r3lib)."""
    d = dict(OPTS); j = _file(rid)
    if isinstance(j, dict): d.update({k: j[k] for k in OPTS if k in j})
    return d


def beats(r, afr=AFR, sa=0, ms=0.5):
    """The take B beats of a reference: its events mapped by the budget ratio (module doc)."""
    V = r['frames']; k = (N - 1) / (V - 1)
    rel = max(18, int(round(r['out'] * k))); seat_ = min(max(int(round(r['seated'] * k)), rel + 16), 47); seat_ = max(rel + 16, seat_ - int(sa))
    h = r.get('handle'); hit = int(round(h['window'][0] * k)) if h and r['gun'] != 'lexington' else 61
    hit = min(max(hit, seat_ + 14), 61); held = hit - 4; rise = seat_ + 1
    return {'N': N, 'cue': 7, 'wind': 8, 'top': rel - 6, 'chop': rel - 5, 'rel': rel, 'dep': rel + 3, 'arr': rel + int(round(afr * (seat_ - rel))), 'slam': seat_ - 6, 'seat': seat_,
            'rise': rise, 'mid': (rise + held) // 2 if ms == 0.5 else rise + int(round(ms * (held - rise))), 'held': held, 'hit': hit, 'back': hit + 2, 'idle': hit + 9}


def anchors(r, B):
    return [0, B['rel'], B['seat'], N - 1], [0, r['out'], r['seated'], r['frames'] - 1]


def prepare(pick):
    """Called by the builders before the context is made: the beats of this pick into the take's beat table."""
    r = vref.ref(pick); B = beats(r, _solve(pick)[2], _opts(pick)['sa'], _opts(pick)['ms']); R2.BEATS[TAKE].clear(); R2.BEATS[TAKE].update(B); _cur['pick'] = pick; _cur['ref'] = r


def keys_of(c, r, B):
    """Per draft frame: key position offset and euler angles of the kept path (the clip's world increments on the idle)."""
    T = np.array(r['T']); Q = np.array(r['Q']); xs, ys = anchors(r, B); out = []
    for f in range(N):
        v = float(np.interp(f, xs, ys)); i = min(int(v), len(T) - 2); w = v - i
        out.append((T[i] * (1 - w) + T[i + 1] * w, slerp(Q[i], Q[i + 1], w)))
    p0, q0 = out[0]; P = np.zeros((N, 3)); R = np.zeros((N, 3)); G = []
    for f, (p, q) in enumerate(out):
        d = qmul(q, qinv(q0)); Qw = qmul(d, c.q0); P[f] = p - p0; R[f] = lowover.euler_xyz(qmul(qinv(c.q0), Qw)); G.append((c.g0 + P[f], Qw))
    return P, R, G


def frees(c, G, B):
    """Frames from the release to the magazine being free on the kept path (well model), or None if it never leaves."""
    plan = {'release': B['rel'], 'mode': 'well', 'out_len': 0.08, 'axis_check_m': 0.09, 'tumble': 2, 'appear': B['rel'] + 10, 'seated': B['seat'], 'floor': 0.08, 'fresh': {'mode': 'still'}}
    try: t = R2.track(c, G, plan)
    except ValueError: return None
    return t['free_from'] - B['rel']


def fill(tl, P, R, f0, f1, p0, r0, a):
    """Kept path on frames f0..f1 (arrays written directly: the vanilla speed profile, no eases). In a lowered build (start pose p0, r0) it comes up from there by frame a."""
    for f in range(f0, f1 + 1):
        w = lowover.w_start(f, 0, a) if np.any(p0) or np.any(r0) else 0.0
        tl.P[f] = w * p0 + (1 - w) * P[f]; tl.R[f] = w * r0 + (1 - w) * R[f]
    tl.f = f1; tl.p = tl.P[f1].copy(); tl.r = tl.R[f1].copy(); tl.rf = f1


def rack_kind(r):
    h = r.get('handle') or {}
    return 'yank' if h.get('dir') and h['dir'][2] > 0.5 and r['gun'] != 'lexington' else 'upper'


def make(rid):
    def fn(c, tl):
        r = _cur['ref'] if _cur.get('pick') == rid else vref.ref(rid); B = c.B; rel = B['rel']
        P, R, G = keys_of(c, r, B); amp, dsc, _, lift_y, wait = _solve(rid); P = P * amp; G = [(g[0] + (amp - 1.0) * (g[0] - c.g0), g[1]) for g in G]; p0, r0 = tl.p.copy(), tl.r.copy(); one = r['one_handed']
        free = frees(c, G, B); tl.mark('cue', 3)
        if one and free is not None and free <= STRIP_FREE:
            # one-handed source: the path as is until the gun is at the place it was reloaded at, then the standard approach, seat and rack
            k0 = B['slam'] - 6; fill(tl, P, R, 0, k0, p0, r0, rel - 7)
            nm = 'v_' + rid; prod.STATION[nm] = (tuple(c.g0 + P[B['seat']] - c.hips), tuple(R[B['seat']]))
            c.P[nm + '_rot'] = tuple(R[B['seat']])
            seat(c, tl, nm, d=0.15, dep=k0, arr=B['slam'] - 1); rack(c, tl, rack_kind(r))
            return mag(c, fresh={'mode': 'still'}, appear=B['slam'] - 8)
        # strip substitution (the kept path does not free the magazine, or the left hand pulled it): inertia release, then the belt rig
        k0 = max(1, rel - 11 - 2); fill(tl, P, R, 0, k0, p0, r0, rel - 7)
        v = (r.get('exit_cm_f') or 5.0) * (r['frames'] - 1) / (N - 1)      # cm per draft frame
        D = DRIVE_N * v / 100.0 / PEAK_OVER_MEAN         # metres: the magazine leaves at the gun speed on the stop, the peak of the drive = 1.875 D / n = v
        D = min(max(D, 0.12), 0.34) * dsc
        e_w = np.array(AXES['exit']); sr = R[rel]; stop = P[rel] + np.array([0.0, lift_y, 0.0])
        tl.hold(k0); top5.arm_release(c, tl, stop, sr, sr + np.array((6.0, 0.0, -4.0)), drop=D, first=k0, arrive=rel - DRIVE_N - 1, wind_hold=rel - 5)
        tl.mark('strip_D_cm', int(round(D * 100)))
        dep = rel + 4 + int(wait); o = _opts(rid); st = 'belt_tl'
        if o['roll'] != 180.0 or o['pitch'] != -40.0 or o['dx'] or o['dy'] or o['dz']:      # the rig with the roll changed (0: the gun is not turned over, no hidden spin) or moved
            bp, br = prod.STATION['belt_tl']; st = 'bv_' + rid; prod.STATION[st] = ((bp[0] + o['dx'], bp[1] + o['dy'], bp[2] + o['dz']), (o['pitch'], br[1], o['roll'])); prod.PWA_DROP[st] = prod.PWA_DROP.get('belt_tl', -0.025)
        seat(c, tl, st, dep=dep, arr=max(B['arr'], dep + 5)); rack(c, tl, rack_kind(r))
        return mag(c, fresh={'mode': 'still'})
    fn.__doc__ = f'Vanilla {rid}.'
    return fn


PICKS = {rid: (f'{lab} {clip}', make(rid)) for rid, (g, clip, lab) in vref.REFS.items()}
MECH = {rid: f'Translated from the game clip {vref.REFS[rid][0]} {vref.REFS[rid][1]}.' for rid in PICKS}


def build(F, pick, quiet=False):
    prepare(pick); return r3lib.build(F, pick, quiet)


def evaluate(rid):
    """Fail lists of the built draft (gate, draft check) for one id."""
    d = renv.OUT + '/clips/pma'; stem = f'{d}/warden_right_{rid}B_empty_reload'
    ck = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/checks/draftcheck.py'
    subprocess.run([sys.executable, '-B', ck, '--family', 'top', '--take', 'B', stem + '.json'], capture_output=True, text=True, cwd=os.path.dirname(ck))
    g = json.load(open(stem + '_gate.json'))['fails']; dc = json.load(open(stem + '_draft.json'))['fails']
    return g, dc


RELIEF_GRID = [(0.85, 1.0, 0.45), (0.7, 1.0, 0.45), (0.55, 1.0, 0.45)]      # after a geometry fail at amplitude 1: the kept path shortened until the body, reach, wrist and shoulder gates pass (the floors are then checked as they are)


def solve(ids):
    """For each id, the first (amp, drive) of SOLVE_GRID whose build passes the gate and the draft checks; else the one with the fewest fails.
    A geometry fail (the gun in the body, the wrist, the shoulder or the cover) at amplitude 1 ends the search: more travel only makes it worse."""
    geo = ('body', 'wrist', 'shoulder', 'cover', 'reach')
    for rid in ids:
        path = f'{renv.OUT}/vsolve_{rid}.json'; best = None; grid = list(SOLVE_GRID); k = 0
        while k < len(grid):
            amp, dsc, afr = grid[k]; k += 1
            json.dump([amp, dsc, afr], open(path, 'w'))
            r = subprocess.run([sys.executable, '-B', os.path.abspath(__file__), 'build', rid], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            if r.returncode: print(rid, amp, dsc, afr, 'build failed', r.stdout[-200:], r.stderr[-300:], flush=True); continue
            g, dc = evaluate(rid); n = len(g) + len(dc); print(rid, amp, dsc, afr, 'gate', g, 'draft', dc, flush=True)
            if best is None or n < best[0]: best = (n, amp, dsc, afr)
            if n == 0: break
            if amp == 1.0 and afr == 0.55 and any(w in x for x in g for w in geo): print(rid, 'geometry fail at amplitude 1: a shorter path is tried instead of a longer one', flush=True); grid = [(amp, dsc, afr)] + RELIEF_GRID; k = 1
        json.dump([best[1], best[2], best[3]] if best else [1.0, 1.0, AFR], open(path, 'w')); json.dump({'id': rid, 'best_fails': best[0] if best else None}, open(f'{renv.OUT}/vsolve_{rid}.result.json', 'w'))


def main(F, argv):
    cmd = argv[0] if argv else 'list'
    if cmd == 'solve':
        solve(argv[1].split(',') if len(argv) > 1 else list(F.PICKS)); return
    if cmd == 'build':
        ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(F.PICKS)
        for p in ids: build(F, p)
    elif cmd == 'list':
        for p, (n, fn) in F.PICKS.items(): print(p, n)
    else: raise SystemExit(__doc__)


if __name__ == '__main__': main(sys.modules[__name__], sys.argv[1:])
