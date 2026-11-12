"""Two-handed dual-wield clip author: gun paths per hand (keyframed offsets from the idle pose), arms solved with
two-bone IK (shoulders fixed unless out of reach), IK helper joints carried with the hand.

usage: author.py <spec.json> [--out clip.glb]
module: setup(spec), then gun_pose(S, f), solve(f), rest, idx, DIAG, ELB; build(spec, out=None) writes the clip.

spec:
  src        rig and template glb; absent: the Lexington dual-wield set of body (pma default)
  template   animation of src whose frame 0 is the idle pose and whose other joints are copied
  clip, frames, out   name and length of the new clip, output glb
  keys       {Left|Right: [[f, [dx,dy,dz], [pitch,yaw,roll]], ...]} gun offset from its idle pose, Catmull-Rom
             optional 4th angle: bank about the idle z axis (d04)
             optional 4th element {vin, vout, rin, rout}: tangents per frame arriving at / leaving the key (L04)
  shakes     {side: [{f, move, rot, hz, decay}]} damped oscillation; type "kick": {f, move, rot, attack, release, lag}
             recoil (fast attack, smooth return, peak 1)
  bumps      {side: [{f: [f0,f1,f2,f3], move}]} world translation, smoothstep in f0..f1, held to f2, out to f3 (author_p)
  turns      {side: [{f: [f0,f1,f2,f3], rot: [x,y,z], about: [x,y,z]}]} world rotation (rotation vector, degrees) of
             the gun about one of its points (gun-local), after keys, shakes and bumps; window as bumps
  twist_share  share of the hand twist put into the forearm bone (author10)
  shoulder   {side: [{f: [f0,f1,f2,f3], move}]} shoulder offset, windows as bumps (author_a)
  pole, swivel  {side: [[f, deg], ...]} elbow swivel about the shoulder-hand axis (author_a pole, author_h swivel;
             the value may be deg or [deg])
  elbow      {side: [[f, [x,y,z]], ...]} pole bias in world axes (v02)
  pole_tilt  k: elbow reference = the rest elbow offset from the rest shoulder-hand line, minus k times that line
             (tilted back). Same elbow as without it in the rest pose. Without it the reference is the rest upper
             arm, which lines up with the shoulder-hand line when the hand goes down to the belt or hip, and the
             elbow flips to the other side in one frame (rifle reloads; 0.6 used there).
  reach      [r0, rmax] soft reach cap: above r0 of the arm length the clavicle turns toward the hand, by at most
             protract_max degrees (40); lock (0.995) is the ratio past which the shoulder translates (L08).
             Only active when reach or protract_max is in the spec.
Offsets in metres, glTF axes (x right, y up, z back); angles in degrees about the gun's own x, y, z."""
import os, sys, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, qrot

spec = src = names = idx = tc = rest = N = None
SIDES = {}
DIAG = {}   # (side, frame): (hand twist about the forearm in degrees, swing in degrees)
ELB = {}    # (side, frame): (elbow angle, reach ratio, shoulder joint move, shoulder shift); reach specs only


def src_path(sp):
    return sp.get('src') or common.reload_glb(sp.get('body', 'pma'), 'right')


def setup(sp):
    """Loads the rig of a spec. The functions below work on the last spec set up."""
    global spec, src, names, idx, tc, rest, N
    spec = sp; src = Glb(common.need(src_path(sp)))
    names = src.names; idx = {n: i for i, n in enumerate(names)}
    tc = Clip(src, sp['template'])
    rest = tc.world(0)
    N = sp['frames']
    SIDES.clear(); DIAG.clear(); ELB.clear()
    for S in ('Left', 'Right'):
        s = S.lower()
        ch = [idx[n] for n in (f'{S}Shoulder', f'{S}Arm', f'{S}ForeArm', f'{S}Hand', f'Weapon{S}')]
        hn = (f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT', f'Torso_World_{S}Arm_PoleVector_JNT',
              f'Torso_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_PoleVector_JNT')
        SIDES[S] = (ch, [idx[n] for n in hn if n in idx])


def qaxis(ax, deg):
    h = math.radians(deg) / 2; v = np.zeros(3); v['xyz'.index(ax)] = 1
    return np.array([*(v * math.sin(h)), math.cos(h)])


