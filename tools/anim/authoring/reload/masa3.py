"""Round 3, Masamune: ten new one-handed drafts for the third slot of its reload set (today M02, M03, M02).

Heavy rifle: every draft builds take B (prod.TAKES['B']). Motion from rlib2 (moves with a speed profile, counter
move, dead stops with rebound kicks, rotation trailing translation), magazine track from magtrack2 (seated until the
release, short slide, free fall with the gun's velocity and spin; the fresh magazine stands still on the body rig).
Elbow reference prod.POLE_TILT. Start and end: the Masamune's raised idle (weapons.json guns[].raised).

Masamune facts used: magazine 17 cm in front of the grip; the gun's own clip pulls it out slowly f16-f28, seats f79;
empty reload: bolt runs forward f97 (the hit lands on that frame); 109 / 121 frames.

Each draft differs from M02 (shake loose, belt, punch on the bolt) and M03 (hip hook, hip bump, out of view) in how
the magazine leaves, where the fresh one stands, and how the bolt is sent home:
  bolt hits   yank   the rifle is jerked back toward the body starting on the bolt frame (the bolt lags: forward)
              nod    the muzzle is snapped down and stops dead on the bolt frame
              thumb  the hand stays still, the thumb drops the bolt: the rifle jolts on the bolt frame

usage: masa3.py build [ids csv] [--clips reload,empty_reload] [--sides right] [--bodies pma] [--out dir]
       masa3.py list
Output: <out>/<id>/<id>_<clip>[_<side>][_<body>].glb, .json (spec), _track.json, _gate.json, gen_<id>.py
(out default: renv.OUT = ROUND_OUT; rest poses go to <out>/rest/<body>).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
R3 = renv.OUT
import numpy as np
import author, rest, rlib2, magtrack2, prod
from rlib import K
from glb import Glb
from fk import Clip
from prod import L, PUNCH, seat_block

GUN = 'masamune'
_make = rest.make


def _rest(right, left, body='pma', out=None):
    """Start and end pose files go under round 3, never into production/rest."""
    return _make(right, left, body, out or f'{R3}/rest/{body}/rest_{right}_R__{left}_L.glb')


rest.make = _rest

# extra stations (offset of the grip from the hips joint: x to the gun hand's side, y up, z back; search start angles)
STATION = dict(prod.STATION)
# the Masamune's barrel is long: in front of the body the stations sit further forward than the front rifles' stomach
# rig, so the muzzle clears the belt block; behind the hip only as far back as the arm reaches
STATION.update({'thigh': ((0.33, 0.135, -0.10), (-62, -14, 10)),      # front of the outer thigh, a little further out than the belt
                'back': ((0.30, 0.215, 0.05), (-82, -16, 12)),         # beside and behind the hip: muzzle down, well facing back onto the rig
                'stomach_m': ((0.20, 0.17, -0.19), (-45, 8, 0)),       # stomach rig, well forward of the belt
                'stomach_low': ((0.24, 0.15, -0.17), (-50, 4, 2))})


class Ctx(prod.Ctx):
    def station(self, name):
        off, hint = STATION[name]; off = np.array(off) + (prod.PWA_DROP.get(name, 0) if self.body == 'pwa' else 0) * np.array([0, 1, 0])
        pos = self.off(self.hips + np.array(off)); rot = self.natural(pos, self.P.get(name + '_rot', hint), span=14, twist_w=0.15)
        return np.array(pos), rot


# ---------------------------------------------------------------- finishing moves (after the seat)
def bolt(c):
    """The bolt frame of this clip, or None (reload clip: no bolt)."""
    h = c.T.get('handle')
    return h[0] if h else None


READY = {'yank': ((0.004, -0.008, -0.045), (2, 0, -2)), 'nod': ((0.004, 0.006, 0.0), (9, 0, -2)), 'thumb': ((0.0, -0.006, 0.006), (-1, 0, 4)), None: ((0, 0, 0), (0, 0, 0))}


def rise_time(c, tl):
    P = c.P; return max(L(P, 7), int(round(float(np.linalg.norm(tl.p)) * 100 / 4.6 * P['w'])))


def finish3(c, tl, kind):
    """After the seated frame: one decisive rise from the station into a ready pose (the muzzle comes up first, so
    the long stock swings away from the torso), dead stop with a rebound; on the empty reload the bolt hit of `kind`
    lands on the bolt frame; settle into the idle."""
    P = c.P; se = c.T['seated']; b = bolt(c); tl.hold(se + 2); n = rise_time(c, tl)
    if b is None: kind = None
    end = se + 2 + n if b is None else min(se + 2 + n, b - 6); pos, rot = READY[kind]
    tl.to(end, pos, rot, 'drive', antic=P['a'] * 0.8, rprof='settle'); tl.kick(end, (0, 0.010 * P['k'], -0.004), (-2, 0, 0), attack=0.5, release=3.0)
    if kind is None: return
    if kind == 'yank':
        tl.hold(b); tl.to(b + 3, (0.0, 0.006, 0.035), (-3, 0, 1), (1.25, 2.6), rlag=0)            # sharp start on the bolt frame: the bolt lags, runs home
        tl.kick(b, (0, 0.002, 0.012 * P['k']), (-2.5 * P['k'], 0, 0), attack=0.5, release=2.0); tl.kick(b + 3, (0, -0.002, -0.006 * P['k']), (1.5, 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', b); tl.hold(b + 4 + (1 if P['w'] > 1 else 0)); e = b + 4 + L(P, 8); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.004, 0.003), (-1, 0, 0), release=3.0)
    elif kind == 'nod':
        tl.hold(b - 4); tl.to(b, (0.0, -0.012, -0.012), (-16, 0, 0), PUNCH, rlag=0)                 # muzzle snapped down, dead stop on the bolt frame
        tl.kick(b, (0, 0.004, 0.004), (5 * P['k'], 0, 0), attack=0.5, release=2.5)
        tl.mark('hit', b); tl.hold(b + 4 + (1 if P['w'] > 1 else 0)); e = b + 4 + L(P, 8); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle'); tl.kick(e, (0, -0.003, 0.003), (-1, 0, 0), release=3.0)
    elif kind == 'thumb':
        tl.hold(b); tl.kick(b, (0, 0.006 * P['k'], -0.012 * P['k']), (-3 * P['k'], 0, 1), attack=0.5, release=2.5)   # the bolt slams home: the rifle jumps
        tl.mark('hit', b); e = b + 3 + L(P, 8); tl.hold(b + 3); tl.to(e, (0, 0, 0), (0, 0, 0), 'settle')
    else: raise ValueError(kind)


# ---------------------------------------------------------------- the drafts
def m11(c, tl):
    """Nod throw, yank. The muzzle is cocked up a little, then snapped down and stopped dead: the magazine is thrown
    out of the well along its own axis and falls. Down to the belt rig and onto the fresh magazine. Up, held a
    little forward, and jerked back toward the body on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 20
    tl.hold(r - 5 - L(P, 4)); tl.to(r - 5, (0.0, 0.018, 0.012), (10, 0, -4), 'ease')
    tl.to(r, (0.01, -0.11, 0.02), (-40, -4, 6), 'drive', rlag=0); tl.kick(r, (0, 0.012 * P['k'], 0), (6 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r - 1)   # tips over a point near the butt: the grip drops, the stock stays low
    tl.hold(r + 5); pos, rot = c.station('belt'); arr = r + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'yank')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 7, 'appear': arr + 2, 'seated': se}}


