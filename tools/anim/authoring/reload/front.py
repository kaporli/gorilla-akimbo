"""Category FRONT: front box magazine pulled straight down (Copperhead, Umbra, Sidewinder; Ajax and Kyubi with their
own timing). Ten one-handed right-hand drafts. Each function takes a context (rlib.Ctx) and returns the motion.

Frames come from the gun's own reload clip (ctx.T): o = magazine leaves, c = clear of the well, fa = carried off,
ne = incoming magazine near, se = seated, h0..h1 = charging handle (empty reload only), N = clip length.
Offsets [dx, dy, dz] in metres from the raised idle (x right, y up, z back), angles [pitch, yaw, roll] in degrees
(pitch + muzzle up, yaw + muzzle left, roll + top tilts left; the right hand cants outward with roll < 0).
"""
import numpy as np
from rlib import K, kick

HIP = (0.29, 1.08, 0.00)        # grip beside the right hip rig (world), the arm nearly straight down
CHEST = (0.14, 1.20, -0.14)     # grip against the stomach rig
THIGH = (0.30, 1.09, 0.02)      # grip above the right thigh, gun muzzle down
LHIP = (0.03, 1.13, -0.15)     # grip in front of the left hip (cross-body)


def frames(c):
    T = c.T; h = T.get('handle') or [T['seated'] + 14, T['seated'] + 22]
    return T['out'], T['clear'] or T['out'] + 3, T['far'] or T['out'] + 5, T['near'], T['seated'], h[0], h[1], c.N, bool(T.get('handle'))


def add(a, b): return [a[i] + b[i] for i in range(3)]


def nat(c, pos, rot, key):
    """Angles of a hidden pose: the parameter if given, else the hint turned to where the wrist bends least."""
    return c.P[key] if key in c.P else c.natural(pos, rot, span=c.P.get('nat_span', 45), twist_w=0.15)


def rise(c, f0, start_pos, start_rot, over=(0.0, 0.012, -0.006), orot=(3, 0, 1)):
    """Keys from a low pose at f0 up into the idle: overshoot, settle."""
    N = c.N; span = N - 1 - f0
    return [K(f0, start_pos, start_rot), K(f0 + span * 0.62, add(over, (0.01, 0, -0.012)), orot), K(f0 + span * 0.84, (0, -0.003, 0), (-1, 0, 0))]


def belt_rack(c, pos, rot, h0, h1, has, pull=0.07):
    """Handle raked back on the belt edge, out of view: the gun is pushed forward against it and let go."""
    if not has: return [], []
    ks = [K(h0 - 3, add(pos, (0, 0.01, 0.02)), rot), K(h0 + 3, add(pos, (0, 0.0, -pull)), add(rot, (4, 0, 0))), K(h1, add(pos, (0, 0.015, 0.0)), rot)]
    return ks, [kick(h0 + 3, (0, 0, 0.012), (-3, 0, 0), release=3.5), kick(h1 - 1, (0, 0, -0.015), (2, 0, 0), release=3.0)]


def inertia_rack(c, h0, h1, has, back=0.05, fwd=0.13, base=(0, 0.02, 0), rot=(2, 0, -3)):
    """Handle racked by a punch: the gun is drawn back, thrown forward and stopped dead, in view."""
    if not has: return [], []
    ks = [K(h0 - 5, add(base, (0, 0, back)), add(rot, (3, 0, -4))), K(h0 + 1, add(base, (0, 0.01, -fwd)), add(rot, (1, 0, 0))),
          K(h0 + 4, add(base, (0, 0.01, -fwd * 0.9)), rot), K(h1, add(base, (0, 0, -0.01)), (0, 0, -1))]
    return ks, [kick(h0 + 1, (0, 0, 0.02), (5, 0, 0), attack=0.5, release=3.0), kick(h1 - 2, (0, 0, -0.012), (-2, 0, 0), release=3.0)]