def qeuler(p, y, r, b=0.0):
    """pitch, yaw, roll about the gun's own axes; b = bank about the idle z axis, applied last."""
    q = qmul(qaxis('x', p), qmul(qaxis('y', y), qaxis('z', r)))
    return qmul(qaxis('z', b), q) if b else q


def hermite(keys, f):
    """Catmull-Rom through the keys; flat at the ends and at holds (a key equal to its neighbour).
    keys: (frame, value[, vin, vout]); vin/vout (per frame) override the tangent arriving at / leaving that key."""
    fs = [k[0] for k in keys]; vs = [np.array(k[1], float) for k in keys]
    vi = [None if len(k) < 3 or k[2] is None else np.array(k[2], float) for k in keys]
    vo = [None if len(k) < 4 or k[3] is None else np.array(k[3], float) for k in keys]
    if f <= fs[0]: return vs[0]
    if f >= fs[-1]: return vs[-1]
    i = max(j for j in range(len(fs)) if fs[j] <= f)
    L = fs[i + 1] - fs[i]
    def tan(j, side):
        ov = (vo if side == 'out' else vi)[j]
        if ov is not None: return ov * L
        if j == 0 or j == len(vs) - 1: return np.zeros_like(vs[j])
        if np.allclose(vs[j], vs[j - 1]) or np.allclose(vs[j], vs[j + 1]): return np.zeros_like(vs[j])
        return (vs[j + 1] - vs[j - 1]) / (fs[j + 1] - fs[j - 1]) * L
    p1, p2, m1, m2 = vs[i], vs[i + 1], tan(i, 'out'), tan(i + 1, 'in')
    t = (f - fs[i]) / L; t2, t3 = t * t, t * t * t
    return (2*t3 - 3*t2 + 1) * p1 + (t3 - 2*t2 + t) * m1 + (-2*t3 + 3*t2) * p2 + (t3 - t2) * m2


def quat_of(M):
    t = np.trace(M)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return np.array([(M[2, 1] - M[1, 2]) / s, (M[0, 2] - M[2, 0]) / s, (M[1, 0] - M[0, 1]) / s, s / 4])
    i = int(np.argmax([M[0, 0], M[1, 1], M[2, 2]])); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + M[i, i] - M[j, j] - M[k, k]) * 2; q = np.zeros(4)
    q[i] = s / 4; q[j] = (M[j, i] + M[i, j]) / s; q[k] = (M[k, i] + M[i, k]) / s; q[3] = (M[k, j] - M[j, k]) / s
    return q


def aim(d, up):
    x = d / np.linalg.norm(d); y = up - x * np.dot(up, x); y /= np.linalg.norm(y)
    return np.stack([x, y, np.cross(x, y)], 1)


def bump_w(fw, f):
    """Window weight: smoothstep in over f0..f1, 1 to f2, out over f2..f3."""
    a0, a1, a2, a3 = fw
    if f <= a0 or f >= a3: return 0.0
    if f < a1: t = (f - a0) / (a1 - a0); return t * t * (3 - 2 * t)
    if f <= a2: return 1.0
    t = (a3 - f) / (a3 - a2); return t * t * (3 - 2 * t)


