"""Finger torque of a reload clip's in-hand turns (gate R7 of the draft check). Reads the clip glb; nothing is written.
In-hand turn frame: the gun turns relative to the hand faster than 0.5 deg/f (dilated by one frame). Only those frames are judged: an arm-driven turn
(the gun fixed in the hand, 15 to 100 N m in approved clips) is not a finger action and is not measured.
Net applied finger torque on a frame = I alpha - m (c - p) x g, about the in-hand spin pivot p (reload/gunmass.py: gun mass and inertia from the
mesh, uniform 1000 kg/m3, voxel method of gg-work/migration/ptorque). Peak = the largest norm over the in-hand turn frames.
usage: fingertorque.py <clip.glb|clip.json> ...   (prints peak, turn frames, I alpha only peak)
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, HERE)
import renv
import numpy as np
import gunmass
from glb import Glb
from wclip import TClip


def series(glb, clip, side):
    """Weapon<side> and <side>Hand world rotations per frame."""
    c = TClip(Glb(glb), clip); iw = c.names.index('Weapon' + side); ih = c.names.index(side + 'Hand'); Rw, Rh = [], []
    for f in range(c.frames):
        W = c.wf(f); Rw.append(gunmass.qmat(np.array(W[iw][1], float))); Rh.append(gunmass.qmat(np.array(W[ih][1], float)))
    return np.array(Rw), np.array(Rh)


def world_D(glb, clip, side, mp):
    """Full torque about the pivot with the gun's world angular motion and the pivot's world acceleration (ptorque/torque.py D): I a_w + w_w x (I w_w) + m (c - p) x (a_p - g), gun axes, N m per frame (0 at the ends). It includes arm swing."""
    from wclip import TClip
    c = TClip(Glb(glb), clip); iw = c.names.index('Weapon' + side); n = c.frames; tw, Rw = [], []
    for f in range(n):
        W = c.wf(f); tw.append(np.array(W[iw][0], float)); Rw.append(gunmass.qmat(np.array(W[iw][1], float)))
    Rw = np.array(Rw); dt = 1 / 30.0; I = np.asarray(mp['I_pivot']); m = mp['mass_kg']; piv = np.asarray(mp['pivot_m']); r = np.asarray(mp['com_m']) - piv; G = np.array([0, -9.81, 0])
    ww = np.array([gunmass.logR(Rw[k].T @ Rw[k + 1]) / dt for k in range(n - 1)]); pw = np.array([tw[f] + Rw[f] @ piv for f in range(n)]); D = np.zeros(n)
    for f in range(1, n - 1):
        w = (ww[f - 1] + ww[f]) / 2; a = (ww[f] - ww[f - 1]) / dt; ap = (pw[f + 1] - 2 * pw[f] + pw[f - 1]) / dt ** 2
        D[f] = np.linalg.norm(I @ a + np.cross(w, I @ w) + m * np.cross(r, Rw[f].T @ (ap - G)))
    return D


def measure(base, spec):
    """-> dict: gun, mass_kg, turn_frames, peak_nm (net), peak_inertial_nm (I alpha only), peak_frame, turn_first, turn_last, turn_deg_f_max, or {'error'} / {'skipped'}."""
    gid = spec.get('_gun')
    if not gid: return {'skipped': 'spec has no _gun'}
    mp = gunmass.props(gid)
    if mp is None: return {'gun': gid, 'skipped': 'gun has no mesh'}
    side = 'Left' if str(spec.get('_side', 'Right')).lower() == 'left' else 'Right'
    Rw, Rh = series(base + '.glb', spec.get('clip', 'reload'), side); Rrel = np.array([Rh[f].T @ Rw[f] for f in range(len(Rw))])
    fl = spec.get('_free_flights') or []      # [[release frame, catch frame], ...]: free-flight steps are exempt, the throw, hold and catch frames stay measured
    skip = {k for a_, b_ in fl for k in range(a_, b_)}
    turn, tau = gunmass.net_torque(Rrel, Rw, mp, skip_steps=skip); _, tau0 = gunmass.net_torque(Rrel, Rw, mp, gravity=False, skip_steps=skip)
    n = len(turn); freeset = {f for a_, b_ in fl for f in range(a_ + 1, b_)}
    Dw = world_D(base + '.glb', spec.get('clip', 'reload'), side, mp)
    arm = [f for f in range(1, n - 1) if not turn[f] and f not in freeset]      # frames where the gun does not turn in the hand (below TURN_DEG_F) and is held: arm-driven, measured as D (ptorque population definition)
    out = {'gun': gid, 'side': side, 'mass_kg': round(mp['mass_kg'], 4), 'turn_frames': int(turn.sum()), 'peak_nm': 0.0, 'peak_inertial_nm': 0.0,
           'arm_driven_peak_nm': round(float(Dw[arm].max()), 3) if arm else 0.0, 'arm_driven_peak_frame': (arm[int(np.argmax(Dw[arm]))] if arm else None)}
    idx = np.nonzero(turn)[0]
    if len(idx):
        nr = np.linalg.norm(tau[idx], axis=1); k = int(np.argmax(nr))
        out.update(peak_nm=float(nr[k]), peak_frame=int(idx[k]), peak_inertial_nm=float(np.linalg.norm(tau0[idx], axis=1).max()), turn_first=int(idx[0]), turn_last=int(idx[-1]))
    return out


if __name__ == '__main__':
    for p in sys.argv[1:]:
        b = os.path.splitext(p)[0]; spec = json.load(open(b + '.json')); r = measure(b, spec)
        print(os.path.basename(b), json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}))
