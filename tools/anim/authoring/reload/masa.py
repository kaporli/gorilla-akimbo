"""Category MASAMUNE: front box magazine that comes out slowly (12 frames from first move to clear of the well), long
clip, bolt release instead of a charging handle (empty reload: the bolt runs forward at b). Ten one-handed right-hand
drafts on the Masamune in its raised pose (hip carry). Conventions as front.py.

The slow exit is the problem to solve: nobody pulls the magazine. Each draft gives it a reason (dragged off on a belt
hook, shaken loose, raked off by the other rifle, sliding out of a tipped rifle) or hides it.
"""
import numpy as np
from rlib import K, kick
from front import add, nat, rise, inertia_rack, CHEST

HIP = (0.31, 1.08, 0.00)        # as front.py, 2 cm further out: the Masamune is wider
THIGH = (0.32, 1.10, 0.02)
LHIP = (0.05, 1.14, -0.13)


def frames(c):
    T = c.T; h = T.get('handle')
    return T['out'], T['clear'] or T['out'] + 12, T['far'] or T['out'] + 15, T['near'], T['seated'], (h[0] if h else None), c.N


def nudge(c, b, at=(0, 0, 0)):
    """Bolt released with the thumb, rifle in view: it jumps forward a little as the bolt slams home."""
    if b is None: return [], []
    return [K(b - 4, add(at, (0, 0.004, 0.006)), (1, 0, -2)), K(b + 6, add(at, (0, 0.0, -0.004)), (0, 0, 0))], [kick(b, (0, 0.004, -0.02), (-3, 0, 0), attack=0.5, release=3.0), kick(b + 2, (0, 0, 0.008), (2, 0, 0), release=2.5)]


def strip_on_belt(c, hip, rot, o, cl, lift=0.075):
    """Down to the belt before the magazine moves, magazine caught on the belt hook, rifle lifted slowly off it."""
    return [K(max(o - 9, 3), (0.04, -0.09, 0.04), (-14, -4, -4)), K(o - 1, add(hip, (0, -0.035, 0)), rot), K(cl, add(hip, (0.0, lift - 0.035, -0.01)), add(rot, (4, 0, 0))),
            K(cl + 5, add(hip, (0, 0.01, 0)), rot)]


def m01_belt_strip(c):
    """Realistic. Straight down to the hip; the magazine catches on the belt hook and the rifle is lifted off it; the
    well goes onto a fresh magazine on the belt; up, and the thumb drops the bolt in view."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    ks = strip_on_belt(c, hip, rot, o, cl) + [K(ne - 4, add(hip, (0, 0.025, 0)), add(rot, (2, 0, 0))), K(se, add(hip, (0, -0.02, 0)), add(rot, (-3, 0, 0))), K(se + 4, add(hip, (0, 0.02, -0.02)), add(rot, (5, 2, 2)))]
    ks += [K((b - 6) if b else se + 20, (0.004, 0.012, -0.004), (3, 0, 1))]
    nk, ns = nudge(c, b); ks += nk
    return {'Right': ks, 'shakes': {'Right': [kick(o, (0, -0.01, 0), (-2, 0, 0), release=3.0), kick(se, (0, -0.022, 0), (-4, 0, 0), release=4.0)] + ns}}


def m02_shake_loose(c):
    """Stylish, in view. The rifle is rolled onto its side and shaken twice; the magazine works loose and flies out to
    the side; a short dip to the belt for the fresh one; the bolt goes home on a forward punch."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); R = P.get('roll', 78); dip = P.get('dip', (0.03, -0.20, 0.10)); drot = nat(c, dip, (-30, -4, 0), 'dip_rot')
    s1, s2 = o + 2, o + 8
    ks = [K(o - 9, (-0.01, 0.0, 0), (0, 3, -10)), K(o - 2, (0.03, 0.02, -0.01), (3, -8, R * 0.85)), K(s1, (0.05, 0.03, -0.01), (4, -10, R)), K(s1 + 3, (0.03, 0.035, -0.01), (4, -9, R - 14)),
          K(s2, (0.06, 0.03, -0.01), (4, -11, R + 6)), K(cl + 2, (0.045, 0.02, 0.0), (2, -9, R - 10)), K(fa + 10, dip, drot), K(ne, add(dip, (0, -0.01, 0)), drot),
          K(se, add(dip, (0, -0.03, 0)), add(drot, (-3, 0, 2))), K(se + 9, (0.01, -0.03, 0.03), (-4, -2, -6))]
    rk, sk = inertia_rack(c, b or se + 16, (b or se + 16) + 9, b is not None, P.get('back', 0.05), P.get('punch', 0.085), base=(0, 0.005, 0.02))
    ks += rk + [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': [kick(s1, (0.02, 0, 0), (0, -2, 7), attack=0.5, release=2.0), kick(s2, (0.024, 0, 0), (0, -2, 8), attack=0.5, release=2.5),
                                              kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0)] + sk}}