def gun_pose(S, f):
    """World position and rotation of a gun at frame f."""
    keys = spec['keys'].get(S) or [[0, [0, 0, 0], [0, 0, 0]]]
    o = lambda k, n: (k[3].get(n) if len(k) > 3 else None)
    dp = hermite([(k[0], k[1], o(k, 'vin'), o(k, 'vout')) for k in keys], f)
    de = hermite([(k[0], k[2], o(k, 'rin'), o(k, 'rout')) for k in keys], f)
    for sh in spec.get('shakes', {}).get(S, []):
        t = f - sh['f']
        if t < 0: continue
        if sh.get('type') == 'kick':
            # recoil: fast attack, smooth exponential return, no oscillation; normalised to peak 1
            ta, tr = sh.get('attack', 0.8), sh.get('release', 6.0)
            def kick(t, ta, tr):
                tp = ta * math.log(1 + tr / ta)
                peak = (1 - math.exp(-tp / ta)) * math.exp(-tp / tr)
                return (1 - math.exp(-t / ta)) * math.exp(-t / tr) / peak
            k1 = kick(t, ta, tr); k2 = kick(max(t - sh.get('lag', 0.7), 0), ta * 1.3, tr * 1.2)
        else:
            w = 2 * math.pi * sh.get('hz', 6) / 30.0
            env = math.exp(-t / sh.get('decay', 5))
            k1 = env * math.sin(w * t); k2 = env * math.sin(w * t - 0.9)
        dp = dp + np.array(sh.get('move', [0, 0, 0])) * k1
        rk = np.zeros_like(de); rr = np.array(sh.get('rot', [0, 0, 0]), float); rk[:len(rr)] = rr
        de = de + rk * k2
    for b in spec.get('bumps', {}).get(S, []):
        dp = dp + np.array(b['move']) * bump_w(b['f'], f)
    g0, q0 = rest[SIDES[S][0][4]]
    gp, gq = g0 + dp, qmul(q0, qeuler(*de))
    for t in spec.get('turns', {}).get(S, []):
        # world rotation (rotation vector in degrees) about a point of the gun (gun-local), window as bumps
        w = bump_w(t['f'], f); rv = np.array(t['rot'], float) * w; a = np.linalg.norm(rv)
        if a < 1e-9: continue
        h = math.radians(a) / 2; qd = np.array([*(rv / a * math.sin(h)), math.cos(h)])
        c = gp + qrot(gq, np.array(t['about'], float))
        gp, gq = c + qrot(qd, gp - c), qmul(qd, gq)
    return gp, gq


def solve(f):
    """{joint index: (local translation, local rotation)} of the arm joints at frame f."""
    W = dict(rest); loc = {}
    soft = 'reach' in spec or 'protract_max' in spec
    for S, (ch, helpers) in SIDES.items():
        sh, ua, fa, hd, gn = ch
        gp, gq = gun_pose(S, f)
        g0, q0 = rest[gn]; hp0, hq0 = rest[hd]
        hq = qmul(gq, qmul(qinv(q0), hq0)); hp = gp + qrot(gq, qrot(qinv(q0), hp0 - g0))
        S0, E0 = rest[ua][0], rest[fa][0]
        a = np.linalg.norm(E0 - S0); b = np.linalg.norm(hp0 - E0)
        shift = np.zeros(3)
        for bb in spec.get('shoulder', {}).get(S, []):
            shift = shift + np.array(bb['move']) * bump_w(bb['f'], f)
        Sp = S0 + shift; d = np.linalg.norm(hp - Sp); qcl = None
        if soft:
            # above r0 the clavicle turns about its root to carry the arm joint toward the hand; the elbow keeps a bend
            r0, rmax = spec.get('reach', [0.9, 0.975]); r = d / (a + b)
            if r > r0:
                re = r0 + (rmax - r0) * math.tanh((r - r0) / (rmax - r0)); want = re * (a + b)
                Cr = rest[sh][0]; v = Sp - Cr; t = hp - Cr
                n = np.cross(v, t); n /= np.linalg.norm(n)
                def at(th):
                    h = th / 2; q = np.array([*(n * math.sin(h)), math.cos(h)]); return q, Cr + qrot(q, v)
                lo_, hi_ = 0.0, math.radians(spec.get('protract_max', 40))
                for _ in range(40):
                    mid = (lo_ + hi_) / 2
                    if np.linalg.norm(hp - at(mid)[1]) > want: lo_ = mid
                    else: hi_ = mid
                qcl, Sp = at(hi_); d = np.linalg.norm(hp - Sp)
        lk = spec.get('lock', 0.995) if soft else 0.995
        if d > (a + b) * lk:
            u = (hp - Sp) / d; ex = u * (d - (a + b) * lk); shift = shift + ex; Sp = Sp + ex; d = (a + b) * lk
        u = (hp - Sp) / d
        x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(a * a - x * x, 0))
        pole = E0 - S0
        if spec.get('pole_tilt') is not None:
            ur = (hp0 - S0) / np.linalg.norm(hp0 - S0); pole = pole - ur * np.dot(pole, ur)
            pole = pole / np.linalg.norm(pole) - spec['pole_tilt'] * ur
        if 'elbow' in spec:
            pole = pole / np.linalg.norm(pole); ek = spec['elbow'].get(S)
            if ek: pole = pole + hermite([(k[0], k[1]) for k in ek], f)
        pole = pole - u * np.dot(pole, u); pole /= np.linalg.norm(pole)
        for key in ('pole', 'swivel'):
            pk = spec.get(key, {}).get(S)
            if pk:
                pa = math.radians(float(hermite([(k[0], k[1] if isinstance(k[1], list) else [k[1]]) for k in pk], f)[0]))
                pole = pole * math.cos(pa) + np.cross(u, pole) * math.sin(pa)
        Ep = Sp + u * x + pole * h
        pr = np.cross(E0 - S0, hp0 - E0); pn = np.cross(Ep - Sp, hp - Ep)
        Rua = aim(Ep - Sp, pn) @ aim(E0 - S0, pr).T
        Rfa = aim(hp - Ep, pn) @ aim(hp0 - E0, pr).T
        qfa = qmul(quat_of(Rfa), rest[fa][1])
        # hand twist about the forearm axis (vs the rest relation); a share of it goes into the forearm bone (pronation)
        uf = (hp - Ep) / np.linalg.norm(hp - Ep)
        rel = qmul(hq, qinv(qmul(qfa, qmul(qinv(rest[fa][1]), hq0))))
        if rel[3] < 0: rel = -rel
        tw = 2 * math.atan2(np.dot(rel[:3], uf), rel[3])
        sw = 2 * math.degrees(math.acos(min(1, math.sqrt(rel[3] ** 2 + np.dot(rel[:3], uf) ** 2))))
        DIAG[(S, f)] = (math.degrees(tw), sw)
        if soft:
            ELB[(S, f)] = (math.degrees(math.acos(np.clip(np.dot((Sp - Ep) / a, (hp - Ep) / np.linalg.norm(hp - Ep)), -1, 1))), d / (a + b), Sp - S0, np.linalg.norm(shift))
        share = spec.get('twist_share', 0.0)
        if share:
            h = tw * share / 2; qfa = qmul(np.array([*(uf * math.sin(h)), math.cos(h)]), qfa)
        world = {sh: (rest[sh][0] + shift, rest[sh][1] if qcl is None else qmul(qcl, rest[sh][1])),
                 ua: (Sp, qmul(quat_of(Rua), rest[ua][1])), fa: (Ep, qfa), hd: (hp, hq)}
        for hj in helpers:
            jp, jq = rest[hj]
            world[hj] = (hp + qrot(hq, qrot(qinv(hq0), jp - hp0)), qmul(hq, qmul(qinv(hq0), jq)))
        for n in [sh, ua, fa, hd] + helpers:
            pw = W[tc.par[n]]; t, q = world[n]
            loc[n] = (qrot(qinv(pw[1]), t - pw[0]), qmul(qinv(pw[1]), q))
            W[n] = world[n]
    return loc


