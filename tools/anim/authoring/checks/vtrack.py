"""Magazine track of a draft that has none: the game's own magazine animation placed on the draft's gun.

The rifle round 1 drafts (2026-11-11) predate _track.json. Their magazine is the game's own magazine clip played on
the same frame axis as the arm clip, so its path is magtrack2.vanilla(gun, clip)['M'] (mesh -> gun axes, per frame) carried
by the draft's gun. This writes <clip>_track.json in the layout survey.py and draftcheck.py read: seated up to the release
(spec _timing.out), 'falling' from the next frame on while the magazine is more than 2 cm from its seat, 'seated' again after.
The frames are the game's, not an own flight: R1 and R3 then measure the glide the owner rejected.

usage: vtrack.py <clip.json> ...
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..'))
import renv, common
import numpy as np


def build(spec):
    import magtrack2
    v = magtrack2.vanilla(spec['_gun'], spec['_gun_clip']); M = v['M']; d = v['dist']; n = spec['frames']; r = int(spec['_timing']['out'])
    gone = next((f for f in range(r + 2, n) if f < len(d) and d[f] < 0.02), n)
    fr = []
    for f in range(n):
        m = np.asarray(M[min(f, len(M) - 1)], float).reshape(16).tolist()
        fr.append({'m': m, 's': 1.0, 'state': 'falling' if r < f < gone else 'seated'})
    return {'release': r, 'free_from': r + 1, 'gone': gone, 'frames': fr, 'plan': {'mode': 'game-animation', 'release': r}, 'note': 'the game magazine clip on the draft gun (vtrack.py)'}


def main(argv):
    for p in argv:
        b = os.path.splitext(p)[0]; spec = json.load(open(b + '.json')); t = build(spec); json.dump(t, open(b + '_track.json', 'w'))
        print(os.path.basename(b), 'release', t['release'], 'gone', t['gone'], 'detached frames', t['gone'] - t['release'] - 1)


if __name__ == '__main__':
    main(sys.argv[1:])
