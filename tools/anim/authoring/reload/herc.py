"""Category HERCULES: side cassette (left side of the receiver, in front of the grip). Its own reload is long (186
frames) and the same for a partly full and an empty gun: a latch on the left opens at L (f19), the cassette is taken
out slowly (o..cl), carried off, a fresh one comes back (ne) and is seated (se), the latch closes at C (f140).
No charging handle. Ten one-handed right-hand drafts on the Hercules in its raised pose. Conventions as front.py.

Each draft gives the latch a reason to open (wrist flick, thumb, the other rifle's muzzle), takes the cassette off
against the body out of view or shakes it out, and gives the latch a reason to close (hip bump, punch, spin, clap).
"""
import numpy as np
from rlib import K, kick
from front import add, nat, inertia_rack, CHEST

HIP = (0.35, 1.09, 0.00)
THIGH = (0.37, 1.11, 0.02)
LHIP = (0.05, 1.14, -0.13)
BACK = (0.33, 1.10, 0.19)       # grip behind the right hip (back rig)


def frames(c):
    T = c.T; g = T['parts'].get('magazine_grabber', {}).get('window', [19, 140])
    return g[0], T['out'], T['clear'] or T['out'] + 14, T['far'] or T['out'] + 19, T['near'], T['seated'], g[1], c.N


def latch_flick(L, roll=-26):
    """The latch is popped with a short outward wrist flick, in view."""
    return [K(L - 6, (0, 0.004, 0), (0, 0, 6)), K(L, (0.01, 0.01, 0), (2, -2, roll)), K(L + 7, (0.004, 0.004, 0), (1, 0, roll * 0.3))], [kick(L, (0.006, 0.004, 0), (0, -2, -5), attack=0.5, release=2.5)]