def m12(c, tl):
    """Heave, nod. A short dip, then the rifle is heaved up and forward and stops dead: the heavy magazine stays
    behind and drops out. Pulled back to the stomach rig and pressed onto the fresh one. Up, and the muzzle is
    snapped down on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 19
    tl.hold(r - 4 - L(P, 3)); tl.to(r, (0.0, -0.045, 0.015), (-6, 0, -6), 'ease'); tl.mark('release', r)
    tl.to(r + 4, (0.015, 0.06, -0.05), (10, 0, -22), PUNCH, rlag=1); tl.kick(r + 4, (0, -0.016 * P['k'], 0), (-3, 0, 5), attack=0.5, release=2.5)
    tl.hold(r + 9); pos, rot = c.station('stomach_m'); arr = r + 9 + L(P, 8); seat_block(c, tl, pos, rot, arr, se, d=0.12, reb=0.009)
    finish3(c, tl, 'nod')
    return {'mag': {'release': r, 'mode': 'throw', 'slide': 3, 'travel': 0.15, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def m13(c, tl):
    """Cant and slide, pendulum. The rifle is canted outward and the muzzle lifted; the thumb lets the magazine go
    and it slides out under its own weight, as slowly as in the game's own reload, and falls. The rifle swings down
    like a pendulum to the thigh rig and onto the fresh magazine. Swung back up; the thumb drops the bolt and the
    rifle jolts on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 17
    tl.hold(r - 2 - L(P, 10)); tl.to(r, (0.03, 0.01, -0.01), (16, -6, 52), 'heavy', antic=P['a']); tl.kick(r, (0.004, -0.004, 0), (-2, 0, 3 * P['k']), attack=0.5, release=3.0)
    rel = r + 2; tl.hold(rel + 9); pos, rot = c.station('thigh'); arr = rel + 9 + L(P, 10); seat_block(c, tl, pos, rot, arr, se, d=0.12)
    finish3(c, tl, 'thumb')
    return {'mag': {'release': rel, 'mode': 'throw', 'slide': 8, 'travel': 0.15, 'tumble': 3, 'appear': arr + 2, 'seated': se}}


