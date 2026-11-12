"""End-pose fix for the top-magazine arm clips: over the rise (F0..F1) the arms flow into the dual-wield idle pose
(idlepose_shoulder of <body>_w_handgun_dual_wield_base.anims) that the graph returns to after the reload.
Hands and guns keep their path (a sub-mm/0.1 deg constant correction is eased in so the last frame is exact).
The shoulders (clavicles), elbow swivel and arm twist ease from the clip's own solution to an IK solution that uses
the idle pose as its rest pose; the IK and pole-vector helper joints ease to the idle ones carried with the hand.
Frames before F0 are copied unchanged.

usage: fix_endpose.py <clip glb> <out glb> [--body pma|pwa] [--idle <glb>] [F0 F1]
  --body  default: the clip's parent folder name. The idle glb is the game's dual-wield base set of that body.
  F0 F1   default: the top-magazine gun's seated frame and last frame (weapons.json topmag.frames: 62, 95).
All clips of a folder: batch.py."""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import numpy as np
from glb import Glb
from fk import Clip, qmul, qinv, qrot, slerp


def window(clip_name=None):
    """(F0, F1) of a clip by its file name: the frames of the top-magazine gun it is named after."""
    tm = common.manifest.topmag_guns(enabled_only=False)
    fr = next((g['topmag']['frames'] for name, _, _, g in tm if clip_name and os.path.basename(clip_name).startswith(name + '_')), None)
    fr = fr or next(g['topmag']['frames'] for _, _, _, g in common.manifest.topmag_guns())
    return fr['seated'], fr['length'] - 1


