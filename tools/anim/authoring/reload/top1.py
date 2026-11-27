"""SMG TOP family, round 1: ten one-handed reload drafts (ST01 to ST10) on the Warden, take B heavy (7.0 l), right
hand, male V, empty reload. Its own one-handed reload, not the Shingen two-arm knock. The magazine lies on top
behind the sight and leaves forward-up (42 deg above the barrel line; the game flicks it off at 6 cm/f). Every
draft: opener on the latch frame (the gun's magazine_open starts f15), wind-up, one thrust or chop along that axis
with a dead stop on the release beat (the magazine flies on at the gun's speed), to a rig, seated, up, rack on the
cocking device, idle (r1lib.BEATS take B, 77 frames).
A forward-up throw from chest height stays on screen for about 15 to 20 frames, longer than the hidden window
allows, and dipping the muzzle far brings the 23 cm stock into the eye, so the gun is rolled or turned over before
the thrust: the same forward-up axis of the gun then points forward-out, sideways or down in the world and the
magazine leaves the view within 2 to 12 frames.
The fresh magazine comes onto the top from the gun's above: it waits on a rig and the gun is driven onto it with
its top first: up from below under a magazine hanging from the stomach rig, or turned over and pressed onto a
magazine in a belt pouch, on the hip or on the outer thigh. (A chest rig was tried: the gun stayed on screen at the
seat and came within 5 cm of the other gun.)

usage: top1.py list | events | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r1lib_round1 as r1lib; sys.modules["r1lib"] = r1lib      # the round 1 engine (older speed rules), beside the shared r1lib
from r1lib import opener, chop, seat, rack

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'ST'
_ex = np.array((0.0, 0.67, -0.74)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': np.array((0.0, -1.0, 0.0))}       # the fresh magazine comes down onto the top (the gun goes up its own y)
# rigs: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), search start angles
STATIONS = {'stomach_t': ((0.18, 0.22, -0.24), (-10, 20, 0)),      # upright, under a magazine hanging lips-down from the belt front
            'belt_t': ((0.27, 0.20, -0.08), (-40, 0, 180)),        # turned over, pressed down onto a magazine standing in a belt pouch
            'hip_t': ((0.31, 0.20, -0.10), (-60, -10, 160)),       # muzzle down, top back, pressed back onto a magazine on the hip
            'thigh_t': ((0.34, 0.18, -0.02), (-60, 0, 90))}        # muzzle down, top toward the leg, pressed onto a magazine on the outer thigh
LIFT = (0.0, 0.0, 0.0)


def mag(c, **k):
    B = c.B; d = {'release': B['rel'], 'mode': 'inertia', 'push': 0.004, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def st01(c, tl):
    """Muzzle-dip thrust. The thumb presses the latch: a dip stops dead on its frame. The muzzle is dipped and the
    gun rolled a little outward (the magazine's axis now points forward and out) and drawn back, still, then thrust
    forward and stopped dead: the magazine flies off the top ahead and to the right and drops in front. Down in
    front of the stomach and driven up under the fresh magazine hanging from the belt rig. Up, cocked back, punched
    forward on the cocking device."""
    opener(c, tl, 'press'); chop(c, tl, (0.03, -0.08, -0.02), (-30, 0, 40), (-24, 0, 36), 0.20)
    seat(c, tl, 'stomach_t'); rack(c, tl, 'punch'); return mag(c)


def st02(c, tl):
    """Flip chop. A tug back stops dead on the latch frame. The gun is turned over (top down), pushed out and raised,
    still, then chopped down and forward along the magazine's axis and stopped dead: the magazine drops off the
    underside and falls in front. Still turned over, down to the belt and pressed onto the fresh magazine in the
    pouch. Rolled upright as it rises, held muzzle-high, the muzzle thrown down on the cocking device."""
    opener(c, tl, 'tug'); chop(c, tl, (0.02, -0.07, -0.07), (0, 0, 170), (6, 0, 176), 0.18)
    seat(c, tl, 'belt_t'); rack(c, tl, 'nod'); return mag(c)


def st03(c, tl):
    """Backhand roll throw. A small snap stops dead on the latch frame. The gun is rolled onto its right side (top
    out to the right), muzzle a little down, and drawn in, still, then backhanded out to the right along the axis
    and stopped dead: the magazine flies out sideways and drops. Down beside the thigh, pressed onto the fresh
    magazine on the outer thigh. Up, held out in front and yanked back on the cocking device."""
    opener(c, tl, 'snap'); chop(c, tl, (0.05, -0.04, 0.0), (-20, 0, 80), (-14, 0, 74), 0.20)
    seat(c, tl, 'thigh_t'); rack(c, tl, 'yank'); return mag(c, tumble=4)


def st04(c, tl):
    """Dipped side thrust. The thumb presses the latch: a dip stops dead on its frame. Rolled 60 deg out and dipped,
    the gun is drawn in low, still, then thrust out and forward and stopped dead: the magazine skims off to the
    front right and drops. Down beside the thigh onto the outer-thigh magazine. Up, cocked low, a rising punch on
    the cocking device."""
    opener(c, tl, 'press'); chop(c, tl, (0.03, -0.08, -0.06), (-20, 0, 60), (-14, 0, 54), 0.18)
    seat(c, tl, 'thigh_t'); rack(c, tl, 'upper'); return mag(c)


def st05(c, tl):
    """Over-roll chop. A tug back stops dead on the latch frame. The gun is rolled far past its side (top down and
    out), muzzle a little down, pushed out and raised, still, then chopped down along the axis and stopped dead: the
    magazine drops off down and to the right. Turned over, pressed onto the magazine in the belt pouch. Rolled
    upright as it rises, held out in front and yanked back on the cocking device."""
    opener(c, tl, 'tug'); chop(c, tl, (0.02, -0.05, -0.06), (-10, 0, 150), (-4, 0, 156), 0.18)
    seat(c, tl, 'belt_t'); rack(c, tl, 'yank'); return mag(c)


def st06(c, tl):
    """Roll-drop. A small snap stops dead on the latch frame. The gun is lifted, rolled a quarter out, still, then
    dropped hard while it rolls over and stopped dead turned over: the magazine leaves the underside spinning and
    falls. Still turned over, onto the magazine in the belt pouch. Rolled upright as it rises, cocked back, punched
    forward on the cocking device."""
    opener(c, tl, 'snap'); chop(c, tl, (0.02, -0.06, -0.04), (0, 0, 160), (8, 0, 100), 0.20)
    seat(c, tl, 'belt_t'); rack(c, tl, 'punch'); return mag(c, tumble=2)


def st07(c, tl):
    """Double pump. The opener is a short forward pump along the axis (muzzle dipped, rolled out) that stops dead on
    the latch frame: the magazine is knocked loose (1.5 cm). Drawn back again, still, then the full thrust stops
    dead: it flies off ahead. Driven up under the magazine hanging from the belt rig. Up, cocked low, a rising punch
    on the cocking device."""
    B = c.B; k = c.P['k']; f = B['cue']; rr = (-24, 0, 30); e = c.along(rr, c.v['exit'], 0.05)
    tl.hold(1); tl.to(f - 3, -e * 0.6, rr, 'ease'); tl.to(f, e * 0.4, rr, 'slam', rlag=0); tl.kick(f, -e * 0.15 * k, (2 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('cue', f); tl.nodrag.append((f - 3, f + 1))
    chop(c, tl, (0.03, -0.08, -0.02), (-30, 0, 40), (-26, 0, 36), 0.18)
    seat(c, tl, 'stomach_t'); rack(c, tl, 'upper'); return mag(c, loosen=[[f, 0.015]])


def st08(c, tl):
    """Down-out chop. A tug back stops dead on the latch frame. The gun is rolled outward past its side (top facing
    down and out) and raised, still, then chopped down and out along the axis and stopped dead: the magazine drops
    out to the right of the gun. Muzzle down, pressed back onto the magazine on the hip. Up, held muzzle-high, the
    muzzle thrown down on the cocking device."""
    opener(c, tl, 'tug'); chop(c, tl, (0.05, -0.05, 0.0), (-6, 0, 130), (2, 0, 124), 0.19)
    seat(c, tl, 'hip_t'); rack(c, tl, 'nod'); return mag(c, tumble=4)


def st09(c, tl):
    """Low thrust. The thumb presses the latch: a dip stops dead on its frame. The gun is pulled back low beside the
    ribs, muzzle dipped hard and rolled out, still, then thrust forward and stopped dead at the belly: the magazine
    skims off low in front and drops. Straight up under the magazine hanging from the belt rig. Up, held muzzle-high,
    the muzzle thrown down on the cocking device."""
    opener(c, tl, 'press'); chop(c, tl, (0.03, -0.12, -0.02), (-34, 0, 30), (-28, 0, 26), 0.18)
    seat(c, tl, 'stomach_t'); rack(c, tl, 'nod'); return mag(c)


def st10(c, tl):
    """Flip drive. A muzzle-up snap stops dead on the latch frame. The gun is turned over and pushed out forward,
    muzzle up, still, then driven down and back along the axis and stopped dead: the magazine flies off the
    underside down in front. Turned over, pressed onto the magazine in the belt pouch. Rolled upright as it rises,
    held out in front and yanked back on the cocking device."""
    opener(c, tl, 'tip'); chop(c, tl, (0.04, -0.06, -0.02), (24, 0, 170), (30, 0, 176), 0.18)
    seat(c, tl, 'belt_t'); rack(c, tl, 'yank'); return mag(c)


PICKS = {'ST01': ('Muzzle-dip thrust', st01), 'ST02': ('Flip chop', st02), 'ST03': ('Backhand roll throw', st03), 'ST04': ('Dipped side thrust', st04), 'ST05': ('Over-roll chop', st05),
         'ST06': ('Roll-drop', st06), 'ST07': ('Double pump', st07), 'ST08': ('Down-out chop', st08), 'ST09': ('Low thrust', st09), 'ST10': ('Flip drive', st10)}
PARAMS = {p: {'lift': LIFT} for p in PICKS}

if __name__ == '__main__': r1lib.main(sys.modules[__name__], sys.argv[1:])