def m14(c, tl):
    """Windmill. A counter lift, then the rifle is swung down and back past the hip in one big arc and stops dead
    behind it: the magazine flies off backward. The well goes onto the fresh magazine on the back rig. Swung forward
    and up into the ready pose and jerked back on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 24
    pos, rot = c.station('back'); mid = np.array(pos) + np.array((0.04, 0.10, -0.02))
    tl.hold(r - 3 - L(P, 11)); tl.to(r - 1, mid, [rot[0] * 0.9, rot[1], rot[2]], 'drive', antic=P['a'] * 1.4, antic_f=4)
    tl.kick(r - 1, (0, 0.004, 0.012 * P['k']), (-4 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r - 2)
    tl.hold(r + 6); arr = r + 6 + L(P, 6); seat_block(c, tl, pos, rot, arr, se, d=0.12)
    finish3(c, tl, 'yank')
    return {'mag': {'release': r - 2, 'mode': 'throw', 'slide': 3, 'travel': 0.16, 'tumble': 9, 'appear': arr + 2, 'seated': se}}


def m15(c, tl):
    """Muzzle-up thrust. The muzzle is raised high and drawn back, then the rifle is thrust forward and stops dead:
    the magazine shoots out of the well forward and falls in front. Down to the belt rig and onto the fresh one. Up,
    and the muzzle is snapped down on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 22
    tl.hold(r - 4 - L(P, 9)); tl.to(r - 4, (0.02, -0.05, 0.14), (40, -6, 4), 'heavy', antic=P['a'])
    tl.to(r, (0.02, -0.02, 0.05), (45, -6, 4), PUNCH, rlag=1)   # drawn back first: a thrust from further forward pulls the shoulder; tl.kick(r, (0, 0, 0.012 * P['k']), (-3 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 6); pos, rot = c.station('belt_wide'); arr = r + 6 + L(P, 8); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'nod')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.16, 'tumble': 6, 'appear': arr + 2, 'seated': se}}


def m16(c, tl):
    """Chop drop, yank. A counter lift, then the rifle is chopped straight down and stops dead low in front of the
    hip: the magazine keeps going and drops out. It stays low and goes onto the fresh magazine on the front of the
    thigh. Up, and jerked back toward the body on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 21
    tl.hold(r - 4 - L(P, 4)); tl.to(r - 4, (0.0, 0.03, 0.0), (6, 0, 0), 'ease')
    tl.to(r, (0.03, -0.115, 0.04), (-12, -4, 4), 'slam', rlag=1); tl.kick(r, (0, 0.012 * P['k'], 0), (3 * P['k'], 0, 0), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 5); pos, rot = c.station('thigh'); arr = r + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'yank')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.15, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def m17(c, tl):
    """Backhand fling, nod. The rifle is swung backhand outward, muzzle sweeping out to the right and rolling onto
    its side, and stops dead: the magazine is flung out to the side. Down to the hip rig and onto the fresh one. Up,
    and the muzzle is snapped down on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 20
    tl.hold(r - 4 - L(P, 4)); tl.to(r - 4, (-0.025, 0.0, 0.01), (0, 8, -10), 'ease')
    tl.to(r, (0.07, -0.01, 0.02), (2, -38, 62), 'drive', rlag=1); tl.kick(r, (0.008, 0, 0), (0, 4 * P['k'], -6 * P['k']), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 5); pos, rot = c.station('hip'); arr = r + 5 + L(P, 8); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'nod')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 8, 'appear': arr + 2, 'seated': se}}


