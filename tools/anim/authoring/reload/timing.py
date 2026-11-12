"""Timing of a gun's own reload animation in 30 fps frames: what an arm clip has to fit.

table(gun id, clip) -> {
  frames      clip length (frames, last included)
  out         magazine starts to leave        clear   12 cm out of the well      far   30 cm away (carried off)
  near        incoming magazine within 12 cm of the seat                          seated  it is in
  exit_dir, exit_speed_cm_f, in_dir   gun axes (x right, y up, z back)
  parts       {gun part: {window [first, last], move_cm, turn_deg, side, stays_moved}} (handle, bolt, flaps)
  handle      [first, last] frames of the charging handle or bolt action after the magazine is in, or null
}
usage: timing.py <gun id> ... [--clips reload,empty_reload] [--json dir]
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from wclip import TClip
import gungeo, magpath, dumpanim

SKIP = ('muzzle_slot', 'fx_muzzle', 'pos_ironsight', 'scope_slot', 'mag_slot', 'reload_hinge_right')
# Guns built on the shared rifle receiver (w_rifle_assault__rcv1): its parts move with the gun's own.
SHARED_RCV = ('copperhead', 'umbra', 'sidewinder')
_cache = {}


def table(gid, clip='empty_reload'):
    if (gid, clip) in _cache: return _cache[(gid, clip)]
    gun = common.gun(gid); b = gungeo.wanim(gun, 'base1'); m = gungeo.wanim(gun, 'mag_std')
    bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
    t = magpath.track(bs, m, clip)
    dc = t['joints'][t['come_joint']]['dist_cm']; near = t['seated']
    while near > 0 and dc[near - 1] < 12: near -= 1
    out = {'gun': gid, 'clip': clip, 'frames': t['frames'], 'out': t['out'], 'clear': t.get('clear'), 'far': t.get('far'), 'near': near,
           'seated': t['seated'], 'exit_dir': t.get('exit_dir'), 'exit_speed_cm_f': t.get('exit_speed_cm_f'), 'in_dir': t['in_dir'],
           'slot': t['slot'], 'base_anim': os.path.basename(b), 'mag_anim': os.path.basename(m), 'parts': {}}
    srcs = [b] + ([gungeo.wanim(gun, 'rcv1')] if gid in SHARED_RCV else [])
    for src in srcs:
        g = Glb(src)
        if clip not in [a['name'] for a in g.j['animations']]: continue
        c = TClip(g, clip)
        for name, w in dumpanim.windows(c).items():
            if name in SKIP: continue
            pos = c.wf(w['peak_f'])[g.names.index(name)][0]
            out['parts'][name] = {'window': [w['first'], w['last']], 'move_cm': w['peak_cm'], 'turn_deg': w['peak_deg'],
                                  'side': 'left' if pos[0] < -0.01 else 'right' if pos[0] > 0.01 else 'centre',
                                  'pos': [round(float(x), 3) for x in pos], 'stays_moved': bool(w['end_cm'] > 0.5 or w['end_deg'] > 2)}
    late = [p['window'] for p in out['parts'].values() if p['window'][0] >= t['seated']]
    out['handle'] = [min(w[0] for w in late), min(max(w[1] for w in late), max(w[0] for w in late) + 12)] if late else None
    _cache[(gid, clip)] = out
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; clips = (common.opt(argv, '--clips') or 'reload,empty_reload').split(','); jd = common.opt(argv, '--json')
    for gid in argv:
        for clip in clips:
            t = table(gid, clip)
            print(f"{gid:11s} {clip:13s} {t['frames']:4d} f  out {t['out']} clear {t['clear']} far {t['far']} near {t['near']} seated {t['seated']} "
                  f"exit {t['exit_dir']} {t['exit_speed_cm_f']} cm/f  in {t['in_dir']}  handle {t['handle']}  parts " +
                  ', '.join(f"{n} {p['window']} {p['move_cm']}cm/{p['turn_deg']}deg {p['side']}" for n, p in t['parts'].items()))
            if jd:
                os.makedirs(jd, exist_ok=True); json.dump(t, open(f'{jd}/timing_{gid}_{clip}.json', 'w'), indent=1)
