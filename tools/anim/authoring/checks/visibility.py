"""R9 reload visibility: where the magazine well and the reloading hand are on the game's first-person screen at the
release and the insert, in each stance the clip plays in.

Camera (game data, checks.draft.r9.camera): eye = the rig's fpp camera joint (static in every clip), horizontal fov =
the game's FieldOfView setting (16:9). Not the review camera of checks.raised (that one is a fit, kept for the pose rule).
Stances: raised = the clip alone (it starts and ends in the raised idle). lowered = the game graph's blend into Reload,
0.2 s linear from friendly_idlepose (transition Ready to Reload), then the clip (absolute pose, not relative to the
stance); the clip does not know the stance. Reload clip, right arm: RightHand and the gun's mag_slot.
Windows (frames, from the clip's own track plan): release = release .. free_from (the magazine leaves the well),
insert = appear .. seated (the fresh magazine travels to the well).

usage: visibility.py --gun <id> --clips <dir> --low <dir> [--picks ST32B,ST38B,ST40B] [--bodies pma,pwa] [--names empty_reload,reload]
                     [--sides right,left] [--json out.json]
"""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import common
for _p in (os.path.join(common.HERE, 'raised'), os.path.join(common.HERE, 'lowered'), os.path.join(common.HERE, 'reload')):
    if _p not in sys.path: sys.path.append(_p)
import numpy as np
import rpose as R                       # raised/rpose.py: screen(), place(), base()
from lpose import Rig, Glb, blend, ease, FPS
from wclip import TClip
import gungeo

CFG = common.manifest.load()['checks']['draft']['r9']
_rigs = {}


def rig(path):
    if path not in _rigs: _rigs[path] = Rig(Glb(path))
    return _rigs[path]


def camera(body):
    """(eye, half horizontal fov in radians): the rig's camera joint in the base set, and the game setting."""
    r, _ = R.base(body)
    return r.world(r.sample('idlepose_shoulder', 0))[r.idx[CFG['camera']['eye_joint']]][0], math.radians(CFG['camera']['hfov_169'] / 2)


SEAT_FALLBACK = {}


def seat(gun):
    """mag_slot of the gun in gun axes (where the magazine sits), from its weapon anim set."""
    b = gungeo.wanim(gun, 'base1')
    if b is None or 'mag_slot' not in Glb(b).names: b = gungeo.wanim(gun, 'rcv1')
    if b is None or 'mag_slot' not in Glb(b).names:      # a gun with no magazine well (pump or break shotgun): the point the discard leaves from, set by reload/discard.py (SEAT_FALLBACK[gun id], gun axes)
        return SEAT_FALLBACK[gun['id']]
    gb = Glb(b); an = [a['name'] for a in gb.j['animations']]
    return TClip(gb, 'reload' if 'reload' in an else an[0]).world(0)[gb.names.index('mag_slot')][0]


def poses(clip_glb, clip, low_glb, side, stance):
    """Local pose per frame of what the graph plays: the clip alone (raised) or the clip blended in from the lowered idle."""
    r = rig(clip_glb); n = int(round(r.duration(clip) * FPS)) + 1
    C = [r.sample(clip, f / FPS) for f in range(n)]
    if stance == 'raised': return r, C
    l = rig(low_glb); assert l.names == r.names
    FR = [l.sample('friendly_idlepose' + ('_l' if side == 'left' else ''), f / FPS) for f in range(int(round(l.duration('friendly_idlepose') * FPS)) + 1)]
    k = int(round(CFG['blend_in_s'] * FPS)); other = R.arm_joints('Left' if side == 'right' else 'Right')
    out = []
    for f in range(n):
        P = blend(FR[f % (len(FR) - 1)], C[f], ease('Linear', min(1.0, (f + 1) / k))) if f < k else list(C[f])
        for j in other: P[j] = FR[f % (len(FR) - 1)][j]       # the other arm is the other hand's own machine: it stays lowered
        out.append(P)
    return r, out


def margin(P, eye, hh):
    """Per point: distance inside the frame edge as a share of the half frame (negative: outside or behind the camera)."""
    sx, sy, ok = R.screen(P, eye, hh)
    return np.where(ok, 1 - np.maximum(np.abs(sx), np.abs(sy)), -1.0)


