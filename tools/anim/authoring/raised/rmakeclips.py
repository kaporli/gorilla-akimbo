"""Writes the clips of the raised poses of weapons.json into paths.raised_clips (RAISEDCLIPS):

  <body>/raised_<pose>.glb         the pose clips of the game's dual-wield base set (rpose.POSE_CLIPS) with the gun
                                   moved by the family delta; plain names move the right arm, _l names the left arm
  <body>/raised_<pose>_hands.glb   equip, unequip, melee (and _l) of the per-hand reload set, the same way
  <body>/topmag/<clip>__<pose>.glb top-magazine arm clips with this gun as the partner: the partner arm starts in the
                                   raised pose, is back on the original clip by frame checks.raised.topmag_window[0]
                                   (so the hit is untouched) and eases into the raised pose again between window[1]
                                   and checks.raised.topmag_back_by, while the guns are down out of view
  each with _spec.json (family, s, per clip: frames, worst wrist change, shoulder pull)

The per-hand reload clips themselves are made by the build (flick.py --rest <body>/raised_<pose>.glb).

usage: rmakeclips.py [--poses p,p] [--bodies pma,pwa] [--only pose,hands,topmag] [--out <dir>]
  GA_TEST=1 includes the guns with status "test". Existing files are replaced.
"""
import json, os, sys
import rpose as R
from rpose import common
import numpy as np
from lpose import FPS, slerp, qmul, qinv, qrot

sys.path.insert(0, common.ANIM)
import topmagsets


def retarget(body, rig, name, S, fam, s, kind, aim=False):
    """Frames of clip `name` of `rig` with hand S moved. -> (frames, report)"""
    src = R.clip_frames(rig, name); n = len(src); fr = []; ww = sh = 0.0
    for f, L in enumerate(src):
        N, st = R.pose(body, L, fam, s, sides=(S,), aim=aim, w=R.ramp(kind, f, n), rig=rig)
        fr.append(N)
        if st: ww = max(ww, st[S]['wrist']); sh = max(sh, st[S]['shift'])
    if len(fr) < 4: fr = (fr * 4)[:4]
    return fr, {'frames': len(fr), 'wrist_change_deg': round(ww, 1), 'shoulder_pull_cm': round(100 * sh, 1)}


def pose_clips(body, pose, fam, s, out):
    rig, p = R.base(body); clips = {}; rep = {}
    for n, kind in R.POSE_CLIPS.items():
        for S, name in (('Right', n), ('Left', n + '_l')):
            clips[name], rep[name] = retarget(body, rig, name, S, fam, s, kind, n in R.AIM_CLIPS)
    R.write_full(rig, p, clips, out)
    return rep


def hand_clips(body, pose, fam, s, out):
    clips = {}; rep = {}
    for S, side, suf in (('Right', 'right', ''), ('Left', 'left', '_l')):
        rig = R.rig_of(common.need(common.reload_glb(body, side)))
        for n, kind in R.HAND_CLIPS.items():
            clips[n + suf], rep[n + suf] = retarget(body, rig, n + suf, S, fam, s, kind)
    R.write_full(R.rig_of(common.reload_glb(body, 'right')), common.reload_glb(body, 'right'), clips, out)
    return rep