def m03_thigh_slam(c):
    """Gorilla. Muzzle down beside the leg; the magazine is scraped off on the thigh rig; the well is slammed down
    onto the fresh one, hard; the butt is bumped on the hip to drop the bolt; up."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); th = c.off(P.get('thigh', THIGH)); rot = nat(c, th, (-82, -8, 10), 'thigh_rot')
    ks = [K(max(o - 10, 3), (0.03, -0.08, 0.04), (-25, -4, -4)), K(o - 1, add(th, (0, -0.02, 0)), rot), K(cl, add(th, (0.0, 0.06, -0.005)), add(rot, (3, 0, 0))),
          K(fa + 6, add(th, (0, 0.03, 0)), rot), K(ne - 5, add(th, (0.01, P.get('windup', 0.10), 0)), add(rot, (4, 0, 0))), K(se - 1, add(th, (0, -0.025, 0)), rot),
          K(se + 5, add(th, (0, 0.035, -0.01)), add(rot, (5, 0, 0)))]
    sk = [kick(se - 1, (0, -0.035, 0), (-6, 0, 0), attack=0.5, release=5.0)]
    if b:
        ks += [K(b - 5, add(th, (-0.02, 0.07, -0.03)), add(rot, (30, 2, 2))), K(b, add(th, (-0.02, 0.05, 0.005)), add(rot, (34, 2, 2)))]
        sk += [kick(b, (0, 0.004, -0.02), (-3, 0, 0), attack=0.5, release=2.0)]
    f0 = (b + 2) if b else se + 14
    ks += rise(c, f0, add(th, (-0.02, 0.07, -0.09)), add(rot, (40, 3, 3)))
    return {'Right': ks, 'shakes': {'Right': sk}}


def m04_spin_close(c):
    """Showy. Belt strip and belt magazine as M01; then the rifle is spun once forward in the hand, out to the right,
    and the bolt slams home as the spin stops."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    out = P.get('spin_pos', (0.12, 0.02, -0.03)); s1 = (b + 1) if b else se + 24; s0 = s1 - P.get('spin_len', 12); cant = P.get('spin_cant', -12)
    ks = strip_on_belt(c, hip, rot, o, cl) + [K(ne - 4, add(hip, (0, 0.025, 0)), add(rot, (2, 0, 0))), K(se, add(hip, (0, -0.02, 0)), add(rot, (-3, 0, 0))),
                                             K(s0, add(out, (0, -0.02, 0)), (0, -12, cant)), K((s0 + s1) / 2, add(out, (0.01, 0.01, 0)), (0, -14, cant)), K(s1, add(out, (0, -0.01, 0)), (0, -10, cant * 0.8)),
                                             K(s1 + 7, (0.02, 0.0, 0.0), (2, -2, -4)), K(N - 6, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'spin': [[s0, 0], [s0 + 2, -25], [s1 - 2, -335], [s1, -360]], 'spin_axis': 'x', 'spin_pivot': P.get('pivot', (0, -0.03, -0.03)),
            'shakes': {'Right': [kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0), kick(s1, (0, -0.012, -0.012), (-5, 0, 0), attack=0.5, release=3.0)]}}


