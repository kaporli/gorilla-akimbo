"""Native lowered mode (the approved method of smgprod.py --lowered, one code path for every generator that builds its clip from a timeline (rlib2.TL): the SMG front picks (frontprod.py) and the rifles (prod.py)).
GA_NATIVE_LOWERED=1 turns it on, GA_NATIVE_S the gesture scale s (solved by native_s.py as lowprod/discard.bisect_s does), GA_NATIVE_SR the scale s_r of the
post-seat gun offset along the lowered arm (reach_axis; default s). shoulder_base moves the IK shoulder origin to the lowered idle's shoulder.
  timeline  the generator's own timeline, the post-seat targets offset by the lowered pose (scaled by s), the end at the lowered pose; the opener is the shipped one, with the lowered offset faded out over
            the start frames (lowover.w_start, h 0, a = release - 7), so the gun rises along the shipped wind-up direction;
  clearance every frame's gun position is kept at least eye_min_cm + clearance_margin_cm from the eye (a push along the eye ray, spread by minimum-jerk weights over clearance_frames each side);
  overlay   lowover.overlay h 0, a, b = last frame - return_frames, e = last frame; the spec carries _lowered, _idle (rest_low), _stance_only, _judge (reach judged between a and b, the shoulder against the
            lowered idle, the shipped control's raised-idle eye distance), _clearance.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest, author, rchecks, lowover
import numpy as np
from glb import Glb
from fk import Clip, qmul

NATIVE = {'s': float(os.environ.get('GA_NATIVE_S', '1.0'))} if os.environ.get('GA_NATIVE_LOWERED') else {}
if NATIVE and os.environ.get('GA_NATIVE_SR'): NATIVE['s_r'] = float(os.environ['GA_NATIVE_SR'])      # scale of the post-seat offset along the lowered arm (reach_axis); unset: s


def shoulder_base(spec, gid, body):
    """Use the lowered stance's shoulder origin for IK, keeping the raised-space gun keys.

    The v1/v1d idles translate the shoulder when the hand exceeds the arm length. Rifle raised
    idles have a different translation. Measuring the raised-origin solve against the lowered
    idle then counts this constant stance difference as pull, even with a zero gesture.
    These stances have equal clavicle rotations and arm-root offsets; refuse other rigs.
    """
    low = f"{common.path('low_clips')}/{body}/lowered_{common.gun(gid)['lowered']['pose']}.glb"
    r, l = Glb(common.mp(spec['src'])), Glb(low)
    rw, lw = Clip(r, 'idle').world(0), Clip(l, lowover.LOW_CLIP).world(0)
    result = {}
    for side in ('Right', 'Left'):
        sh, arm = r.names.index(side + 'Shoulder'), r.names.index(side + 'Arm')
        ls, la = l.names.index(side + 'Shoulder'), l.names.index(side + 'Arm')
        delta = np.array(lw[ls][0]) - rw[sh][0]
        if abs(float(np.dot(rw[sh][1], lw[ls][1]))) < 1 - 1e-8 or np.linalg.norm(lw[la][0] - rw[arm][0] - delta) > 1e-6:
            raise ValueError(f'{gid} {body} {side}: lowered shoulder needs rotational retargeting')
        result[side] = delta.tolist()
    spec['shoulder_base'] = result
    spec['_shoulder_idle'] = low


def reach_axis(low):
    """Unit vector from RightArm to RightHand in the lowered pose (world). Gun offsets along it change the arm's reach."""
    l = Glb(low); W = Clip(l, lowover.LOW_CLIP).world(0); v = np.array(W[l.names.index('RightHand')][0]) - np.array(W[l.names.index('RightArm')][0])
    return v / np.linalg.norm(v)


def clearance(P, R, gid, rest, note):
    """Eye clearance as a generation constraint (native lowered mode, every gun): where the generated gun path comes within the eye limit (checks.rreload.eye_min_cm + checks.lowered_variant.clearance_margin_cm,
    the gate's rounding), that frame's gun position is pushed out along the eye ray (eye to the closest gun point) by the shortfall; the push is spread over the neighbouring frames by minimum-jerk
    weights (clearance_frames each side, the largest weighted push wins), so the path stays smooth and no joint rate is limited. Recorded in note."""
    import manifest, lowover
    from fk import qmul
    lv = manifest.load()['checks']['lowered_variant']; lim = (manifest.load()['checks']['rreload']['eye_min_cm'] + lv['clearance_margin_cm']) / 100.0; k = int(lv['clearance_frames'])
    g = Glb(common.mp(rest)); cl = Clip(g, 'idle'); i = g.names.index('WeaponRight'); g0, q0 = cl.world(0)[i]; V = rchecks.gun_points(gid, 3000); N = len(P); D = np.zeros((N, 3))
    for f in range(N):
        t = np.array(g0) + P[f]; q = qmul(q0, author.qeuler(*R[f])); GP = rchecks.place((t, q), V); d = np.linalg.norm(GP - rchecks.EYE, axis=1); j = int(np.argmin(d))
        if d[j] < lim: D[f] = (GP[j] - rchecks.EYE) / max(float(d[j]), 1e-9) * (lim - float(d[j]))
    out = P.copy(); pushed = [f for f in range(N) if np.linalg.norm(D[f]) > 0]
    for f in range(N):
        best = np.zeros(3)
        for g_ in pushed:
            if abs(f - g_) <= k:
                v = D[g_] * lowover.mj(1.0 - abs(f - g_) / float(k + 1)) if f != g_ else D[g_]
                if np.linalg.norm(v) > np.linalg.norm(best): best = v
        out[f] = P[f] + best
    note.update({'limit_cm': round(lim * 100, 2), 'frames': pushed, 'max_push_cm': round(float(max([np.linalg.norm(D[f]) for f in pushed] or [0])) * 100, 2)})
    return out, R