def topmag_clip(body, src, pose, fam, s, S, out):
    """Partner hand S of a top-magazine clip: full delta at frame 0, none inside the window, full at the end."""
    rig = R.rig_of(src); name = rig.g.j['animations'][0]['name']
    frames = R.clip_frames(rig, name); n = len(frames); a, b = R.RULES['topmag_window']; e = R.RULES['topmag_back_by']; fr = []; ww = sh = 0.0

    def ease(x):
        x = min(max(x, 0.0), 1.0)
        return x * x * (3 - 2 * x)
    # The raised idle of this hand (the pose the graph blends from when the reload starts and cuts to when it ends).
    irig = R.rig_of(R.clip_glb(pose, body)); idle = irig.sample(R.IDLE + ('' if S == 'Right' else '_l'), 0.0); Wi = irig.world(idle)
    R.arm_joints(S); ch, hh, ph = R.A.SIDES[S]
    for f, L in enumerate(frames):
        w = 1 - ease(f / a) if f < a else ease((f - b) / (e - b)) if f > b else 0.0
        N, st = R.pose(body, L, fam, s, sides=(S,), w=w, rig=rig)
        if f < a:   # the source clip starts a little off the game idle: start exactly in the raised idle
            k = ease(f / a)
            for j in ch[:4]: N[j] = (idle[j][0] + (N[j][0] - idle[j][0]) * k, slerp(idle[j][1], N[j][1], k))
            W = rig.world(N)
            for js, anchor in ((hh, ch[3]), (ph, ch[2])):   # IK helpers: carried by the hand and the forearm as in the idle
                for j in js:
                    rt = qrot(qinv(Wi[anchor][1]), Wi[j][0] - Wi[anchor][0]); rq = qmul(qinv(Wi[anchor][1]), Wi[j][1])
                    t = W[anchor][0] + qrot(W[anchor][1], rt); q = qmul(W[anchor][1], rq); pw = W[rig.par[j]]
                    lt, lq = qrot(qinv(pw[1]), t - pw[0]), qmul(qinv(pw[1]), q)
                    N[j] = (lt + (N[j][0] - lt) * k, slerp(lq, N[j][1], k))
        fr.append(N)
        if st: ww = max(ww, st[S]['wrist']); sh = max(sh, st[S]['shift'])
    R.write_full(rig, src, {name: fr}, out)
    return {'source': src, 'partner': S, 'frames': n, 'wrist_change_deg': round(ww, 1), 'shoulder_pull_cm': round(100 * sh, 1)}


if __name__ == '__main__':
    argv = sys.argv[1:]
    OUT = common.opt(argv, '--out') or common.path('raised_clips')
    only = (common.opt(argv, '--only') or 'pose,hands,topmag').split(',')
    want = common.opt(argv, '--poses'); bodies = common.body_list(common.opt(argv, '--bodies'))
    defs = common.manifest.raised_defs()
    for body in bodies:
        os.makedirs(f'{OUT}/{body}/topmag', exist_ok=True)
        for pose, (fam, sv) in defs.items():
            if want and pose not in want.split(','): continue
            s = sv[body]
            for kind, fn, suffix in (('pose', pose_clips, ''), ('hands', hand_clips, '_hands')):
                if kind not in only: continue
                glb = f'{OUT}/{body}/raised_{pose}{suffix}.glb'
                rep = fn(body, pose, fam, s, glb)
                json.dump({'pose': pose, 'family': fam, 's': s, 'body': body, 'delta_idle': R.delta(fam, s), 'delta_aim': R.delta(fam, s, True),
                           'clips': rep}, open(glb.replace('.glb', '_spec.json'), 'w'), indent=1)
                print(body, pose, kind, 'worst wrist change', max(r['wrist_change_deg'] for r in rep.values()),
                      'shoulder pull', max(r['shoulder_pull_cm'] for r in rep.values()), flush=True)
        if 'topmag' in only:
            for b, src, pose, S in topmagsets.raised_sources(common.path('clips')):
                if b != body or (want and pose not in want.split(',')): continue
                fam, sv = defs[pose]
                glb = f'{OUT}/{body}/topmag/{os.path.basename(src)[:-4]}__{pose}.glb'
                rep = topmag_clip(body, src, pose, fam, sv[body], S, glb)
                json.dump(dict(rep, pose=pose, family=fam, s=sv[body], window=R.RULES['topmag_window']), open(glb.replace('.glb', '_spec.json'), 'w'), indent=1)
                print(body, os.path.basename(glb), rep['wrist_change_deg'], rep['shoulder_pull_cm'], flush=True)
