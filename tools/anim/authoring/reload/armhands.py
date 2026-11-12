"""What V's hands do in a gun's own two-handed reload (the game's arm set), in gun axes: is the magazine pulled by the
left hand or does it drop free, and which hand works the charging handle or bolt.

usage: armhands.py <gun id> <arm set glb> [--clips reload,empty_reload]
Per clip: the left hand's distance to the leaving magazine at the frames it leaves, to the incoming magazine as it
is seated, and each hand's distance to every moving gun part while it moves. The hand point is the middle finger
root (the palm), so "holding" is under about 12 cm.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import qrot, qinv
from wclip import TClip, FPS
import gungeo, magpath, dumpanim


def hands(arm_glb, clip):
    """Per frame: {LeftHand, RightHand: palm position in gun axes}."""
    c = TClip(Glb(arm_glb), clip); nm = c.names; gi = nm.index('WeaponRight'); out = []
    for f in range(c.frames):
        W = c.wf(f); g0, gq = W[gi]; row = {}
        for S in ('Left', 'Right'):
            p = W[nm.index(f'{S}HandMiddle1')][0]; row[S] = qrot(qinv(gq), p - g0)
        out.append(row)
    return out


def report(gid, arm_glb, clip):
    gun = common.gun(gid); H = hands(arm_glb, clip); n = len(H); out = {'clip': clip, 'frames': n}
    b = gungeo.wanim(gun, 'base1'); m = gungeo.wanim(gun, 'mag_std')
    bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
    t = magpath.track(bs, m, clip); out['mag'] = {k: t[k] for k in ('out', 'clear', 'far', 'in_start', 'seated', 'exit_dir', 'exit_speed_cm_f', 'in_dir', 'leave_joint', 'come_joint', 'frames')}
    P = np.array(t['joints'][t['leave_joint']]['pos']); Q = np.array(t['joints'][t['come_joint']]['pos'])
    d = lambda S, f, p: round(100 * float(np.linalg.norm(H[min(f, n - 1)][S] - p)), 1)
    fo = t['out']
    out['left_to_mag_at_out'] = {f: d('Left', f, P[min(f, len(P) - 1)]) for f in (fo - 2, fo, fo + 2, t.get('clear') or fo + 4)}
    out['left_to_mag_at_seat'] = {f: d('Left', f, Q[min(f, len(Q) - 1)]) for f in (t['seated'] - 4, t['seated'] - 1, t['seated'])}
    parts = {}
    for src in {b, gungeo.wanim(gun, 'rcv1')} - {None}:
        g = Glb(src)
        if clip not in [a['name'] for a in g.j['animations']]: continue
        c = TClip(g, clip)
        for name, w in dumpanim.windows(c).items():
            if name in ('muzzle_slot', 'fx_muzzle', 'pos_ironsight', 'scope_slot', 'mag_slot'): continue
            i = g.names.index(name); fp = min(w['peak_f'], n - 1); pos = c.wf(fp)[i][0]
            parts[name] = {'window': [w['first'], w['last']], 'peak_f': w['peak_f'], 'move_cm': w['peak_cm'], 'turn_deg': w['peak_deg'],
                           'pos': pos.round(3).tolist(), 'side': 'left' if pos[0] < -0.01 else 'right' if pos[0] > 0.01 else 'centre',
                           'left_hand_cm': min(d('Left', f, c.wf(f)[i][0]) for f in range(w['first'], min(w['last'], n - 1) + 1)),
                           'right_hand_cm': min(d('Right', f, c.wf(f)[i][0]) for f in range(w['first'], min(w['last'], n - 1) + 1)),
                           'stays_moved': w['end_cm'] > 0.5 or w['end_deg'] > 2}
    out['parts'] = parts
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; clips = (common.opt(argv, '--clips') or 'reload,empty_reload').split(',')
    import json
    for clip in clips:
        r = report(argv[0], argv[1], clip); print(argv[0], json.dumps(r))
