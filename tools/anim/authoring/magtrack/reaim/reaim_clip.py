"""Apply a striker Delta (reaim_core.Delta, world rigid transform per frame) to an arm clip: the striking hand (and its
gun) moves by the delta, the arm is re-solved with two-bone IK keeping the shoulder, the bone lengths and the elbow's
side (pole) of the original frame, the IK helper joints move with the hand. Only frames where the delta is not identity
are rewritten; every other sample is copied unchanged.
usage: reaim_clip.py <in.glb> <out.glb> <delta.json> <striker side Left|Right>"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from reaim_core import Delta, load_delta, quat
from glb import Glb
from fk import Clip, qmul, qinv, qrot


def aim(d, up):
    x = d / np.linalg.norm(d); y = up - x * np.dot(up, x); y /= np.linalg.norm(y)
    return np.stack([x, y, np.cross(x, y)], 1)


def apply(src, out, delta, S):
    """Returns (frames rewritten, {frame: hand and elbow move, reach})."""
    g = Glb(src); c = Clip(g, 'smack'); idx = {n: i for i, n in enumerate(g.names)}
    s = S.lower()
    sh, ua, fa, hd = (idx[f'{S}Shoulder'], idx[f'{S}Arm'], idx[f'{S}ForeArm'], idx[f'{S}Hand'])
    helpers = [idx[n] for n in (f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT', f'Torso_World_{S}Arm_PoleVector_JNT',
                                f'Torso_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_PoleVector_JNT') if n in idx]
    an = g.j['animations'][0]
    chan = {}
    for ch in an['channels']:
        chan[(ch['target']['node'], ch['target']['path'])] = an['samplers'][ch['sampler']]
    arrays = {}
    for key, smp in chan.items():
        if key[0] in (ua, fa, hd) + tuple(helpers):
            arrays[key] = g.acc(smp['output']).copy()
    changed = []; info = {}
    for f in range(c.frames):
        D = delta.at(f)
        if np.allclose(D, np.eye(4), atol=1e-9): continue
        W = c.world(f); Rd = D[:3, :3]; qd = quat(Rd)
        Sp, E, H = W[ua][0], W[fa][0], W[hd][0]
        a = np.linalg.norm(E - Sp); b = np.linalg.norm(H - E)
        H2 = Rd @ H + D[:3, 3]; hq2 = qmul(qd, W[hd][1])
        d = np.linalg.norm(H2 - Sp)
        if d > (a + b) * 0.999: raise SystemExit(f'f{f}: out of reach {d:.4f} > {a + b:.4f}')
        u = (H - Sp) / np.linalg.norm(H - Sp); pole = (E - Sp) - u * np.dot(E - Sp, u); pole /= np.linalg.norm(pole)
        u2 = (H2 - Sp) / d; pole2 = pole - u2 * np.dot(pole, u2); pole2 /= np.linalg.norm(pole2)
        x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(a * a - x * x, 0))
        E2 = Sp + u2 * x + pole2 * h
        n1 = np.cross(E - Sp, H - E); n2 = np.cross(E2 - Sp, H2 - E2)
        qua2 = qmul(quat(aim(E2 - Sp, n2) @ aim(E - Sp, n1).T), W[ua][1])
        qfa2 = qmul(quat(aim(H2 - E2, n2) @ aim(H - E, n1).T), W[fa][1])
        new = {ua: (Sp, qua2), fa: (E2, qfa2), hd: (H2, hq2)}
        for j in helpers:
            t, q = W[j]; new[j] = (Rd @ t + D[:3, 3], qmul(qd, q))
        info[f] = dict(hand_move_cm=round(float(np.linalg.norm(H2 - H)) * 100, 2),
                       elbow_move_cm=round(float(np.linalg.norm(E2 - E)) * 100, 2), reach=round(d / (a + b), 3))
        Wn = dict(W); Wn.update(new)
        for j in (ua, fa, hd) + tuple(helpers):
            pt, pq = Wn[c.par[j]]; t, q = Wn[j]
            lt = qrot(qinv(pq), t - pt); lq = qmul(qinv(pq), q)
            for path, val in (('translation', lt), ('rotation', lq)):
                if (j, path) not in arrays: continue
                times = g.acc(chan[(j, path)]['input'])
                k = int(np.argmin(np.abs(times - f / 30.0))); assert abs(times[k] - f / 30.0) < 1e-4, (j, path, f)
                if path == 'rotation' and np.dot(val, arrays[(j, path)][k]) < 0: val = -val
                arrays[(j, path)][k] = val
        changed.append(f)
    for key, arr in arrays.items():
        a_ = g.j['accessors'][chan[key]['output']]; v = g.j['bufferViews'][a_['bufferView']]
        off = v.get('byteOffset', 0) + a_.get('byteOffset', 0); buf = arr.astype(np.float32).tobytes()
        g.bin[off:off + len(buf)] = buf
    g.save(out)
    return changed, info


if __name__ == '__main__':
    if len(sys.argv) < 5: raise SystemExit(__doc__)
    src, out, dj, S = sys.argv[1:5]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    ch, info = apply(src, out, load_delta(dj), S)
    print('rewrote frames', ch, info)
