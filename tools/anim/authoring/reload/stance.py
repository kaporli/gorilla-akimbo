"""Stance-only lowered clips: the shipped clip's motion with the lowered idle at both ends and no lift (owner 2026-11-25: every lowered-stance slot without a discard variant gets one).
Same code path as the discard layer (discard.build_clip) with a zero offset: the key path is kept, the lowered gun pose is faded in over frames 0 .. a and back from the seated frame (s from the reach and
shoulder limits), lowover.overlay trades the arm for the lowered set's own arm at both ends. The clip length, key count and the clip's own timing marks are the shipped ones; the hidden window is compared
with the shipped layout and reported (no frames are added or removed).

usage: stance.py produce <gun> [--follow-rise] --root <dir> [--control <shipped root>] [--picks SF35,SF40] [--retime <frames>]    (writes <root>/stance/lowered/{clips,layout.json,solve/<pick>.json}; <root>/stance/report.json)
       exit 0 all made and layouts equal the shipped ones, 1 a gate fail or a layout difference
"""
import os, sys, json, glob, time
HERE = os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')
sys.path.insert(0, HERE)
import renv, common, manifest, lowprod, discard
import numpy as np


def produce(gid, root, ctl_arg=None, only=None, retime=None):
    g, r = lowprod.gun_entry(gid)
    if not g.get('lowered') or not r.get('slots') or r.get('shares'): print(f'{gid}: no lowered entry, no slots or shared: not made'); return 3
    take = 'A' if r['weight'] == 'light' else 'B'; picks = [p + take for p in r['slots'] if not only or p in only]
    root = os.path.abspath(root).replace(chr(92), '/').rstrip('/') + '/stance'; ctl = lowprod.ship_root(gid, ctl_arg); reps = []; made = []; z = np.zeros(3)
    for pk in picks:
        t0 = time.time(); rep = {'pick': pk}; E = discard.entries(gid, pk, ctl); w1map = {f"{e['body']}_{e['side']}_{e['clip']}": e['sr']['F'] for e in E}
        sd = f'{root}/lowered/solve'; os.makedirs(sd, exist_ok=True)
        s, trials = discard.bisect_s(gid, pk, ctl, root, z, w1map, retime=retime); rep['s'] = s; rep['trials'] = trials
        fails = discard.build_pick(gid, pk, ctl, f'{root}/lowered/clips', z, w1map, dict({'s': s, 'stance_only': True}, **discard.FOLLOW()), retime=retime); rep['gate_fails'] = fails; rep['seconds'] = round(time.time() - t0); reps.append(rep); made.append(pk[:-1])
        json.dump(rep, open(f'{sd}/{pk}.json', 'w'), indent=1); print(json.dumps({k: v for k, v in rep.items() if k != 'trials'}), flush=True)
    clips = f'{root}/lowered/clips'; lay, fails = discard.layout_of(gid, made, take, clips, ctl); json.dump({'layout': lay, 'fails': fails}, open(f'{root}/lowered/layout.json', 'w'), indent=1)
    diff = []
    for pk in made:      # the shipped layout (hide_start, hide_end, seated, length) of each clip
        for clip in discard.CLIPS:
            lvl = ((r.get('lowered_variant') or {}).get('layout') or {}).get(pk + take, {}).get(clip)      # a lowered clip is compared with the layout wired for it (measured on the lowered clip: its gun leaves the frame earlier), the shipped layout only when none is wired
            sh = dict(lvl or r['layout'][pk + take][clip]); got = lay[pk + take][clip]
            bad = {k: (sh.get(k), got.get(k)) for k in ('hide_start', 'hide_end', 'seated', 'length') if sh.get(k) != got.get(k)}
            if bad: diff.append(f'{pk + take} {clip}: {bad}')
    json.dump({'reports': reps, 'layout_diff': diff}, open(f'{root}/report.json', 'w'), indent=1)
    print(f'stance-only: {len(glob.glob(clips + "/*/*.glb"))} clips, {len(fails)} gate fails, {len(diff)} layout differences from the shipped')
    for f in fails + diff: print('  ', f)
    return 1 if fails or diff else 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--follow-rise' in a: os.environ['GA_FOLLOW_RISE'] = '1'; a.remove('--follow-rise')
    if len(a) < 2 or a[0] != 'produce': raise SystemExit(__doc__)
    pk = common.opt(a, '--picks'); rt = common.opt(a, '--retime')      # --retime <delta>: stretch (+) or cut (-) the hidden window only
    sys.exit(produce(a[1], common.opt(a, '--root'), common.opt(a, '--control'), pk.split(',') if pk else None, {'delta': int(rt)} if rt else None))