def measure(gun, body, side, clip_glb, track, clip, low_glb, stance):
    S = 'Right' if side == 'right' else 'Left'
    r, L = poses(clip_glb, clip, low_glb, side, stance)
    eye, hh = camera(body); st = seat(common.gun(gun))
    well, hand = [], []
    for p in L:
        W = r.world(p); well.append(R.place(W[r.idx['Weapon' + S]], st[None])[0]); hand.append(W[r.idx[S + 'Hand']][0])
    mw, mh = margin(np.array(well), eye, hh), margin(np.array(hand), eye, hh)
    pl = track['plan']; wins = {'release': (track['release'], track.get('free_from', track['release'])),
                                'insert': (pl.get('appear', pl['seated']), pl['seated'])}
    out = {'frames': len(L), 'well': [round(float(x), 3) for x in mw], 'hand': [round(float(x), 3) for x in mh]}
    for k, (a, b) in wins.items():
        idx = list(range(a, b + 1))
        out[k] = {'window': [a, b], 'n': len(idx), 'in_view': int(sum(mw[f] > 0 for f in idx)), 'worst_margin': round(float(min(mw[f] for f in idx)), 3),
                  'hand_in_view': int(sum(mh[f] > 0 for f in idx)), 'worst_hand': round(float(min(mh[f] for f in idx)), 3)}
    return out


def run(gun, clips, low, picks, bodies, names, sides, stances=('raised', 'lowered')):
    rows = []
    for body in bodies:
        for pick in picks:
            for nm in names:
                for side in sides:
                    stem = f'{clips}/{body}/{gun}_{side}_{pick}_{nm}'
                    if not os.path.exists(stem + '.glb'): continue
                    track = json.load(open(stem + '_track.json'))
                    for stance in stances:
                        m = measure(gun, body, side, stem + '.glb', track, 'reload_draft', f'{low}/{body}/lowered_{common.gun(gun)["lowered"]["pose"]}.glb', stance)
                        rows.append({'clip': f'{pick}_{nm}', 'body': body, 'side': side, 'stance': stance, **m})
    return rows


def verdict(rows):
    """R9: in each window the lowered stance shows the magazine well in as many frames as the raised stance of the same clip, and
    its worst margin is not smaller (the margins are rounded to 0.001). Absolute 'inside the frame' is not the rule: the production gate
    puts the release and the insert out of view on purpose (the magazine must be off screen from hide_start), so every shipped clip is
    out of view there in the raised stance too. Returns [(clip, body, side, window, raised, lowered, ok)]."""
    by = {(x['clip'], x['body'], x['side'], x['stance']): x for x in rows}; out = []
    for (c, b, sd, st), x in by.items():
        if st != 'lowered': continue
        r = by[(c, b, sd, 'raised')]
        for w in ('release', 'insert'):
            ok = x[w]['in_view'] >= r[w]['in_view'] and x[w]['worst_margin'] >= r[w]['worst_margin'] - 0.001
            out.append((c, b, sd, w, r[w], x[w], ok))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    js = common.opt(a, '--json'); gun = common.opt(a, '--gun'); csv = lambda k, d: (common.opt(a, k) or d).split(',')
    rows = run(gun, common.opt(a, '--clips'), common.opt(a, '--low'), csv('--picks', 'ST32B,ST38B,ST40B'), csv('--bodies', 'pma,pwa'),
               csv('--names', 'empty_reload,reload'), csv('--sides', 'right,left'))
    print('clip, body, side, stance: release in view / n (worst margin), insert in view / n (worst margin)   margin = share of the half frame inside the edge')
    for x in rows:
        print(f'{x["clip"]:22s} {x["body"]} {x["side"]:5s} {x["stance"]:8s} release {x["release"]["in_view"]}/{x["release"]["n"]} ({x["release"]["worst_margin"]:+.2f})'
              f'  insert {x["insert"]["in_view"]}/{x["insert"]["n"]} ({x["insert"]["worst_margin"]:+.2f})')
    v = verdict(rows); bad = [x for x in v if not x[6]]
    print(f'R9 parity (lowered vs raised): {len(v) - len(bad)}/{len(v)} pass')
    for x in bad: print('FAIL', x[:4], 'raised', x[4], 'lowered', x[5])
    if js: json.dump(rows, open(js, 'w'))
    sys.exit(1 if bad else 0)
