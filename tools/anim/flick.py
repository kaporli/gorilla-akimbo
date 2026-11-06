"""Builds dual-wield reload clips for magazine guns, after the pistol (Lexington) dual-wield reload:
the gun tips up like the pistol's (smoothed, scaled down for long guns) while the magazine drops, then the
arm goes straight down out of view, holds there and rises straight back. This side's arm moves rigidly with
the gun, so its FK chain and IK targets always agree.

usage: flick.py <src glb> <out glb> <right|left> [lift share]
"""
import sys
import numpy as np
from glb import Glb
from fk import Clip, qinv, qmul, qrot, slerp

SRC, OUT, SIDE = sys.argv[1], sys.argv[2], sys.argv[3]
LIFT = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5   # share of the pistol's tip-up kept
FPS = 30.0
LIFT_F = 20        # pistol frames used for the tip-up (magazine out at frame 8)
DROP_S = 0.30      # seconds to go down out of view
RISE_F = (36, 69)  # pistol empty reload frames used for the rise: up from below, overshoot, settle
RISE_ROT = 0.4     # share of the pistol's rise rotation kept (muzzle up, turned in), so long barrels stay on their side
RISE_BLEND = 0.35  # share of the rise over which the gun eases from its drop pose onto the pistol path
DOWN = 0.62        # metres the gun goes down
PITCH = 30.0       # degrees the muzzle tips down on the way down, so long barrels leave the view too
OUT_M = 0.08       # metres it drifts outward on the way down
FWD_M = 0.12       # metres it moves forward on the way down, so the stock stays clear of the camera
SMOOTH = 2.5       # gaussian sigma in frames for the pistol path
FADE_F = 8         # frames over which the tip-up fades in
PLAIN_F = 12       # plain variant (_02 clips, shell-by-shell guns): frames to go straight down, no tip-up
OPEN_F = 36        # the tip-up is stretched over this many frames (1.2 s, GorillaAkimboReload.OpenEnd) so the magazine
                   # has time to fall before the drop; the script picks the playback speed per gun
PRE_F = 105        # clip frames before the rise (3.5 s, GorillaAkimboReload.HoldEnd): the drop ends by frame 45 (DropEnd),
                   # then a hold the script fast-forwards so the rise starts when the gun's ammo lands
SUFFIX = '' if SIDE == 'right' else '_l'
S, s = ('Right', 'right') if SIDE == 'right' else ('Left', 'left')
TOPS = [f'{S}Shoulder', f'arm_{s}_ik', f'Torso_World_{S}Arm_Hand_IK_JNT', f'Torso_World_{S}Arm_PoleVector_JNT',
        f'Torso_{S}Arm_Hand_IK_JNT', f'Torso_{S}Arm_PoleVector_JNT']
GUN = f'Weapon{S}'
# Output clip -> pistol clip it takes the tip-up from (lengths come from PRE_F and the rise).
CLIPS = {'reload': ('reload', 0), 'reload_01': ('reload', 0), 'reload_02': ('reload', 0),
         'empty_reload': ('empty_reload', 0), 'empty_reload_01': ('empty_reload', 0),
         'empty_reload_02': ('empty_reload', 0)}
IDENT = np.array([0.0, 0.0, 0.0, 1.0])


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def smooth_path(P, Q, sigma):
    n = len(P)
    k = np.exp(-0.5 * (np.arange(-4, 5) / sigma) ** 2)
    Ps, Qs = [], []
    for i in range(n):
        w, p, q = 0.0, np.zeros(3), np.zeros(4)
        for j, kj in zip(range(i - 4, i + 5), k):
            jj = min(max(j, 0), n - 1)
            qq = Q[jj] if np.dot(Q[jj], Q[i]) >= 0 else -Q[jj]
            p += kj * P[jj]; q += kj * qq; w += kj
        Ps.append(p / w); Qs.append(q / np.linalg.norm(q))
    return Ps, Qs


g = Glb(SRC)
src_g = Glb(SRC)  # untouched copy to read from: g's clips are replaced as the loop goes
nodes = g.j['nodes']
idx = {n: i for i, n in enumerate(g.names)}
tops = [idx[t] for t in TOPS]
gun = idx[GUN]
out_dir = np.array([1.0, 0.0, 0.0]) if SIDE == 'right' else np.array([-1.0, 0.0, 0.0])


def subtree(i, out):
    out.add(i)
    for c in nodes[i].get('children', []):
        subtree(c, out)
    return out


side = set()
for t in tops:
    subtree(t, side)

