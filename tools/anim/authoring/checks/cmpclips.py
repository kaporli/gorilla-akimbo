"""Compares two clips folders (<body>/<clip>.glb), or two glb files: byte for byte, and where the bytes differ, the
largest difference per clip in cm (translations) and degrees (rotations), frame by frame in local space.

usage: cmpclips.py <a> <b> [--only <text in the file name>]
Exit code 1 if anything differs or a file of <a> is missing in <b>.
"""
import glob, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip


def ang(q1, q2):
    d = abs(float(np.dot(q1 / np.linalg.norm(q1), q2 / np.linalg.norm(q2)))); return float(np.degrees(2 * np.arccos(min(1, d))))


def numeric(a, b):
    """(max cm, max deg, note) over all clips, joints and frames of two glbs."""
    A, B = Glb(a), Glb(b)
    na, nb = [x['name'] for x in A.j['animations']], [x['name'] for x in B.j['animations']]
    if na != nb or A.names != B.names:
        return float('inf'), float('inf'), 'clip names or joints differ'
    cm = deg = 0.0
    for name in na:
        ca, cb = Clip(A, name), Clip(B, name)
        if ca.frames != cb.frames:
            return float('inf'), float('inf'), f'{name}: {ca.frames} and {cb.frames} frames'
        for f in range(ca.frames):
            for i in range(len(A.names)):
                ta, qa = ca.local(i, f); tb, qb = cb.local(i, f)
                cm = max(cm, float(np.linalg.norm(ta - tb)) * 100); deg = max(deg, ang(qa, qb))
    return cm, deg, ''


def compare(a, b, only=None):
    """[(relative name, 'identical' | 'differs' | 'missing', cm, deg, note)]"""
    if os.path.isfile(a):
        pairs = [(os.path.basename(a), a, b)]
    else:
        pairs = []
        for f in sorted(glob.glob(a + '/**/*.glb', recursive=True)):
            rel = os.path.relpath(f, a).replace(os.sep, '/')
            if not only or only in rel:
                pairs.append((rel, f, b + '/' + rel))
    out = []
    for rel, fa, fb in pairs:
        if not os.path.exists(fb):
            out.append((rel, 'missing', None, None, ''))
        elif open(fa, 'rb').read() == open(fb, 'rb').read():
            out.append((rel, 'identical', 0.0, 0.0, ''))
        else:
            out.append((rel, 'differs') + numeric(fa, fb))
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]
    only = common.opt(argv, '--only')
    res = compare(argv[0], argv[1], only)
    for rel, state, cm, deg, note in res:
        if state != 'identical':
            print(f'{state:9s} {rel}' + (f'  max {cm:.4f} cm {deg:.4f} deg {note}' if state == 'differs' else ''))
    same = sum(r[1] == 'identical' for r in res)
    diff = [r for r in res if r[1] == 'differs']
    print(f'{len(res)} glb: {same} byte-identical, {len(diff)} differ'
          + (f' (max {max(r[2] for r in diff):.4f} cm, {max(r[3] for r in diff):.4f} deg)' if diff else '')
          + f', {sum(r[1] == "missing" for r in res)} missing in {argv[1]}')
    sys.exit(0 if same == len(res) else 1)