def m05_stock_rake(c):
    """Two arms. The left rifle swings its stock across and pins the right rifle's magazine; the right rifle is lifted
    off it while the stock rakes it down and out; the right rifle then goes to the belt as M01 and the thumb drops the bolt. Blocks the left gun early."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    import author
    rp = np.array(P.get('right_pos', (-0.11, -0.03, 0.02))); rr = (4, 8, 6); lift = P.get('lift', 0.06)
    ks = [K(o - 8, rp * 0.8, (3, 6, 4)), K(o, rp, rr), K(cl, rp + np.array((0.0, lift, 0.0)), (6, 8, 4)), K(cl + 4, rp + np.array((0.03, lift * 0.6, -0.03)), (2, 2, -6)),
          K(fa + 14, hip, rot), K(ne - 4, add(hip, (0, 0.025, 0)), add(rot, (2, 0, 0))), K(se, add(hip, (0, -0.02, 0)), add(rot, (-3, 0, 0))), K(se + 4, add(hip, (0, 0.02, -0.02)), add(rot, (5, 2, 2)))]
    ks += [K((b - 6) if b else se + 20, (0.004, 0.012, -0.004), (3, 0, 1))]
    nk, ns = nudge(c, b); ks += nk
    S = np.array(P.get('stock_point', (0.0, -0.06, 0.25))); lrot = P.get('left_rot', (-4, 116, -8))
    qr = author.qmul(c.q0, author.qeuler(*rr)); ql = author.qmul(c.ql0, author.qeuler(*lrot))
    top = c.g0 + rp + author.qrot(qr, np.array(P.get('mag_top', (-0.03, -0.02, -0.18)))); down = author.qrot(qr, np.array((0, -1.0, 0.15)))
    hit = top - author.qrot(ql, S) - c.gl0
    L = [K(o - 12, (-0.01, 0.01, 0.0), (0, 10, -3)), K(o - 4, hit + np.array((-0.08, 0.04, 0.02)), (lrot[0], lrot[1] * 0.85, lrot[2])), K(o, hit, lrot),
         K(cl, hit + down * P.get('rake', 0.04), lrot), K(cl + 4, hit + down * (P.get('rake', 0.04) + 0.01) + np.array((-0.05, 0.02, 0.02)), (lrot[0], lrot[1] * 0.85, lrot[2])), K(cl + 18, (-0.01, -0.01, 0), (-1, 6, -2)), K(cl + 26, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'Left': L, 'shakes': {'Right': [kick(o, (0.008, 0.004, 0), (0, -2, -3), attack=0.5, release=3.0), kick(se, (0, -0.022, 0), (-4, 0, 0), release=4.0)] + ns,
                                               'Left': [kick(o, (-0.008, 0, 0.004), (0, -3, 0), attack=0.5, release=3.0)]},
            'notes': 'two-arm: left gun busy f%d..f%d' % (o - 12, cl + 26)}


def m06_gun_clap(c):
    """Two arms, late. Belt strip and belt magazine as M01; back up, then the two rifles are clapped together side to
    side and the knock drops the bolt. Blocks the left gun only for the clap."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); m = m01_belt_strip(c)
    if b is None: return m
    import author
    rr = P.get('right_rot', (2, 4, -8)); lr = P.get('left_rot', (2, -4, 8)); half = P.get('half', 0.05)
    # the rifles meet at the centre line: each grip stops half a rifle width from it
    rx = (half - c.g0[0]); lx = (-half - c.gl0[0]); y = P.get('lift', 0.02)
    m['Right'] = [k for k in m['Right'] if k[0] < b - 12] + [K(b - 8, (rx * 0.25, y + 0.01, 0.0), (rr[0], rr[1] * 0.5, rr[2] * 0.5)), K(b, (rx, y, 0.0), rr), K(b + 5, (rx * 0.5, y, 0), (rr[0], rr[1], rr[2] * 0.6)),
                                                               K(N - 8, (0.004, 0.003, 0), (1, 0, 0))]
    m['Left'] = [K(b - 16, (0, 0, 0), (0, 0, 0)), K(b - 8, (lx * 0.25, y + 0.01, 0.0), (lr[0], lr[1] * 0.5, lr[2] * 0.5)), K(b, (lx, y, 0.0), lr), K(b + 5, (lx * 0.5, y, 0), (lr[0], lr[1], lr[2] * 0.6)),
                 K(N - 8, (-0.004, 0.003, 0), (1, 0, 0))]
    m['shakes']['Right'] = [s for s in m['shakes']['Right'] if s['f'] <= se] + [kick(b, (0.014, 0, 0), (0, -2, -4), attack=0.5, release=2.0)]
    m['shakes']['Left'] = [kick(b, (-0.014, 0, 0), (0, 2, 4), attack=0.5, release=2.0)]
    m['notes'] = 'two-arm: left gun busy f%d..f%d' % (b - 16, N - 1)
    return m