for name, (src, n) in CLIPS.items():
    plain = name.endswith('_02')
    name += SUFFIX
    c = Clip(src_g, src + SUFFIX)
    rest = c.world(0)
    g0, q0 = rest[gun]
    # Pistol gun path over the tip-up, smoothed, as a scaled offset from the rest pose.
    raw = [c.world(f)[gun] for f in range(LIFT_F + 5)]
    P, Q = smooth_path([p for p, _ in raw], [q for _, q in raw], SMOOTH)
    lift = []
    for f in range(LIFT_F + 1):
        # Fade the offset in over the first frames so the clip starts exactly at rest.
        k = LIFT * ease(f / FADE_F)
        lift.append((g0 + (P[f] - g0) * k, slerp(IDENT, qmul(Q[f], qinv(q0)), k)))
    th = np.radians(-PITCH) / 2  # about the model X axis; negative lowers the muzzle (glTF: -Z forward)
    drop = (g0 + np.array([0.0, -DOWN, -FWD_M]) + out_dir * OUT_M, np.array([np.sin(th), 0.0, 0.0, np.cos(th)]))
    # Pistol rise from the empty reload, smoothed, as offsets from rest; the residual at its end is faded out.
    ce = Clip(src_g, 'empty_reload' + SUFFIX)
    q0e = ce.world(0)[gun][1]
    g0e = ce.world(0)[gun][0]
    rr = [ce.world(f)[gun] for f in range(RISE_F[0] - 4, RISE_F[1] + 5)]
    RP, RQ = smooth_path([p for p, _ in rr], [q for _, q in rr], SMOOTH)
    RP, RQ = RP[4:-4], RQ[4:-4]
    nr = len(RP)
    endp, endq = RP[-1] - g0e, qmul(RQ[-1], qinv(q0e))
    rise = []
    for j in range(nr):
        u = j / (nr - 1)
        dp = (RP[j] - g0e) - endp * u
        dq = slerp(qmul(RQ[j], qinv(q0e)), qmul(qmul(RQ[j], qinv(q0e)), qinv(endq)), u)
        path = (g0 + dp, slerp(IDENT, dq, RISE_ROT))
        w = ease(u / RISE_BLEND)
        rise.append((drop[0] + (path[0] - drop[0]) * w, slerp(drop[1], path[1], w)))
    rise[-1] = (g0, IDENT)
    n = PRE_F + nr
    rise_f0 = PRE_F
    drop_end = OPEN_F + DROP_S * FPS
    # Gun offset per output frame: (gun position, rotation relative to rest).
    offs = []
    for f in range(n):
        t = f / FPS
        if plain and f < rise_f0:
            u = ease(f / PLAIN_F)
            offs.append(((g0 + (drop[0] - g0) * u), slerp(IDENT, drop[1], u)))
        elif f <= OPEN_F:
            # The pistol's tip-up, stretched over OPEN_F frames (sampled between its frames).
            x = f / OPEN_F * LIFT_F
            i0 = min(int(x), LIFT_F - 1); w = x - i0
            a, b = lift[i0], lift[i0 + 1]
            offs.append((a[0] + (b[0] - a[0]) * w, slerp(a[1], b[1], w)))
        elif f <= drop_end:
            u = ease((f - OPEN_F) / (drop_end - OPEN_F))
            a = lift[LIFT_F]
            offs.append((a[0] + (drop[0] - a[0]) * u, slerp(a[1], drop[1], u)))
        elif f < rise_f0:
            offs.append(drop)
        else:
            offs.append(rise[f - rise_f0])

    times = np.arange(n) / FPS
    t_in = g.add_acc(times, 'SCALAR')
    t_one = g.add_acc(np.array([0.0]), 'SCALAR')
    tmpl = src_g.anim(src + SUFFIX)
    animated = {ch['target']['node'] for ch in tmpl['channels']}
    samplers, channels = [], []

    def channel(i, path, vals, keys):
        samplers.append({'input': keys, 'output': g.add_acc(vals, 'VEC3' if path == 'translation' else 'VEC4'),
                         'interpolation': 'LINEAR'})
        channels.append({'sampler': len(samplers) - 1, 'target': {'node': i, 'path': path}})

    for i in sorted(animated):
        lt, lr = c.local(i, 0)
        if i in tops:
            pw = rest[c.par[i]]
            pj, qj = rest[i]
            ts, rs = [], []
            for gp, rd in offs:
                wp = gp + qrot(rd, pj - g0)      # rigid move around the gun
                wq = qmul(rd, qj)
                ts.append(qrot(qinv(pw[1]), wp - pw[0])); rs.append(qmul(qinv(pw[1]), wq))
            channel(i, 'translation', np.array(ts), t_in)
            channel(i, 'rotation', np.array(rs), t_in)
        else:
            channel(i, 'translation', lt[None, :], t_one)
            channel(i, 'rotation', lr[None, :], t_one)

    a = g.anim(name)
    ex = dict(tmpl['extras'])
    # No sounds in the arm clips: the script plays each weapon's own reload sounds.
    ex['animEvents'] = [e for e in ex.get('animEvents') or [] if e.get('type') != 'Sound']
    # Fallback frame indices point into the set's table of fallback poses, which is the vanilla one: keep the
    # slots of the vanilla clip this one replaces. Other slots belong to other clips and crash the game when sampled.
    ex['fallbackFrameIndices'] = list(src_g.anim(name)['extras'].get('fallbackFrameIndices') or [])
    ex['optimizationHints'] = dict(ex.get('optimizationHints', {}), preferSIMD=True)
    a['samplers'], a['channels'], a['extras'] = samplers, channels, ex
    print(name, n, 'frames from', src + SUFFIX)

g.save(OUT)
print('saved', OUT)
