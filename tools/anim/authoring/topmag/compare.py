"""Compare regenerated clips with the recorded generator output.
usage: compare.py [clips dir]   (default: the topmag work folder's clips; holds <body>/<clip>.glb)
The recorded generator output of a clip is its oldest kept version: the authoring data folder's
clips_prev_20261107 (before the local re-time), else clips_prev_20261107_r3 (before the re-aim), else the
clips_pre_endpose folder (clips that were never re-timed or re-aimed).
Prints per clip: identical (byte for byte), or the largest difference over all joint tracks in cm and degrees."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
from glb import Glb

STAGES = ('clips_prev_20261107', 'clips_prev_20261107_r3')


def recorded(body, name):
    for s in STAGES:
        p = common.anim_work(s, body, name)
        if os.path.exists(p):
            return p
    p = common.path('clips_pre_endpose') + f'/{body}/{name}'
    return p if os.path.exists(p) else None


def tracks(path):
    g = Glb(path)
    return g.tracks(g.j['animations'][0]['name'])


def diff(a, b):
    """(largest translation difference cm, largest rotation difference deg, worst joint, note)"""
    A, B = tracks(a), tracks(b)
    if set(A) != set(B):
        return None, None, '', f'track sets differ ({len(A)} vs {len(B)})'
    dt = dr = 0.0; worst = ''
    for k in A:
        x, y = A[k][1], B[k][1]
        if x.shape != y.shape:
            return None, None, k[0], f'{k[0]} {k[1]}: {len(x)} vs {len(y)} keys'
        if k[1] == 'translation':
            d = float(np.linalg.norm(x - y, axis=1).max()) * 100
            if d > dt: dt = d; worst = k[0]
        elif k[1] == 'rotation':
            c = np.abs((x * y).sum(1)) / (np.linalg.norm(x, axis=1) * np.linalg.norm(y, axis=1))
            d = float(np.degrees(2 * np.arccos(np.clip(c, -1, 1))).max())
            if d > dr: dr = d; worst = k[0]
    return dt, dr, worst, ''


def compare(clips_dir):
    rows = []
    for body in sorted(os.listdir(clips_dir)):
        if not os.path.isdir(f'{clips_dir}/{body}'):
            continue
        for name in sorted(os.listdir(f'{clips_dir}/{body}')):
            if not name.endswith('.glb'):
                continue
            new = f'{clips_dir}/{body}/{name}'; old = recorded(body, name)
            if not old:
                rows.append((body, name, None, 'no recorded clip')); continue
            if open(new, 'rb').read() == open(old, 'rb').read():
                rows.append((body, name, old, 'identical')); continue
            dt, dr, worst, note = diff(new, old)
            rows.append((body, name, old, note or f'differs: {dt:.4f} cm, {dr:.4f} deg (worst {worst})'))
    return rows


if __name__ == '__main__':
    d = (sys.argv[1] if len(sys.argv) > 1 else common.work('topmag', 'clips')).replace('\\', '/')
    rows = compare(d)
    root = common.path('anim_work')
    for body, name, old, res in rows:
        print(f'{body} {name:44s} {res:48s} {old.replace(root + "/", "") if old else ""}')
    n = sum(r[3] == 'identical' for r in rows)
    print(f'{n} of {len(rows)} identical')