def m07_tip_slide(c):
    """Closest to today's clip. The muzzle tips up and the magazine slides out of the tipped rifle and falls; the
    rifle swings down beside the leg like a pendulum for the fresh magazine, swings up, and a forward snap drops
    the bolt."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); tip = P.get('tip', 34)
    back = c.off(P.get('rear', (0.33, 1.10, 0.06))); brot = nat(c, back, (-105, -10, 10), 'rear_rot')
    ks = [K(o - 9, (0, 0.006, 0.01), (tip * 0.3, 0, -4)), K(o, (0.012, 0.02, 0.03), (tip, -2, -8)), K((o + cl) / 2, (0.014, 0.03, 0.035), (tip + 6, -3, -9)),
          K(cl + 1, (0.018, 0.03, 0.035), (tip + 4, -4, -10)), K(fa + 4, (0.07, -0.10, 0.07), (-20, -6, -4)), K(fa + 12, back, brot), K(ne, add(back, (0, 0.01, 0.01)), add(brot, (-4, 0, 0))),
          K(se, add(back, (0, -0.02, 0)), add(brot, (2, 0, 0))), K(se + 9, (0.06, -0.12, 0.07), (-30, -6, -4))]
    rk, sk = inertia_rack(c, b or se + 16, (b or se + 16) + 9, b is not None, 0.04, P.get('punch', 0.08), base=(0.01, 0.005, 0.01), rot=(2, -3, -6))
    ks += rk + [K(N - 8, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': [kick(se, (0, -0.02, 0), (3, 0, 0), release=4.0)] + sk}}


def m08_cross_body(c):
    """Cross draw. The rifle sweeps low across the body, muzzle to the left; the magazine is hooked off on the left
    hip rig and the fresh one seated there; it sweeps back up and the thumb drops the bolt."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); lh = c.off(P.get('lhip', LHIP)); rot = nat(c, lh, (-35, 70, 20), 'lhip_rot')
    ks = [K(max(o - 10, 3), (-0.03, -0.08, 0.0), (-12, 20, -2)), K(o - 1, add(lh, (0, -0.03, 0)), rot), K(cl, add(lh, (0.0, 0.04, 0.0)), add(rot, (3, 0, 0))), K(cl + 6, add(lh, (0, 0.01, 0)), rot),
          K(ne - 4, add(lh, (0, 0.025, 0)), rot), K(se, add(lh, (-0.012, -0.02, 0)), add(rot, (-3, 2, 0))), K(se + 6, (-0.03, -0.22, 0.10), (-24, 36, 6))]
    ks += [K((b - 6) if b else se + 20, (0.0, 0.012, -0.004), (3, 2, 1))]
    nk, ns = nudge(c, b); ks += nk
    return {'Right': ks, 'shakes': {'Right': [kick(se, (-0.014, -0.015, 0), (-3, 3, 0), release=4.0)] + ns}}