def station(c, pos, rot, o, cl, ne, se, lift=0.06, via=(0.04, -0.09, 0.04), via_rot=(-14, -4, -4)):
    """To a place on the body before the cassette moves; it is hooked there and the rifle lifted off it; the rifle
    waits, then is pressed onto the fresh cassette."""
    return [K(o - 14, via, via_rot), K(o - 2, add(pos, (0, -0.03, 0)), rot), K(cl, add(pos, (0.0, lift - 0.03, -0.01)), add(rot, (4, 0, 0))), K(cl + 6, add(pos, (0, 0.005, 0)), rot),
            K((cl + ne) // 2, add(pos, (0.005, 0.015, 0)), add(rot, (2, 0, 0))), K(se - 7, add(pos, (0, 0.035, 0)), add(rot, (2, 0, 0))), K(se, add(pos, (0, -0.02, 0)), add(rot, (-3, 0, 0))),
            K(se + 6, add(pos, (0, 0.012, -0.01)), add(rot, (3, 0, 0)))]


def up(C, low, lrot, N, over=(0.006, 0.012, -0.014)):
    """From a low pose after the latch has closed back into the idle."""
    return [K(C + 3, low, lrot), K(C + 19, over, (3, 0, 1)), K(C + 27, (0, -0.003, 0), (-1, 0, 0)), K(C + 34, (0, 0, 0), (0, 0, 0))]


def bump_close(c, pos, rot, C, d=(-0.01, 0.03, 0.02)):
    """The latch is knocked shut against the body, out of view."""
    return [K(C - 6, add(pos, (0.01, 0.04, -0.03)), add(rot, (6, 0, 0))), K(C, add(pos, d), add(rot, (8, 0, 0)))], [kick(C, (-0.006, 0.0, 0.012), (2, 0, 0), attack=0.5, release=2.5)]


def h01_belt_swap(c):
    """Realistic. A wrist flick pops the latch; down to the hip, the cassette is hooked off on the belt and the rifle
    pressed onto a fresh one there; the latch is knocked shut on the hip; up."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    lk, ls = latch_flick(L); bk, bs = bump_close(c, hip, rot, C)
    ks = lk + station(c, hip, rot, o, cl, ne, se) + bk + up(C, add(hip, (0, 0.04, -0.04)), add(rot, (12, 3, 3)), N)
    return {'Right': ks, 'shakes': {'Right': ls + [kick(o, (0, -0.01, 0), (-2, 0, 0), release=3.0), kick(se, (0, -0.022, 0), (-4, 0, 0), release=4.0)] + bs}}


def h02_flip_shake(c):
    """Stylish, in view. The rifle is flicked to pop the latch, rolled onto its left side and shaken twice: the
    cassette slides out and away; a dip to the belt for the fresh one; back up, and a forward punch that stops dead
    snaps the latch shut."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); R = P.get('roll', 78); dip = P.get('dip', (0.03, -0.20, 0.10)); drot = nat(c, dip, (-30, -4, 0), 'dip_rot')
    lk, ls = latch_flick(L); s1, s2 = o + 3, o + 10
    ks = lk + [K(o - 12, (0.0, 0.004, 0), (1, 2, -8)), K(o - 3, (0.03, 0.03, -0.01), (3, -8, R * 0.85)), K(s1, (0.05, 0.04, -0.01), (4, -10, R)), K(s1 + 3, (0.03, 0.045, -0.01), (4, -9, R - 14)),
               K(s2, (0.06, 0.04, -0.01), (4, -11, R + 6)), K(cl + 3, (0.045, 0.03, 0.0), (2, -9, R - 10)), K(fa + 12, dip, drot), K((fa + ne) // 2 + 6, add(dip, (0, 0.01, 0)), drot),
               K(se - 6, add(dip, (0, 0.02, 0)), drot), K(se, add(dip, (0, -0.03, 0)), add(drot, (-3, 0, 2))), K(se + 10, (0.01, -0.03, 0.03), (-4, -2, -6)), K(C - 12, (0, 0.006, 0.01), (2, 0, -3))]
    rk, sk = inertia_rack(c, C, C + 9, True, P.get('back', 0.05), P.get('punch', 0.085), base=(0, 0.005, 0.02))
    ks += rk + [K(C + 22, (0, 0.004, 0), (1, 0, 0)), K(C + 30, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': ls + [kick(s1, (0.02, 0, 0), (0, -2, 7), attack=0.5, release=2.0), kick(s2, (0.024, 0, 0), (0, -2, 8), attack=0.5, release=2.5),
                                                   kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0)] + sk}}