def m18(c, tl):
    """Seesaw. The rifle is rocked muzzle up, muzzle down, twice, each rock stopping dead: the first works the
    magazine loose, the second throws it out along the well. Down to the stomach rig and onto the fresh one. Up,
    and jerked back on the bolt frame."""
    P = c.P; se = c.T['seated']; r1 = 16
    tl.hold(r1 - 4 - L(P, 3)); tl.to(r1 - 3, (0, 0.012, 0.008), (14, 0, -2), 'ease'); tl.to(r1, (0, -0.07, 0.0), (-18, 0, 2), PUNCH, rlag=0)
    tl.kick(r1, (0, 0.004, 0), (4, 0, 0), attack=0.5, release=2.0); tl.to(r1 + 4, (0, 0.0, 0.01), (16, 0, -2), PUNCH, rlag=0)
    tl.hold(r1 + 5 + (1 if P['w'] > 1 else 0)); r2 = tl.f + 4
    tl.to(r2, (0.01, -0.15, 0.02), (-36, -2, 4), PUNCH, rlag=0); tl.kick(r2, (0, 0.006 * P['k'], 0), (6 * P['k'], 0, 0), attack=0.5, release=2.5)
    tl.mark('loosen', r1); tl.mark('release', r2 - 1)
    tl.hold(r2 + 5); pos, rot = c.station('stomach_low'); arr = r2 + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se, d=0.12, reb=0.009)
    finish3(c, tl, 'yank')
    return {'mag': {'release': r2 - 1, 'loosen': [[r1, 0.025]], 'mode': 'throw', 'slide': 3, 'travel': 0.16, 'tumble': 6, 'appear': arr + 2, 'seated': se}}


