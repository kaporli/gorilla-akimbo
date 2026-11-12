"""Motion windows of every moving joint of weapon anim glbs, per 30 fps frame.

usage: dumpanim.py <glb> [<glb> ...] [--clips reload,empty_reload]
Per clip: duration, frames; per moving joint: frames in which its local transform differs from frame 0
(first, last), frame and size of the peak, peak direction (parent axes), value at the last frame.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from wclip import TClip, FPS


def windows(c, eps_t=0.001, eps_r=1.0):
    out = {}
    for i, n in enumerate(c.names):
        if not any(k[0] == n for k in c.tr): continue
        t0, r0 = c.local(i, 0.0); dt = []; dr = []; vec = []
        for f in range(c.frames):
            t, r = c.local(i, f / FPS)
            dt.append(float(np.linalg.norm(t - t0))); vec.append(t - t0)
            dr.append(float(np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(r, r0))))))))
        dt = np.array(dt); dr = np.array(dr)
        mv = np.where((dt > eps_t) | (dr > eps_r))[0]
        if not len(mv): continue
        kp = int(np.argmax(dt)) if dt.max() > eps_t else int(np.argmax(dr))
        out[n] = {'first': int(mv[0]), 'last': int(mv[-1]), 'peak_f': kp, 'peak_cm': round(100 * float(dt.max()), 1),
                  'peak_deg': round(float(dr.max()), 1), 'dir': [round(float(x), 2) for x in (vec[kp] / max(dt[kp], 1e-9))],
                  'end_cm': round(100 * float(dt[-1]), 2), 'end_deg': round(float(dr[-1]), 1)}
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; clips = (common.opt(argv, '--clips') or 'reload,empty_reload').split(',')
    for p in argv:
        g = Glb(p); print('==', os.path.basename(p))
        for a in g.j['animations']:
            if a['name'] not in clips: continue
            c = TClip(g, a['name']); print(f'  {a["name"]}: {c.duration:.3f} s, {c.frames} frames')
            for n, w in windows(c).items():
                print(f'     {n:22s} f{w["first"]:3d}..{w["last"]:3d} peak f{w["peak_f"]:3d} {w["peak_cm"]:6.1f} cm {w["peak_deg"]:6.1f} deg dir {w["dir"]} end {w["end_cm"]} cm {w["end_deg"]} deg')
