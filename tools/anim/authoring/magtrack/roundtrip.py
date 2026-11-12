"""Round trip of the magazine sets: the packed .anims exported back to glb by WolvenKit, compared per frame with the
glbs written by tools/anim/magtrack.py. Catches a resampled import (odd clip lengths came back with one key less and
up to 7 mm of motion before the hit).
usage: roundtrip.py <written sets glb dir> <exported glb dir> [--spec <spec.json>]
  exported: <set prefix>_<family>_<side>.anims.glb per set. Exit code 1 on a frame count or tolerance miss.
compare(written, exported, spec) -> [{set, clip, frames, frames_exported, diff_mm, diff_deg, still_mm}]
"""
import os, sys
import numpy as np
import mag_geom as g
from mag_geom import Glb, Clip
from fk import qmul, qrot

TOL_MM, TOL_DEG, STILL_MM = 0.05, 0.05, 0.001


def track(gl, name, joint):
    """world (t, q) of one joint per frame, walking its parent chain only"""
    c = Clip(gl, name); i = gl.names.index(joint); chain = []
    while i is not None: chain.append(i); i = c.par.get(i)
    out = []
    for f in range(c.frames):
        T, R = np.zeros(3), np.array([0, 0, 0, 1.0])
        for k in reversed(chain):
            t, r = c.local(k, f); T = T + qrot(R, t); R = qmul(R, r)
        out.append((T, R / np.linalg.norm(R)))
    return out


def cmp(A, B):
    """(max translation difference mm, max rotation difference deg) over the common frames"""
    dt = da = 0
    for (ta, ra), (tb, rb) in zip(A, B):
        dt = max(dt, np.linalg.norm(ta - tb))
        da = max(da, np.degrees(2 * np.arccos(min(1, abs(np.dot(ra / np.linalg.norm(ra), rb / np.linalg.norm(rb)))))))
    return dt * 1000, da


def compare(written, exported, spec=None):
    spec = spec or g.load_spec(); out = []
    for key in g.spec_keys(spec):
        a = Glb(g.common.need(g.set_glb(written, key)))
        b = Glb(g.common.need(g.set_glb(exported, key)[:-4] + '.anims.glb'))
        for pi, e in enumerate(spec[key]):
            for nm in (g.NAMES[pi], g.EMPTY[pi]):
                A, B = track(a, nm, 'mag_std'), track(b, nm, 'mag_std')
                still = max(np.linalg.norm(B[f][0] - B[0][0]) for f in range(min(e['K'] + 1, len(B)))) * 1000
                dt, da = cmp(A, B)
                out.append(dict(set=key, clip=nm, frames=len(A), frames_exported=len(B), diff_mm=float(dt),
                                diff_deg=float(da), still_mm=float(still)))
    return out


if __name__ == '__main__':
    a = sys.argv[1:]; spec = g.load_spec(g.common.opt(a, '--spec'))
    if len(a) != 2: raise SystemExit(__doc__)
    bad = 0
    for r in compare(a[0], a[1], spec):
        ok = r['frames'] == r['frames_exported'] and r['diff_mm'] <= TOL_MM and r['diff_deg'] <= TOL_DEG and r['still_mm'] <= STILL_MM
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {r['set']:11s} {r['clip']:16s} frames {r['frames']}/{r['frames_exported']} max diff "
              f"{r['diff_mm']:.2f} mm {r['diff_deg']:.2f} deg | exported motion before release {r['still_mm']:.3f} mm")
    sys.exit(1 if bad else 0)
