"""Re-aim every arm clip of one pick: apply a striker delta (reaim_clip.py) to each clip of the pick in the spec, then
optionally give all clips the magazine-gun arm of one of them (unify.py).
usage: reaim_pick.py <set>_<pick> <delta.json> <in clips dir> <out clips dir> [--unify <clip name>] [--spec <spec.json>]
  The clips are read as <in>/<body>/<file> and written as <out>/<body>/<file>; in and out must differ.
  --unify: name of the pick's clip (no folder, no .glb) whose magazine-gun arm f18-32 is copied into the others.
The shipped re-aims (2026-11-07), from the clips before them:
  reaim_pick.py long_right_lupper delta_long_right_lupper.json <in> <out>
  reaim_pick.py smg_right_uppercut delta_smg_right_uppercut.json <in> <out> --unify shingen_right_uppercut_top_low
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reaim_core as rc
from reaim_core import g
from reaim_clip import apply
from unify import unify


def reaim_pick(spec, name, delta, src, dst, unify_from=None):
    """Returns the written files."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit('in and out folder are the same')
    key, pi = g.find_pick(spec, name); st = rc.striker(spec, key, pi); sh = spec[key][pi]['side']; out = []
    for p, body, _, _, _ in g.spec_cases(spec, key, pi, src):
        o = f'{dst}/{body}/{os.path.basename(p)}'; os.makedirs(os.path.dirname(o), exist_ok=True)
        ch, info = apply(p, o, delta, st)
        print(f'{body}/{os.path.basename(p)}: frames {ch}, hand moves up to {max(i["hand_move_cm"] for i in info.values())} cm')
        out.append((body, o))
    if unify_from:
        for body, o in out:
            ref = f'{dst}/{body}/{unify_from}.glb'
            if os.path.abspath(o) != os.path.abspath(g.common.need(ref)):
                print(f'{body}/{os.path.basename(o)}: {unify(ref, o, o, sh)} samples of the {sh} arm from {unify_from}')
    return [o for _, o in out]


if __name__ == '__main__':
    a = sys.argv[1:]
    spec = g.load_spec(g.common.opt(a, '--spec')); uf = g.common.opt(a, '--unify')
    if len(a) != 4: raise SystemExit(__doc__)
    reaim_pick(spec, a[0], rc.load_delta(a[1]), a[2], a[3], uf)
