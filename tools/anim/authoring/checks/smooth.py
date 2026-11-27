"""Smoothness (rule S1): is the motion of the arm chain after the hidden window as fluid as the shipped clip the variant is made from?

Why relative: no absolute measure separates the owner-rejected follow-rise clips from the shipped set (every candidate has a shipped worst at or above the rejected worst: designed kicks and snaps), and
the gun and hand screen jerk fails 113 of 220 shipped clips. The clamps (rate limits, damping) made the arm chain rougher than the clip they were applied to: pairing each variant with its source shows it.
Measure (pfix3/arm_cal.py, pfix3/arm_cal.json): for the clip's reloading arm, the local rotations of the clavicle (<S>Shoulder), upper arm, forearm and hand; angular speed per frame (deg/f) over the
frames after hide_end (event frames of the spec within 2 frames excluded: designed contact snaps); jerk = peak |change of angular acceleration|; sign changes = frames where the angular acceleration reverses
(both sides above 0.3 deg/f^2).
Rule: against the control (the shipped clip of the same name), the variant's clavicle jerk, the chain jerk (sum of the four joints' peaks) and the clavicle sign changes rise by at most the limits
(checks.draft.s1: the worst rise of the approved Warden variants x 1.1). Calibration: approved Warden variants vs shipped +0.1 / +0.6 / 0; the 34 rejected follow-rise clips (pma) vs their source: 30 exceed,
the 4 that do not are smoother than their source.
usage: smooth.py <variant stem> <control stem>
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')
sys.path.insert(0, HERE + '/../reload'); sys.path.insert(0, HERE + '/..')
import renv, common, manifest
import numpy as np
from glb import Glb
from fk import Clip

CHAIN = ('clavicle', 'arm', 'forearm', 'hand')


def lim():
    return manifest.load()['checks']['draft']['s1']


def series(stem, sp):
    S = sp['_side']; g = Glb(stem + '.glb'); c = Clip(g, sp['clip']); N = sp['frames']; out = {}
    for k, n in (('clavicle', S + 'Shoulder'), ('arm', S + 'Arm'), ('forearm', S + 'ForeArm'), ('hand', S + 'Hand')):
        i = g.names.index(n); Q = np.array([c.local(i, f)[1] for f in range(N)], float)
        for f in range(1, N):
            if np.dot(Q[f], Q[f - 1]) < 0: Q[f] = -Q[f]
        d = np.einsum('ij,ij->i', Q[1:], Q[:-1]); out[k] = np.r_[0.0, np.degrees(2 * np.arccos(np.clip(np.abs(d), 0, 1)))]
    return out


def measure(stem):
    """{'clavicle_jerk', 'chain_jerk', 'clavicle_signchg'} of a clip after its hide_end."""
    sp = json.load(open(stem + '.json')); gt = json.load(open(stem + '_gate.json')); N = sp['frames']; he = gt['layout']['hide_end']; a = (he if he is not None else int(N * 0.4)) + 1
    ev = set()
    for v in (sp.get('_marks') or {}).values():
        if isinstance(v, (int, float)):
            for d in range(-2, 3): ev.add(int(v) + d)
    ser = series(stem, sp); res = {}
    for k, w in ser.items():
        acc = np.r_[0.0, np.diff(w)]; jerk = 0.0; sc = 0
        for f in range(a + 2, N - 2):
            if f in ev or f - 1 in ev or f + 1 in ev: continue
            jerk = max(jerk, abs(acc[f + 1] - acc[f]))
            if abs(acc[f]) > 0.3 and abs(acc[f + 1]) > 0.3 and acc[f] * acc[f + 1] < 0: sc += 1
        res[k] = (jerk, sc)
    return {'clavicle_jerk': res['clavicle'][0], 'chain_jerk': sum(res[k][0] for k in CHAIN), 'clavicle_signchg': res['clavicle'][1]}


def visible_chain(stem):
    """{'arm': (peak, jerk), 'forearm': (peak, jerk)}: angular speed (deg/f) peak and jerk (peak |third difference|) of the upper arm and the forearm on the frames after hide_end."""
    sp = json.load(open(stem + '.json')); he = json.load(open(stem + '_gate.json'))['layout']['hide_end']; ser = series(stem, sp); out = {}
    for k in ('arm', 'forearm'):
        w = ser[k][he + 1:]; d3 = np.diff(np.diff(w)); out[k] = (float(w.max()), float(np.abs(d3).max()) if len(d3) else 0.0)
    return out


def ratio_fails(stem, ctl):
    """Fails of the visible arm chain of a lowered rise against its source clip: the approved lowered variants' worst ratio x 1.1 per joint and measure (checks.draft.s1.arm_ratio_max)."""
    a = visible_chain(stem); b = visible_chain(ctl); B = manifest.load()['checks']['draft']['s1']['arm_ratio_max']; fails = []
    for k in ('arm', 'forearm'):
        for i, m in enumerate(('peak', 'jerk')):
            r = a[k][i] / max(b[k][i], 1e-6)
            if r > B[k][m] + 1e-9: fails.append(f'{k} {m} ratio {r:.2f} > {B[k][m]}')
    return fails


def compare(stem, ctl):
    """Rise of the variant over its control: {'clavicle_jerk', 'chain_jerk', 'clavicle_signchg'} (positive = rougher)."""
    a = measure(stem); b = measure(ctl)
    return {k: round(a[k] - b[k], 3) for k in a}


def verdict(d):
    L = lim(); fails = []
    for k in ('clavicle_jerk', 'chain_jerk', 'clavicle_signchg'):
        if d[k] > L[k + '_rise_max'] + 1e-9: fails.append(f"{k} rises {d[k]} > {L[k + '_rise_max']}")
    return fails


if __name__ == '__main__':
    d = compare(sys.argv[1], sys.argv[2]); print(d, verdict(d))