def m19(c, tl):
    """Inward dump, thumb. The rifle is rolled inward, well toward the other gun, and given a short hop that stops
    dead: the magazine drops out in front of the belly. Down to the stomach rig and onto the fresh one. Up; the
    thumb drops the bolt and the rifle jolts on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 20
    tl.hold(r - 4 - L(P, 6)); tl.to(r - 4, (-0.01, 0.04, 0.0), (4, 6, -50), 'heavy', antic=P['a'])
    tl.to(r, (-0.025, -0.07, -0.01), (-8, 8, -60), PUNCH, rlag=0); tl.kick(r, (0, 0.008 * P['k'], 0), (2, 0, 4 * P['k']), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 5); pos, rot = c.station('stomach_m'); arr = r + 5 + L(P, 6); seat_block(c, tl, pos, rot, arr, se, d=0.12, reb=0.009)
    finish3(c, tl, 'thumb')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.14, 'tumble': 5, 'appear': arr + 2, 'seated': se}}


def m20(c, tl):
    """Corkscrew. A counter roll, then one heavy move down and out that rolls the rifle onto its side and stops dead:
    the magazine is flung out and down. Straight on to the belt rig and onto the fresh one. Up; the thumb drops the
    bolt and the rifle jolts on the bolt frame."""
    P = c.P; se = c.T['seated']; r = 21
    tl.hold(r - 4 - L(P, 4)); tl.to(r - 4, (-0.015, 0.015, 0.0), (4, 4, -16), 'ease')
    tl.to(r, (0.07, -0.08, 0.03), (-12, -10, 80), 'slam', rlag=1); tl.kick(r, (0.01, 0.006, 0), (0, 0, -7 * P['k']), attack=0.5, release=2.5); tl.mark('release', r - 1)
    tl.hold(r + 5); pos, rot = c.station('belt'); arr = r + 5 + L(P, 7); seat_block(c, tl, pos, rot, arr, se)
    finish3(c, tl, 'thumb')
    return {'mag': {'release': r - 1, 'mode': 'throw', 'slide': 3, 'travel': 0.17, 'tumble': 8, 'appear': arr + 2, 'seated': se}}


DRAFTS = {'M11': ('Nod throw, yank', m11), 'M12': ('Heave, nod', m12), 'M13': ('Cant and slide, pendulum', m13), 'M14': ('Windmill', m14),
          'M15': ('Muzzle-up thrust', m15), 'M16': ('Chop drop, yank', m16), 'M17': ('Backhand fling, nod', m17), 'M18': ('Seesaw', m18),
          'M19': ('Inward dump, thumb', m19), 'M20': ('Corkscrew', m20)}
GEN = '''"""{did} {name} (Masamune round 3, take {take}). Rebuilds reload and empty reload, right hand, male V."""
import sys
sys.path.insert(0, '{here}')
import masa3
PARAMS = {params}
if __name__ == '__main__':
    for clip in ('reload', 'empty_reload'): masa3.build('{did}', clip, params=PARAMS)
'''


def stem(did, clip, side='right', body='pma'):
    return f'{did}_{clip}' + ('' if side == 'right' else f'_{side}') + ('' if body == 'pma' else f'_{body}')


def build(did, clip, side='right', body='pma', take='B', out=R3, params=None, quiet=False):
    import rgate
    name, fn = DRAFTS[did]; d = f'{out}/{did}'; os.makedirs(d, exist_ok=True); st = stem(did, clip, side, body)
    S = side.capitalize(); P = dict(prod.TAKES[take]); P.update(params or {}); c = Ctx(GUN, body, clip, P, S); tl = rlib2.TL(c, P['lag'], P['drag']); m = fn(c, tl)
    Pk, Rk = tl.arrays(); kicks = [dict(k) for k in tl.kicks]
    if S == 'Left':
        Pk = Pk * prod.MIR_P; Rk = Rk * prod.MIR_R
        for k in kicks: k['move'] = list(np.array(k['move'], float) * prod.MIR_P); k['rot'] = list(np.array(k['rot'], float) * prod.MIR_R)
    keys = [K(f, Pk[f], Rk[f]) for f in range(c.N)]; keys[0] = K(0); keys[-1] = K(c.N - 1)
    for sh in kicks: sh['release'] = round(min(sh.get('release', 6.0), max((c.N - 1 - sh['f']) / 11.0, 0.3)), 2)
    spec = {'_draft': st, '_id': did, '_name': f'{name}, take {take}', '_doc': ' '.join((fn.__doc__ or '').split()), '_gun': GUN, '_left_gun': GUN, '_body': body, '_side': S,
            '_gun_clip': clip, '_pick': did, '_take': take, '_timing': c.T, '_params': {k: v for k, v in c.P.items()}, '_marks': tl.marks, '_mag': m['mag'], '_two_arm': False, '_round': 3,
            'src': c.rest, 'template': 'idle', 'clip': 'reload_draft', 'frames': c.N, 'keys': {S: keys, ('Left' if S == 'Right' else 'Right'): [K(0)]},
            'shakes': {S: kicks}, 'reach': [0.93, 0.985], 'twist_share': 0.6, 'pole_tilt': prod.POLE_TILT, 'out': f'{d}/{st}.glb'}
    author.build(spec, spec['out'])
    g = Glb(spec['out']); cl = Clip(g, 'reload_draft'); i = g.names.index('Weapon' + S); G = [cl.world(f)[i] for f in range(c.N)]
    track = magtrack2.build(GUN, clip, [(np.array(t), np.array(q)) for t, q in G], m['mag']); spec['_track'] = f'{d}/{st}_track.json'
    json.dump(track, open(spec['_track'], 'w')); json.dump(spec, open(f'{d}/{st}.json', 'w'), indent=1)
    o = rgate.gate(spec, track); json.dump(o, open(f'{d}/{st}_gate.json', 'w'), indent=1)
    if clip == 'empty_reload' and side == 'right' and body == 'pma':
        open(f'{d}/gen_{did}.py', 'w').write(GEN.format(did=did, name=name, take=take, params=json.dumps(params or {}), here=os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')))
    if not quiet: print(rgate.line(o), flush=True)
    return spec, o


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cs = lambda v: v.split(',') if v else None
    cmd = argv[0] if argv else 'list'
    if cmd == 'list':
        for k, (n, fn) in DRAFTS.items(): print(k, n, '|', ' '.join((fn.__doc__ or '').split()))
    elif cmd == 'build':
        ids = cs(argv[1]) if len(argv) > 1 and not argv[1].startswith('--') else list(DRAFTS)
        for did in ids:
            for body in (cs(o('--bodies')) or ['pma']):
                for side in (cs(o('--sides')) or ['right']):
                    for clip in (cs(o('--clips')) or ['reload', 'empty_reload']): build(did, clip, side, body, out=o('--out') or R3)
    else: raise SystemExit(__doc__)