def build(sp, out=None):
    """Solves every frame and writes the clip glb (the template's other joints at their frame 0 values)."""
    setup(sp)
    out = out or sp['out']
    g = Glb(src_path(sp))
    frames = [solve(f) for f in range(N)]
    times = np.arange(N) / 30.0
    t_in = g.add_acc(times, 'SCALAR'); t_one = g.add_acc(np.array([0.0]), 'SCALAR')
    tmpl = src.anim(sp['template'])
    animated = {c['target']['node'] for c in tmpl['channels']} | set(frames[0].keys())
    samplers, channels = [], []

    def channel(i, path, vals, keys):
        samplers.append({'input': keys, 'output': g.add_acc(vals, 'VEC3' if path == 'translation' else 'VEC4'),
                         'interpolation': 'LINEAR'})
        channels.append({'sampler': len(samplers) - 1, 'target': {'node': i, 'path': path}})

    for i in sorted(animated):
        if i in frames[0]:
            channel(i, 'translation', np.array([fr[i][0] for fr in frames]), t_in)
            channel(i, 'rotation', np.array([fr[i][1] for fr in frames]), t_in)
        else:
            lt, lr = tc.local(i, 0)
            channel(i, 'translation', lt[None, :], t_one); channel(i, 'rotation', lr[None, :], t_one)
    a = g.anim(sp['template'])
    a['name'] = sp['clip']; a['samplers'], a['channels'] = samplers, channels
    g.j['animations'] = [a]
    g.save(out)
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]; o = common.opt(argv, '--out')
    print('saved', build(json.load(open(argv[0])), o), N, 'frames')