def h03_thigh_slam(c):
    """Gorilla. Latch flicked open; muzzle down beside the leg, the cassette is scraped off on the thigh rig; the
    rifle is wound up and slammed down onto the fresh one; the latch is knocked shut on the hip; up."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); th = c.off(P.get('thigh', THIGH)); rot = nat(c, th, (-82, -8, 10), 'thigh_rot')
    lk, ls = latch_flick(L)
    ks = lk + [K(o - 14, (0.03, -0.08, 0.04), (-25, -4, -4)), K(o - 2, add(th, (0, -0.02, 0)), rot), K(cl, add(th, (0.0, 0.05, -0.005)), add(rot, (3, 0, 0))), K(cl + 6, add(th, (0, 0.02, 0)), rot),
               K((cl + ne) // 2, add(th, (0.005, 0.03, 0)), rot), K(se - 7, add(th, (0.01, P.get('windup', 0.11), 0)), add(rot, (4, 0, 0))), K(se - 1, add(th, (0, -0.025, 0)), rot),
               K(se + 6, add(th, (0, 0.035, -0.01)), add(rot, (5, 0, 0)))]
    bk, bs = bump_close(c, th, add(rot, (26, 2, 2)), C, d=(-0.02, 0.05, 0.005))
    ks += bk + up(C, add(th, (-0.02, 0.07, -0.09)), add(rot, (40, 3, 3)), N)
    return {'Right': ks, 'shakes': {'Right': ls + [kick(se - 1, (0, -0.035, 0), (-6, 0, 0), attack=0.5, release=5.0)] + bs}}


def h04_spin_close(c):
    """Showy. Belt swap as H01; back up, then the rifle is spun once forward in the hand, out to the right, and the
    latch snaps shut as the spin stops."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); hip = c.off(P.get('hip', HIP)); rot = nat(c, hip, (-45, -10, 0), 'hip_rot')
    lk, ls = latch_flick(L); out = P.get('spin_pos', (0.12, 0.04, -0.03)); s1 = C + 1; s0 = s1 - P.get('spin_len', 12); cant = P.get('spin_cant', -12)
    ks = lk + station(c, hip, rot, o, cl, ne, se) + [K(s0, add(out, (0, -0.02, 0)), (0, -12, cant)), K((s0 + s1) / 2, add(out, (0.01, 0.01, 0)), (0, -14, cant)), K(s1, add(out, (0, -0.01, 0)), (0, -10, cant * 0.8)),
                                                    K(s1 + 8, (0.02, 0.0, 0.0), (2, -2, -4)), K(s1 + 18, (0, 0.004, 0), (1, 0, 0)), K(s1 + 26, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'spin': [[s0, 0], [s0 + 2, -25], [s1 - 2, -335], [s1, -360]], 'spin_axis': 'x', 'spin_pivot': P.get('pivot', (0, -0.03, -0.03)),
            'shakes': {'Right': ls + [kick(se, (0, -0.02, 0), (-4, 0, 0), release=4.0), kick(s1, (0, -0.012, -0.012), (-5, 0, 0), attack=0.5, release=3.0)]}}


def h05_muzzle_poke(c):
    """Two arms, early. The right rifle turns its left side in and the left rifle's muzzle pokes the latch open; then
    the belt swap of H01 and the hip bump. Blocks the left gun only for the poke."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); m = h01_belt_swap(c)
    import author
    rp = np.array(P.get('right_pos', (-0.05, 0.03, -0.02))); rr = P.get('right_rot', (4, -14, 10)); lrot = P.get('left_rot', (4, -42, 0))
    m['Right'] = [k for k in m['Right'] if k[0] > L + 8] + [K(L - 9, rp * 0.7, (rr[0], rr[1] * 0.6, rr[2] * 0.6)), K(L, rp, rr), K(L + 6, rp + np.array((0.012, 0.0, 0.0)), (rr[0], rr[1], rr[2] * 0.7))]
    qr = author.qmul(c.q0, author.qeuler(*rr)); ql = author.qmul(c.ql0, author.qeuler(*lrot))
    latch = c.g0 + rp + author.qrot(qr, np.array(P.get('latch_point', (-0.06, 0.07, -0.18))))
    hit = latch - author.qrot(ql, np.array(P.get('muzzle_point', (0.0, 0.03, -0.44)))) - c.gl0
    back = author.qrot(ql, np.array((0, 0, 1.0))) * 0.07
    m['Left'] = [K(L - 14, (0, 0, 0), (0, 0, 0)), K(L - 5, hit + back, lrot), K(L, hit, lrot), K(L + 4, hit + back * 0.8, lrot), K(L + 18, (0, 0.004, 0), (1, -4, 0)), K(L + 26, (0, 0, 0), (0, 0, 0))]
    m['shakes']['Right'] = [s for s in m['shakes']['Right'] if s['f'] != L] + [kick(L, (0.01, 0, 0), (0, -3, -4), attack=0.5, release=2.5)]
    m['shakes']['Left'] = [kick(L, (0, 0, 0.012), (2, 0, 0), attack=0.5, release=2.5)]
    m['notes'] = 'two-arm: left gun busy f%d..f%d' % (L - 14, L + 26)
    return m


def h06_gun_clap(c):
    """Two arms, late. Belt swap as H01; back up with the latch still open, then the two rifles are clapped together
    side to side and the knock shuts it. Blocks the left gun only for the clap."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); m = h01_belt_swap(c)
    rr = P.get('right_rot', (2, 4, -8)); lr = P.get('left_rot', (2, -4, 8)); half = P.get('half', 0.065)
    rx = (half - c.g0[0]); lx = (-half - c.gl0[0]); y = P.get('lift', 0.03)
    m['Right'] = [k for k in m['Right'] if k[0] <= se + 6] + [K(C - 13, (0.004, 0.01, -0.004), (3, 0, 1)), K(C - 6, (rx * 0.2, y + 0.01, 0.0), (rr[0], rr[1] * 0.5, rr[2] * 0.5)), K(C, (rx, y, 0.0), rr),
                                                             K(C + 6, (rx * 0.5, y, 0), (rr[0], rr[1], rr[2] * 0.6)), K(C + 20, (0.004, 0.003, 0), (1, 0, 0)), K(C + 28, (0, 0, 0), (0, 0, 0))]
    m['Left'] = [K(C - 18, (0, 0, 0), (0, 0, 0)), K(C - 9, (lx * 0.2, y + 0.01, 0.0), (lr[0], lr[1] * 0.5, lr[2] * 0.5)), K(C, (lx, y, 0.0), lr), K(C + 6, (lx * 0.5, y, 0), (lr[0], lr[1], lr[2] * 0.6)),
                 K(C + 20, (-0.004, 0.003, 0), (1, 0, 0)), K(C + 28, (0, 0, 0), (0, 0, 0))]
    m['shakes']['Right'] = [s for s in m['shakes']['Right'] if s['f'] <= se] + [kick(C, (0.014, 0, 0), (0, -2, -4), attack=0.5, release=2.0)]
    m['shakes']['Left'] = [kick(C, (-0.014, 0, 0), (0, 2, 4), attack=0.5, release=2.0)]
    m['notes'] = 'two-arm: left gun busy f%d..f%d' % (C - 18, C + 28)
    return m


def h07_tip_slide(c):
    """Closest to today's clip. Latch flicked open; the muzzle tips up and the cassette slides back out of the tipped
    rifle and falls; the rifle swings down beside the leg like a pendulum for the fresh one, swings up, and a
    forward snap shuts the latch."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); tip = P.get('tip', 34)
    back = c.off(P.get('rear', (0.38, 1.11, 0.06))); brot = nat(c, back, (-105, -10, 10), 'rear_rot'); lk, ls = latch_flick(L)
    ks = lk + [K(o - 12, (0, 0.006, 0.01), (tip * 0.3, 0, -4)), K(o, (0.012, 0.03, 0.03), (tip, -2, -8)), K((o + cl) / 2, (0.014, 0.04, 0.035), (tip + 6, -3, -9)),
               K(cl + 1, (0.018, 0.04, 0.035), (tip + 4, -4, -10)), K(fa + 5, (0.07, -0.10, 0.07), (-20, -6, -4)), K(fa + 14, back, brot), K((fa + ne) // 2 + 8, add(back, (0, 0.012, 0.012)), add(brot, (-5, 0, 0))),
               K(se - 6, add(back, (0, 0.02, 0.01)), add(brot, (-4, 0, 0))), K(se, add(back, (0, -0.02, 0)), add(brot, (2, 0, 0))), K(se + 10, (0.06, -0.12, 0.07), (-30, -6, -4)), K(C - 12, (0.005, 0.004, 0.012), (2, -2, -4))]
    rk, sk = inertia_rack(c, C, C + 9, True, 0.04, P.get('punch', 0.08), base=(0.01, 0.005, 0.01), rot=(2, -3, -6))
    ks += rk + [K(C + 22, (0, 0.004, 0), (1, 0, 0)), K(C + 30, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': ls + [kick(se, (0, -0.02, 0), (3, 0, 0), release=4.0)] + sk}}


def h08_cross_body(c):
    """Cross draw. Latch flicked open; the rifle sweeps low across the body, muzzle to the left; the cassette is hooked
    off on the left hip rig and the fresh one seated there; the latch is knocked shut on the buckle; back up."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); lh = c.off(P.get('lhip', LHIP)); rot = nat(c, lh, (-35, 70, 20), 'lhip_rot'); lk, ls = latch_flick(L)
    ks = lk + station(c, lh, rot, o, cl, ne, se, lift=0.05, via=(-0.03, -0.08, 0.0), via_rot=(-12, 20, -2))
    mid = c.off(P.get('buckle', (0.12, 1.13, -0.14))); mrot = nat(c, mid, (-30, 30, 0), 'buckle_rot')
    ks += [K(C - 8, add(mid, (0.0, 0.03, -0.02)), mrot), K(C, add(mid, (-0.01, 0.0, 0.02)), mrot)] + up(C, add(mid, (0.02, 0.03, -0.03)), add(mrot, (6, -6, -2)), N)
    return {'Right': ks, 'shakes': {'Right': ls + [kick(se, (-0.014, -0.015, 0), (-3, 3, 0), release=4.0), kick(C, (-0.004, 0, 0.012), (2, 0, 0), attack=0.5, release=2.5)]}}


def h09_chest_tuck(c):
    """Compact. Latch flicked open; the rifle is pulled back against the stomach rig, canted; the cassette is dragged
    off on the rig and the fresh one pressed in there (it only just leaves the view); pushed back out, and the thumb
    shuts the latch with the rifle in view."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); ch = c.off(P.get('chest', CHEST)); rot = nat(c, ch, (-30, 8, 0), 'chest_rot'); lk, ls = latch_flick(L)
    ks = lk + station(c, ch, rot, o, cl, ne, se, lift=0.05, via=(0.0, -0.04, 0.06), via_rot=(-8, 2, -12))
    ks += [K(se + 22, (0.0, 0.012, -0.004), (3, 0, 1)), K(C - 4, (0, 0.004, 0.006), (1, 0, -2)), K(C + 6, (0, 0.0, -0.004), (0, 0, 0)), K(C + 14, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': ls + [kick(se, (-0.012, -0.008, 0.012), (-2, 0, 3), release=4.0), kick(C, (0.004, 0.004, -0.012), (-2, 0, -3), attack=0.5, release=2.5)]}}


def h10_back_rig(c):
    """Out of sight. Latch flicked open; the rifle goes down and round behind the right hip, muzzle at the ground; the
    cassette is swapped on the back rig; the latch is knocked shut there; the rifle comes back round the side."""
    P = c.P; L, o, cl, fa, ne, se, C, N = frames(c); bk = c.off(P.get('back', BACK)); rot = nat(c, bk, (-100, -20, 20), 'back_rot'); lk, ls = latch_flick(L)
    side = P.get('side', (0.25, -0.15, 0.07))
    ks = lk + station(c, bk, rot, o, cl, ne, se, lift=0.05, via=side, via_rot=(-45, -10, 0))
    b2, bs = bump_close(c, bk, rot, C, d=(-0.02, 0.02, -0.01))
    ks += b2 + [K(C + 3, add(bk, (0.01, 0.03, -0.03)), rot), K(C + 12, side, (-45, -10, 0)), K(C + 24, (0.006, 0.012, -0.014), (3, 0, 1)), K(C + 31, (0, -0.003, 0), (-1, 0, 0)), K(C + 38, (0, 0, 0), (0, 0, 0))]
    return {'Right': ks, 'shakes': {'Right': ls + [kick(se, (0, -0.02, 0), (-3, 0, 0), release=4.0)] + bs}}


DRAFTS = {
    'H01': ('Belt swap', h01_belt_swap), 'H02': ('Flip and shake, punch', h02_flip_shake), 'H03': ('Thigh slam', h03_thigh_slam),
    'H04': ('Spin close', h04_spin_close), 'H05': ('Muzzle poke (two arms)', h05_muzzle_poke), 'H06': ('Gun clap (two arms)', h06_gun_clap),
    'H07': ('Tip-up slide, pendulum', h07_tip_slide), 'H08': ('Cross-body belt', h08_cross_body), 'H09': ('Chest tuck', h09_chest_tuck),
    'H10': ('Back rig', h10_back_rig)}