def m09_chest_tuck(c):
    """Compact. The rifle is pulled back against the stomach rig, canted; the magazine is dragged off on the rig and
    the fresh one pressed in there (it only just leaves the view); pushed back out, thumb drops the bolt."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); ch = c.off(P.get('chest', CHEST)); rot = nat(c, ch, (-30, 8, 0), 'chest_rot')
    ks = [K(max(o - 10, 3), (0.0, -0.04, 0.06), (-8, 2, -12)), K(o - 1, add(ch, (0, -0.02, 0)), rot), K(cl, add(ch, (0.0, 0.05, -0.01)), add(rot, (3, 0, 0))), K(cl + 6, add(ch, (0, 0.01, 0)), rot),
          K(ne - 4, add(ch, (0, 0.02, 0.0)), rot), K(se, add(ch, (-0.012, -0.012, 0.012)), add(rot, (-2, 0, 4))), K(se + 5, add(ch, (0, 0.02, -0.03)), add(rot, (4, 0, 0)))]
    ks += [K((b - 6) if b else se + 20, (0.0, 0.012, -0.004), (3, 0, 1))]
    nk, ns = nudge(c, b); ks += nk
    return {'Right': ks, 'shakes': {'Right': [kick(se, (-0.012, -0.008, 0.012), (-2, 0, 3), release=4.0)] + ns}}


def m10_hip_knocks(c):
    """Brute force. The rifle drops to the hip and its butt is knocked on the hip rig twice; the magazine jumps loose
    and falls; the fresh one goes in on an upward punch; one more knock on the way up drops the bolt."""
    P = c.P; o, cl, fa, ne, se, b, N = frames(c); low = P.get('low', (0.03, -0.22, 0.10)); lrot = nat(c, low, (-30, -4, 0), 'low_rot'); k1, k2 = o + 1, o + 8
    ks = [K(max(o - 9, 3), (0.01, -0.06, 0.03), (-10, -2, -4)), K(k1 - 3, add(low, (0, 0.04, -0.02)), lrot), K(k1, add(low, (0, 0.0, 0.02)), lrot), K(k1 + 4, add(low, (0, 0.035, -0.015)), lrot),
          K(k2, add(low, (0, 0.0, 0.02)), lrot), K(cl + 3, add(low, (0, 0.02, 0.0)), lrot), K(ne - 3, add(low, (0, -0.05, 0.01)), add(lrot, (-4, 0, 0))), K(se, add(low, (0, 0.03, 0)), add(lrot, (4, 0, 0)))]
    sk = [kick(k1, (0, 0.004, -0.018), (3, 0, 0), attack=0.5, release=2.0), kick(k2, (0, 0.004, -0.02), (3, 0, 0), attack=0.5, release=2.5), kick(se, (0, 0.03, 0), (5, 0, 0), attack=0.5, release=4.5)]
    if b:
        ks += [K(b - 6, (0.01, -0.10, 0.03), (-12, -2, -4)), K(b, (0.01, -0.12, 0.07), (-14, -2, -4)), K(b + 5, (0.005, -0.05, 0.02), (-6, 0, -2))]
        sk += [kick(b, (0, 0.006, -0.02), (3, 0, 0), attack=0.5, release=2.0)]
    else:
        ks += [K(se + 10, (0.005, -0.05, 0.02), (-6, 0, -2))]
    ks += [K(N - 7, (0, 0.004, 0), (1, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': sk}}


DRAFTS = {
    'M01': ('Belt strip', m01_belt_strip), 'M02': ('Shake loose, punch', m02_shake_loose), 'M03': ('Thigh slam, hip bump', m03_thigh_slam),
    'M04': ('Spin close', m04_spin_close), 'M05': ('Stock rake (two arms)', m05_stock_rake), 'M06': ('Gun clap (two arms)', m06_gun_clap),
    'M07': ('Tip-up slide, pendulum', m07_tip_slide), 'M08': ('Cross-body belt', m08_cross_body), 'M09': ('Chest tuck', m09_chest_tuck),
    'M10': ('Hip knocks', m10_hip_knocks)}
