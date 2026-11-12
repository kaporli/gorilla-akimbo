"""Copy the magazine-gun-side arm (shoulder, arm, forearm, hand, IK helpers) of one clip into another over a frame
range, so all category clips of a pick share the same motion of the magazine gun (the magazine track is converted with
their mean pose; the per-category retime left their kicks up to 1 cm apart at f26).
usage: unify.py <from.glb> <into.glb> <out.glb> <magazine gun side Left|Right> [f0 f1]   (default f18 f32)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import common
import numpy as np
from glb import Glb


def unify(src, dst, out, S, f0=18, f1=32):
    gs, gd = Glb(src), Glb(dst); s = S.lower()
    names = {f'{S}Shoulder', f'{S}Arm', f'{S}ForeArm', f'{S}Hand', f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT',
             f'Torso_World_{S}Arm_PoleVector_JNT', f'Torso_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_PoleVector_JNT'}
    def chans(g):
        an = g.j['animations'][0]
        return {(g.names[c['target']['node']], c['target']['path']): an['samplers'][c['sampler']] for c in an['channels']}
    cs, cd = chans(gs), chans(gd); n = 0
    for key, smp in cd.items():
        if key[0] not in names: continue
        a = gs.acc(cs[key]['output']); b = gd.acc(smp['output']).copy()
        ts = gs.acc(cs[key]['input']); td = gd.acc(smp['input'])
        assert len(a) == len(b) and np.allclose(ts, td)
        for k, t in enumerate(td):
            if f0 <= round(t * 30) <= f1: b[k] = a[k]; n += 1
        acc = gd.j['accessors'][smp['output']]; v = gd.j['bufferViews'][acc['bufferView']]
        off = v.get('byteOffset', 0) + acc.get('byteOffset', 0); buf = b.astype(np.float32).tobytes()
        gd.bin[off:off + len(buf)] = buf
    gd.save(out); return n


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 4: raise SystemExit(__doc__)
    os.makedirs(os.path.dirname(os.path.abspath(a[2])), exist_ok=True)
    print('samples copied', unify(a[0], a[1], a[2], a[3], *(int(x) for x in a[4:6])))