def prepare(tl, c, gid, body, seat_f, m_ref):
    """Patches the timeline tl of a generator context c (rlib2.TL) in place; m_ref is a callable returning the generator's mag plan (release frame) once the pick has run. Returns the note dict (_clearance)."""
    low_ = f"{common.path('low_clips')}/{body}/lowered_{common.gun(gid)['lowered']['pose']}.glb"; Lp, Lr = lowover.gun_pose(c.rest, low_, 'Right'); to0 = tl.to
    tl.end_p = Lp; tl.end_r = Lr; sc = NATIVE.get('s', 1.0); sr = NATIVE.get('s_r', sc); note = {}
    u = reach_axis(low_)
    def post(pos):      # post-seat gun offset: the part along the lowered arm (shoulder to hand) scaled by s_r, the rest by s
        pos = np.array(pos, float); return pos * sc + (sr - sc) * float(pos @ u) * u
    def to_(f, pos, rot, *a, **k): return to0(f, post(pos) + Lp if f > seat_f else np.array(pos, float), np.array(rot, float) * (sc if f > seat_f else 1) + (Lr if f > seat_f else 0), *a, **k)
    tl.to = to_; arr0 = tl.arrays
    def kicks_(kicks):      # GA_NATIVE_SR set: post-seat kick moves lose the same share of their part along the lowered arm (Right space, before mirroring)
        if 's_r' not in NATIVE: return kicks
        for k in kicks:
            if k['f'] > seat_f: m_ = np.array(k['move'], float); k['move'] = list(m_ + (sr - 1.0) * float(m_ @ u) * u)
        return kicks
    tl.native_kicks = kicks_
    def arrays_():
        P_, R_ = arr0(); a_ = int(m_ref()['mag']['release']) - 7
        for f in range(0, a_ + 1):
            w = lowover.w_start(f, 0, a_); P_[f] = P_[f] + w * Lp; R_[f] = R_[f] + w * Lr
        P_[0] = Lp; R_[0] = Lr; P_[-1] = Lp; R_[-1] = Lr
        return clearance(P_, R_, gid, c.rest, note)
    tl.arrays = arrays_
    return Lp, Lr, note


def finish(spec, c, m, gid, body, S, name, out_root, ctl_gate_dir):
    """After author.build: the arm overlay and the spec entries. ctl_gate_dir: the folder of the shipped control clips (<dir>/<body>/<name>_gate.json)."""
    low = f"{common.path('low_clips')}/{body}/lowered_{common.gun(gid)['lowered']['pose']}.glb"; lr = f'{out_root}/../rest_low/{body}/rest_low_{gid}.glb'; os.makedirs(os.path.dirname(lr), exist_ok=True)
    lowover.rest(c.rest, low, lr); e = c.N - 1; L_ = {'h': 0, 'a': int(m['mag']['release']) - 7, 'b': e - manifest.load()['checks']['lowered_variant']['return_frames'], 'e': e, 's': NATIVE.get('s', 1.0), 's_r': NATIVE.get('s_r', NATIVE.get('s', 1.0))}
    lowover.overlay(spec['out'], 'reload_draft', low, S, c.N, L_['h'], L_['a'], L_['b'], L_['e'], lowover.arm_joints(c.rest, low)); spec['_idle'] = lr; spec['_lowered'] = dict(L_, low=low); spec['_stance_only'] = not os.environ.get('GA_NATIVE_VARIANT')      # GA_NATIVE_VARIANT=1: a variant pick (its discard offset is zero: the gun is visible already), R9 applies
    cg = f"{ctl_gate_dir}/{body}/{name}_gate.json"
    spec['_judge'] = {'reach_frames': [L_['a'], L_['b']], 'eye_idle_cm': (json.load(open(cg)).get('eye_idle_cm') if os.path.exists(cg) else None), 'low_w': [1.0] * c.N}