def f01_belt_drop(c):
    """Realistic. The rifle cants and hops, the magazine drops free; down to the hip rig, the well is pressed onto a
    fresh magazine on the belt, the handle is raked on the belt edge, back up."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    ks = [K(o - 6, (0, 0.012, 0), (3, 0, -6)), K(o, (0.012, P.get('hop', 0.025), -0.004), (5, -2, P.get('cant', -22))),
          K(cl + 1, (0.018, P.get('hop', 0.025) + 0.006, -0.004), (6, -3, P.get('cant', -22) - 3)),
          K(fa + 3, (0.07, -0.13, 0.05), (-16, -6, -8)), K(fa + 10, hip, rot), K(ne, add(hip, (0, 0.012, 0)), add(rot, (2, 0, 0))), K(se, add(hip, (0, -0.02, 0)), add(rot, (-3, 0, 0))),
          K(se + 5, add(hip, (0, 0.02, -0.02)), add(rot, (6, 2, 2)))]
    rk, sk = belt_rack(c, add(hip, (0, 0.03, -0.03)), add(rot, (10, 2, 2)), h0, h1, has)
    f0 = (h1 + 2) if has else se + 12
    ks += rk + rise(c, f0, add(hip, (0, 0.04, -0.04)), add(rot, (12, 3, 3)))
    return {'Right': ks, 'shakes': {'Right': [kick(o, (0, 0.01, 0), (2, 0, -2), release=3.5), kick(se, (0, -0.022, 0), (-4, 0, 0), release=4.0)] + sk}}


def f02_side_flick(c):
    """Stylish, mostly in view. A hard outward wrist roll throws the magazine out to the side; a short dip to the belt
    for the fresh one; the handle is racked by a forward punch that stops dead."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); R = P.get('roll', 85)
    dip = P.get('dip', (0.03, -0.24, 0.11)); drot = nat(c, dip, (-30, -4, 0), 'dip_rot')
    ks = [K(o - 8, (-0.012, 0.0, 0), (0, 3, -12)), K(o - 1, (0.03, 0.0, -0.01), (4, -9, R * 0.75)), K(o + 2, (0.055, -0.01, -0.01), (5, -13, R)),
          K(cl + 3, (0.04, -0.02, 0.02), (-4, -8, R * 0.6)), K(fa + 9, dip, drot), K(ne, add(dip, (0, -0.01, 0)), drot),
          K(se, add(dip, (0, -0.03, 0)), add(drot, (-3, 0, 2))), K(se + 8, (0.01, -0.04, 0.03), (-5, -2, -8))]
    rk, sk = inertia_rack(c, h0, h1, has, P.get('back', 0.05), P.get('punch', 0.085), base=(0, 0.005, 0.02))
    ks += rk + [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': [kick(o + 1, (0.012, 0.004, 0), (0, -3, 8), release=3.5), kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0)] + sk}}


def f03_thigh_slam(c):
    """Gorilla. The rifle swings muzzle-down beside the leg, the magazine strips on the way; the well is slammed down
    onto a magazine on the thigh rig, hard; the handle catches the belt as the rifle comes up."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); th = c.off(P.get('thigh', THIGH)); rot = nat(c, th, (-82, -8, 10), 'thigh_rot')
    ks = [K(o - 6, (0.01, -0.03, 0.02), (-10, -3, -5)), K(o + 1, (0.035, -0.14, 0.08), (-36, -6, -9)), K(fa + 5, add(th, (0, 0.03, 0)), rot),
          K(ne - 5, add(th, (0.01, P.get('windup', 0.09), 0)), add(rot, (4, 0, 0))), K(se - 1, add(th, (0, -0.025, 0)), rot), K(se + 5, add(th, (0, 0.035, -0.01)), add(rot, (5, 0, 0)))]
    rk, sk = belt_rack(c, add(th, (-0.02, 0.05, -0.05)), add(rot, (40, 3, 2)), h0, h1, has)
    f0 = (h1 + 2) if has else se + 12
    ks += rk + rise(c, f0, add(th, (-0.02, 0.07, -0.07)), add(rot, (46, 4, 3)))
    return {'Right': ks, 'shakes': {'Right': [kick(se - 1, (0, -0.035, 0), (-6, 0, 0), attack=0.5, release=5.0)] + sk}}


def f04_spin_rack(c):
    """Showy. Hop and drop the magazine, dip to the belt; then the rifle is spun once forward in the hand, out to the
    right, and the spin racks the handle."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); dip = P.get('dip', (0.03, -0.25, 0.11)); drot = nat(c, dip, (-30, -4, 0), 'dip_rot')
    out = P.get('spin_pos', (0.14, -0.03, -0.03)); s0 = (h0 - 9) if has else se + 8; s1 = s0 + P.get('spin_len', 15)
    ks = [K(o - 6, (0, 0.012, 0), (3, 0, -6)), K(o, (0.012, 0.025, -0.004), (5, -2, -22)), K(cl + 1, (0.018, 0.03, -0.004), (6, -3, -25)),
          K(fa + 8, dip, drot), K(ne, add(dip, (0, -0.01, 0)), drot), K(se, add(dip, (0, -0.03, 0)), add(drot, (-3, 0, 0))),
          K(s0, add(out, (0, -0.02, 0)), (0, -12, P.get('spin_cant', -12))), K((s0 + s1) / 2, add(out, (0.01, 0.01, 0)), (0, -14, P.get('spin_cant', -12))),
          K(s1, add(out, (0, -0.01, 0)), (0, -10, P.get('spin_cant', -12) * 0.8)), K(s1 + 6, (0.02, 0.0, 0.0), (2, -2, -6)), K(N - 6, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'spin': [[s0, 0], [s0 + 2, -25], [s1 - 2, -335], [s1, -360]], 'spin_axis': 'x', 'spin_pivot': P.get('pivot', (0, -0.03, -0.03)),
            'shakes': {'Right': [kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0), kick(s1, (0, -0.012, -0.01), (-5, 0, 0), release=3.5)]}}


def f05_stock_knock(c):
    """Two arms. The left rifle swings its stock across and knocks the right rifle's magazine release; the magazine
    drops as the right rifle hops. Then as the belt drop. Blocks the left gun until the stock is back."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); m = f01_belt_drop(c)
    # the right gun waits a little higher and turned in, so the release faces the left gun
    rp = np.array(P.get('right_pos', (-0.10, -0.025, -0.01)))
    m['Right'] = [k for k in m['Right'] if k[0] > cl + 1] + [K(o - 8, rp * 0.8, (3, 6, 4)), K(o, rp, (4, 8, 6)), K(cl + 1, rp + np.array((0.01, 0.012, 0.0)), (6, 4, -8))]
    # left gun: stock end (gun axes) onto the release, left face of the right gun at the well
    import author
    S = np.array(P.get('stock_point', (0.0, -0.02, c.P.get('stock_z', 0.29)))); tgt_local = np.array(P.get('release_point', (-0.045, -0.01, -0.10)))
    rr = (4, 8, 6); qr = author.qmul(c.q0, author.qeuler(*rr)); tw = c.g0 + rp + author.qrot(qr, tgt_local)
    lrot = P.get('left_rot', (-4, 110, -8)); ql = author.qmul(c.ql0, author.qeuler(*lrot))
    hit = tw - author.qrot(ql, S) - c.gl0
    pre = hit + np.array(P.get('windup', (-0.10, 0.03, 0.02)))
    m['Left'] = [K(o - 11, (-0.01, 0.01, 0.0), (0, 10, -3)), K(o - 4, pre, (lrot[0] * 0.8, lrot[1] * 0.8, lrot[2])), K(o, hit, lrot),
                 K(o + 4, hit + np.array((-0.05, 0.01, 0.01)), (lrot[0], lrot[1] * 0.85, lrot[2])), K(o + 18, (-0.01, -0.01, 0), (-1, 6, -2)), K(o + 26, (0, 0, 0), (0, 0, 0))]
    m['shakes']['Left'] = [kick(o, (-0.012, 0, 0.004), (0, -4, 0), attack=0.5, release=3.0)]
    m['shakes']['Right'] += [kick(o, (0.012, 0.004, 0), (0, -3, -5), attack=0.5, release=3.5)]
    m['notes'] = 'two-arm: left gun busy f%d..f%d' % (o - 11, o + 26)
    return m


def f06_cross_rack(c):
    """Two arms. Magazine as the belt drop; then the rifles cross in front and the left rifle's barrel hooks the right
    rifle's handle: the right shoves forward, the left pulls back, and the handle racks. Blocks the left gun then."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); m = f01_belt_drop(c)
    if not has: return m
    import author
    rrot = P.get('right_rot', (4, 26, 8)); lrot = P.get('left_rot', (8, -30, -6))
    rpos = np.array(P.get('right_pos', (-0.07, -0.03, 0.01)))          # right gun: in and a little forward, under the left barrel
    Hl = np.array(P.get('handle_point', (0.0, 0.085, -0.22)))           # top of the right gun at the handle (gun axes)
    Bl = np.array(P.get('barrel_point', (0.0, -0.035, -0.42)))          # underside of the left barrel (gun axes)
    qr = author.qmul(c.q0, author.qeuler(*rrot)); ql = author.qmul(c.ql0, author.qeuler(*lrot))
    hw = c.g0 + rpos + author.qrot(qr, Hl)                              # handle in the world
    lpos = hw - author.qrot(ql, Bl) - c.gl0 + np.array((0, P.get('gap', -0.02), 0))
    fwd = author.qrot(qr, np.array((0, 0, -1.0))) * P.get('shove', 0.05); pull = author.qrot(qr, np.array((0, 0, 1.0))) * P.get('pull', 0.03)
    m['Right'] = [k for k in m['Right'] if k[0] <= se] + [K(se + 8, rpos + np.array((0.06, -0.13, 0.05)), (rrot[0] - 14, rrot[1] * 0.4, rrot[2] * 0.4)),
                                                             K(h0 - 1, rpos, rrot), K(h0 + 4, rpos + fwd, rrot), K(h1 + 1, rpos + fwd * 0.4 + np.array((0.02, -0.02, 0)), (rrot[0], rrot[1] * 0.7, rrot[2] * 0.6)),
                                                             K(N - 8, (0.004, 0.0, 0), (1, 2, 1))]
    m['Left'] = [K(h0 - 16, (0, 0, 0), (0, 0, 0)), K(h0 - 7, lpos + np.array((-0.02, 0.06, 0.0)), (lrot[0] + 4, lrot[1] * 0.8, lrot[2])), K(h0 - 1, lpos, lrot),
                 K(h0 + 4, lpos + pull, lrot), K(h1 + 2, lpos * 0.6 + np.array((-0.01, 0.03, 0)), (lrot[0], lrot[1] * 0.6, lrot[2] * 0.6)), K(N - 9, (0, 0.003, 0), (1, -2, 0))]
    m['shakes']['Right'] = [s for s in m['shakes']['Right'] if s['f'] <= se] + [kick(h0 + 3, (0, -0.006, 0.01), (-3, 0, 0), attack=0.5, release=3.0)]
    m['shakes']['Left'] = [kick(h0 + 3, (0, 0.006, -0.008), (3, 0, 0), attack=0.5, release=3.0)]
    m['notes'] = 'two-arm: left gun busy f%d..f%d' % (h0 - 16, N - 1)
    return m


def f07_tipup_pendulum(c):
    """Closest to today's clip. The muzzle tips up, the magazine slides out and falls; the rifle swings down beside
    the leg like a pendulum until it points at the ground behind, takes the magazine there, swings forward again and
    is snapped to a stop to rack."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); tip = P.get('tip', 30)
    back = c.off(P.get('rear', (0.31, 1.10, 0.06))); brot = nat(c, back, (-105, -10, 10), 'rear_rot')
    ks = [K(o - 7, (0, 0.006, 0.01), (tip * 0.4, 0, -4)), K(o, (0.012, 0.016, 0.03), (tip, -2, -8)), K(cl + 1, (0.018, 0.02, 0.035), (tip + 3, -4, -10)),
          K(fa + 4, (0.07, -0.12, 0.07), (-28, -6, -4)), K(fa + 11, back, brot), K(ne, add(back, (0, 0.01, 0.01)), add(brot, (-4, 0, 0))), K(se, add(back, (0, -0.02, 0)), add(brot, (2, 0, 0))),
          K(se + 9, (0.06, -0.14, 0.07), (-30, -6, -4))]
    rk, sk = inertia_rack(c, h0, h1, has, 0.04, P.get('punch', 0.09), base=(0.01, 0.005, 0.01), rot=(2, -3, -6))
    ks += rk + [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': [kick(se, (0, -0.02, 0), (3, 0, 0), release=4.0)] + sk}}


def f08_cross_body(c):
    """Cross draw. The magazine drops, the rifle sweeps low across the body under the left rifle, muzzle to the left,
    to a magazine on the left hip, seats with a bump and sweeps back; the handle is raked on the buckle on the way."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); lh = c.off(P.get('lhip', LHIP)); rot = nat(c, lh, (-35, 70, 20), 'lhip_rot')
    ks = [K(o - 6, (0, 0.008, 0), (3, 0, -6)), K(o, (0.008, 0.022, 0.008), (6, -2, -18)), K(cl + 1, (0.0, 0.015, 0.012), (4, 4, -14)),
          K(fa + 5, (-0.05, -0.18, 0.0), (-20, 32, 0)), K(fa + 12, lh, rot), K(ne, add(lh, (0, 0.01, 0)), rot), K(se, add(lh, (-0.012, -0.02, 0)), add(rot, (-3, 2, 0))),
          K(se + 7, (-0.05, -0.24, 0.08), (-24, 40, 6))]
    mid = c.off(P.get('buckle', (0.12, 1.12, -0.16))); mrot = nat(c, mid, (-30, 30, 0), 'buckle_rot')
    rk, sk = belt_rack(c, mid, mrot, h0, h1, has, pull=0.06)
    f0 = (h1 + 2) if has else se + 14
    ks += rk + rise(c, f0, add(mid, (0.02, 0.03, -0.02)), add(mrot, (6, -6, -2)))
    return {'Right': ks, 'shakes': {'Right': [kick(se, (-0.014, -0.015, 0), (-3, 3, 0), release=4.0)] + sk}}


def f09_chest_tuck(c):
    """Compact. The rifle cants, the magazine drops; it is pulled straight back against the stomach rig for the fresh
    magazine (it only just leaves the view), pushed back out, and the handle is racked by a short punch."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); ch = c.off(P.get('chest', CHEST)); rot = nat(c, ch, (-30, 8, 0), 'chest_rot')
    ks = [K(o - 6, (0, 0.006, 0.0), (2, 0, -10)), K(o, (0.014, 0.018, 0.0), (4, 0, -30)), K(cl + 1, (0.018, 0.02, 0.005), (4, 0, -34)),
          K(fa + 8, ch, rot), K(ne, add(ch, (0, 0.006, 0.005)), rot), K(se, add(ch, (-0.012, -0.012, 0.012)), add(rot, (-2, 0, 4))), K(se + 8, (0.0, -0.05, 0.05), (-4, 0, -12))]
    rk, sk = inertia_rack(c, h0, h1, has, 0.04, P.get('punch', 0.075), base=(0, 0.005, 0.02))
    ks += rk + [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': [kick(se, (-0.012, -0.008, 0.012), (-2, 0, 3), release=4.0)] + sk}}


def f10_chop_pump(c):
    """Brute force. A downward chop stops dead and the magazine carries on out of the well; the rifle stays low, the
    fresh magazine goes in on an upward punch, and the handle is worked by pumping the rifle down and up once."""
    P = c.P; o, cl, fa, ne, se, h0, h1, N, has = frames(c); low = P.get('low', (0.02, -0.27, 0.09)); lrot = nat(c, low, (-30, -4, 0), 'low_rot')
    ks = [K(o - 9, (0, 0.05, 0.02), (10, 0, -4)), K(o - 1, (0.01, -0.12, 0.02), (-20, -2, -6)), K(o + 2, (0.01, -0.10, 0.02), (-14, -2, -6)),
          K(fa + 6, low, lrot), K(ne - 2, add(low, (0, -0.05, 0.01)), add(lrot, (-4, 0, 0))), K(se, add(low, (0, 0.03, 0)), add(lrot, (4, 0, 0))),
          K(se + 8, (0.0, -0.02, 0.01), (-3, 0, -4))]
    sk = [kick(o - 1, (0, 0.02, 0), (5, 0, 0), attack=0.5, release=3.0), kick(se, (0, 0.03, 0), (5, 0, 0), attack=0.5, release=4.5)]
    if has:
        pd = P.get('pump', 0.13)
        ks += [K(h0 - 4, (0, 0.05, 0.01), (6, 0, -3)), K(h0 + 1, (0, -pd, 0.0), (-10, 0, -3)), K(h0 + 4, (0, -pd * 0.85, 0.0), (-8, 0, -3)), K(h1, (0, 0.03, 0), (4, 0, -1))]
        sk += [kick(h0 + 1, (0, 0.02, 0), (5, 0, 0), attack=0.5, release=3.0), kick(h1 - 1, (0, -0.012, 0), (-2, 0, 0), release=3.0)]
    ks += [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': sk}}


DRAFTS = {
    'F01': ('Belt drop', f01_belt_drop), 'F02': ('Side flick, punch rack', f02_side_flick), 'F03': ('Thigh slam', f03_thigh_slam),
    'F04': ('Spin rack', f04_spin_rack), 'F05': ('Stock knock (two arms)', f05_stock_knock), 'F06': ('Cross rack (two arms)', f06_cross_rack),
    'F07': ('Tip-up, pendulum', f07_tipup_pendulum), 'F08': ('Cross-body belt', f08_cross_body), 'F09': ('Chest tuck', f09_chest_tuck),
    'F10': ('Chop and pump', f10_chop_pump)}