def fix(CLIP, IDLE, OUT, F0, F1):

    g = Glb(CLIP); a0 = g.j['animations'][0]; NAME = a0['name']; c = Clip(g, NAME); N = c.frames
    names = g.names; ix = {n: i for i, n in enumerate(names)}
    ig = Glb(IDLE); ic = Clip(ig, 'idlepose_shoulder'); iix = {n: i for i, n in enumerate(ig.names)}
    IW = ic.world(0)


    def idle_w(n): return IW[iix[n]]
    def idle_l(n): return ic.local(iix[n], 0)


    def wcurve(f):
        s = min(max((f - F0) / (F1 - F0), 0.0), 1.0)
        return s * s * s * (s * (6 * s - 15) + 10)


    def qn(q): return q / np.linalg.norm(q)


    def qalign(a, b):
        """shortest rotation taking unit a to unit b"""
        v = np.cross(a, b); d = float(np.dot(a, b))
        if d < -0.999999:
            p = np.cross(a, [1, 0, 0])
            if np.linalg.norm(p) < 1e-6: p = np.cross(a, [0, 1, 0])
            p /= np.linalg.norm(p); return np.array([*p, 0.0])
        return qn(np.array([*v, 1 + d]))


    def mul(A, B):  # rigid (t, q)
        return (A[0] + qrot(A[1], B[0]), qmul(A[1], B[1]))


    def inv(A):
        qi = qinv(A[1]); return (-qrot(qi, A[0]), qi)


    def blend(A, B, w):
        return (A[0] * (1 - w) + B[0] * w, slerp(qn(A[1]), qn(B[1]), w))


    def qpow(q, w):  # slerp from identity
        return slerp(np.array([0, 0, 0, 1.0]), qn(q), w)


    SIDES = []
    for S in ('Right', 'Left'):
        s = S.lower()
        helpers = [n for n in (f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_Hand_IK_JNT',
                               f'Torso_World_{S}Arm_PoleVector_JNT', f'Torso_{S}Arm_PoleVector_JNT') if n in ix and n in iix]
        SIDES.append((S, f'{S}Shoulder', f'{S}Arm', f'{S}ForeArm', f'{S}Hand', helpers))
    CHAIN = {n for S in SIDES for n in S[1:5]}
    HELP = {n for S in SIDES for n in S[5]}
    # other joints whose last frame differs from the idle (helper offset spaces): eased to the idle local
    OTHER = []
    for i, n in enumerate(names):
        if n in CHAIN or n in HELP or n not in iix: continue
        tl, ql = c.local(i, N - 1); ti, qi = idle_l(n)
        if np.linalg.norm(tl - ti) > 1e-5 or abs(abs(float(np.dot(qn(ql), qn(qi)))) - 1) > 1e-7:
            OTHER.append(n)

    # constant hand correction so the last frame is the exact idle hand: C = H95^-1 * H_idle
    W95 = c.world(N - 1)
    HC = {S: mul(inv(W95[ix[hd]]), idle_w(hd)) for S, cl, ua, fa, hd, h in SIDES}


    def solve_frame(f):
        w = wcurve(f)
        Wo = c.world(f)
        over = {}
        for n in OTHER:
            over[ix[n]] = blend(c.local(ix[n], f), idle_l(n), w)
        Wb = c.world(f, local=over) if over else Wo
        final_world = {}
        for S, cl, ua, fa, hd, helpers in SIDES:
            par = Wb[c.par[ix[cl]]]
            t_ua = c.local(ix[ua], f)[0]; t_fa = c.local(ix[fa], f)[0]; t_hd = c.local(ix[hd], f)[0]
            L1, L2 = np.linalg.norm(t_fa), np.linalg.norm(t_hd)
            # hand: original path with the constant correction eased in
            Ho = Wo[ix[hd]]; C = HC[S]
            Hf = mul(Ho, (C[0] * w, qpow(C[1], w)))
            Ph = Hf[0]
            # original chain
            cl_l_o = c.local(ix[cl], f)
            Ps_o, Pe_o = Wo[ix[ua]][0], Wo[ix[fa]][0]
            Ru_o, Rf_o = Wo[ix[ua]][1], Wo[ix[fa]][1]
            # idle-rest IK for the same hand (author.py's two-bone solve with the idle as rest)
            cl_l_i = (cl_l_o[0], idle_l(cl)[1])
            clw_i = mul(par, cl_l_i); Ps_i = mul(clw_i, (t_ua, np.array([0, 0, 0, 1.0])))[0]
            S0, E0, H0 = idle_w(ua)[0], idle_w(fa)[0], idle_w(hd)[0]
            d = np.linalg.norm(Ph - Ps_i); shift = np.zeros(3)
            if d > (L1 + L2) * 0.995:
                u = (Ph - Ps_i) / d; shift = u * (d - (L1 + L2) * 0.995); Ps_i = Ps_i + shift; d = (L1 + L2) * 0.995
            u = (Ph - Ps_i) / d
            x = (L1 * L1 - L2 * L2 + d * d) / (2 * d); h = math.sqrt(max(L1 * L1 - x * x, 0))
            pole = E0 - S0; pole = pole - u * np.dot(pole, u); pole /= np.linalg.norm(pole)
            Pe_i = Ps_i + u * x + pole * h
            Ru_i = qmul(qalign((E0 - S0) / L1, (Pe_i - Ps_i) / L1), idle_w(ua)[1])
            # twist from the pole plane: rotate about the bone so the plane normal matches (as author.py's aim())
            def plane_fix(R, bone, n_rest_world, n_new):
                # R maps rest frame; make R*(R_rest^-1 n_rest) align with n_new around 'bone'
                cur = qrot(R, n_rest_world); cur = cur - bone * np.dot(cur, bone); tgt = n_new - bone * np.dot(n_new, bone)
                if np.linalg.norm(cur) < 1e-9 or np.linalg.norm(tgt) < 1e-9: return R
                cur /= np.linalg.norm(cur); tgt /= np.linalg.norm(tgt)
                ang = math.atan2(np.dot(np.cross(cur, tgt), bone), np.dot(cur, tgt))
                return qmul(np.array([*(bone * math.sin(ang / 2)), math.cos(ang / 2)]), R)
            pr = np.cross(E0 - S0, H0 - E0); pr /= np.linalg.norm(pr)
            pn = np.cross(Pe_i - Ps_i, Ph - Pe_i); pn /= np.linalg.norm(pn)
            bu = (Pe_i - Ps_i) / L1
            Ru_i = plane_fix(Ru_i, bu, qrot(qinv(idle_w(ua)[1]), pr), pn)
            bf = (Ph - Pe_i) / L2
            Rf_i = qmul(qalign((H0 - E0) / L2, bf), idle_w(fa)[1])
            Rf_i = plane_fix(Rf_i, bf, qrot(qinv(idle_w(fa)[1]), pr), pn)
            # blend: clavicle local, then swivel and twist about the final bones
            cl_l_f = (cl_l_o[0], slerp(qn(cl_l_o[1]), qn(cl_l_i[1]), w))
            clw_f = mul(par, cl_l_f)
            Ps_f = mul(clw_f, (t_ua, np.array([0, 0, 0, 1.0])))[0] + shift * w
            clw_f = (clw_f[0] + shift * w, clw_f[1])
            d = np.linalg.norm(Ph - Ps_f)
            if d > (L1 + L2) * 0.9999: raise SystemExit(f'out of reach at f{f} {S}')
            ax = (Ph - Ps_f) / d
            x = (L1 * L1 - L2 * L2 + d * d) / (2 * d); h = math.sqrt(max(L1 * L1 - x * x, 0))
            vo = Pe_o - Ps_o; vo = vo - ax * np.dot(vo, ax); vo /= np.linalg.norm(vo)
            vi = Pe_i - Ps_i; vi = vi - ax * np.dot(vi, ax); vi /= np.linalg.norm(vi)
            ang = math.atan2(np.dot(np.cross(vo, vi), ax), np.dot(vo, vi)) * w
            vf = qrot(np.array([*(ax * math.sin(ang / 2)), math.cos(ang / 2)]), vo)
            Pe_f = Ps_f + ax * x + vf * h
            bu = (Pe_f - Ps_f) / L1; bf = (Ph - Pe_f) / L2
            A = qmul(qalign(qrot(Ru_o, t_fa / L1), bu), Ru_o); B = qmul(qalign(qrot(Ru_i, t_fa / L1), bu), Ru_i)
            Ru_f = slerp(qn(A), qn(B), w)
            A = qmul(qalign(qrot(Rf_o, t_hd / L2), bf), Rf_o); B = qmul(qalign(qrot(Rf_i, t_hd / L2), bf), Rf_i)
            Rf_f = slerp(qn(A), qn(B), w)
            final_world[cl] = clw_f
            final_world[ua] = (Ps_f, Ru_f)
            final_world[fa] = (Pe_f, Rf_f)
            final_world[hd] = Hf
            # helpers: original world eased to the idle helper carried with the hand
            Hi = idle_w(hd)
            for n in helpers:
                tgt = mul(Hf, mul(inv(Hi), idle_w(n)))
                final_world[n] = blend(Wo[ix[n]], tgt, w)
        # locals, top-down
        loc = {}
        Wn = dict(Wb)
        order = sorted(CHAIN | HELP | set(OTHER), key=lambda n: depth(ix[n]))
        for n in order:
            i = ix[n]
            if n in OTHER and n not in final_world:
                loc[n] = over[i]
                Wn[i] = mul(Wn[c.par[i]], over[i])
                continue
            pw = Wn[c.par[i]]
            L = mul(inv(pw), final_world[n])
            loc[n] = (L[0], qn(L[1]))
            Wn[i] = final_world[n]
        return loc


    def depth(i):
        k = 0
        while i in c.par: i = c.par[i]; k += 1
        return k


    MOD = sorted(CHAIN | HELP | set(OTHER), key=lambda n: ix[n])
    vals = {n: ([], []) for n in MOD}
    for f in range(N):
        if f < F0:
            for n in MOD:
                t, q = c.local(ix[n], f); vals[n][0].append(t); vals[n][1].append(q)
        else:
            L = solve_frame(f)
            for n in MOD:
                t, q = L[n]
                # keep quaternion sign continuous with the previous frame
                if np.dot(q, vals[n][1][-1]) < 0: q = -q
                vals[n][0].append(t); vals[n][1].append(q)

    t_in = g.add_acc(np.arange(N) / 30.0, 'SCALAR')
    done = set()
    for ch in a0['channels']:
        n = names[ch['target']['node']]
        if n not in vals: continue
        p = ch['target']['path']
        arr = np.array(vals[n][0] if p == 'translation' else vals[n][1])
        s = a0['samplers'][ch['sampler']]
        s['input'] = t_in; s['output'] = g.add_acc(arr, 'VEC3' if p == 'translation' else 'VEC4'); s['interpolation'] = 'LINEAR'
        done.add((n, p))
    for n in MOD:
        for p in ('translation', 'rotation'):
            if (n, p) not in done:
                arr = np.array(vals[n][0] if p == 'translation' else vals[n][1])
                a0['samplers'].append({'input': t_in, 'output': g.add_acc(arr, 'VEC3' if p == 'translation' else 'VEC4'), 'interpolation': 'LINEAR'})
                a0['channels'].append({'sampler': len(a0['samplers']) - 1, 'target': {'node': ix[n], 'path': p}})
    g.save(OUT)
    return len(MOD), OTHER


if __name__ == '__main__':
    argv = sys.argv[1:]
    body = common.opt(argv, '--body'); idle = common.opt(argv, '--idle')
    clip, out = argv[:2]
    body = body or os.path.basename(os.path.dirname(os.path.abspath(clip)))
    f0, f1 = (int(argv[2]), int(argv[3])) if len(argv) > 3 else window(clip)
    n, other = fix(clip, idle or common.need(common.idle_glb(body)), out, f0, f1)
    print('saved', out, 'modified', n, 'joints; other:', other)
