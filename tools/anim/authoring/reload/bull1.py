"""SMG BULLPUP family, round 1: ten one-handed reload drafts (SB01 to SB10) on the Pulsar, take A snappy (light,
2.2 l), right hand, male V, empty reload. The magazine sits behind the hand under the stock (centre 6.6 cm behind
and 4.6 cm under the grip), curved forward at its foot. It leaves down along the top of the magazine (the part in
the well, 14 deg forward: the game rocks it forward 3 cm, then pulls it down), the fresh one waits upright in a
pouch and the rear of the gun, behind the hand, is driven down onto it. Every draft: opener, wind-up, one chop
along the well with a dead stop on the release beat (the magazine flies on at the gun's speed), down to the
pouch, seated, up, rack on the cocking handle, idle (r1lib.BEATS take A, 68 frames).
The Pulsar's cocking handle (gun f80 to 86, centre) is time-mapped onto the hit (f53 to 56).

usage: bull1.py list | events | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r1lib_round1 as r1lib; sys.modules["r1lib"] = r1lib      # the round 1 engine (older speed rules), beside the shared r1lib
from r1lib import opener, chop, seat, rack

FAMILY = 'BULLPUP'; GUN = 'pulsar'; TAKE = 'A'; PREFIX = 'SB'
_ex = np.array((0.0, -0.97, -0.24)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': -_ex}
# pouches: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), search start angles. The
# gun about level, muzzle forward-down: the well, behind the hand, sits over the pouch.
STATIONS = {'belt_b': ((0.27, 0.22, -0.11), (-16, -6, 4)), 'thigh_b': ((0.28, 0.14, -0.09), (-24, -8, 6)), 'hip_b': ((0.30, 0.23, -0.05), (-20, -12, 10)),
            'stomach_b': ((0.16, 0.24, -0.17), (-16, 10, -6)), 'rear_b': ((0.29, 0.23, 0.02), (-22, -14, 10))}


def mag(c, **k):
    B = c.B; d = {'release': B['rel'], 'mode': 'inertia', 'push': 0.004, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def sb01(c, tl):
    """Wind-up chop. A tug back stops dead on the cue. The muzzle is lifted and the gun raised, still, then chopped
    straight down and stopped dead in front of the chest: the magazine behind the hand flies on down out of the
    well and falls past the forearm. Down to the belt pouch, the rear of the gun driven onto the fresh magazine. Up,
    cocked low, a rising punch stops dead on the handle frame."""
    opener(c, tl, 'tug'); chop(c, tl, (0.0, -0.03, 0.02), (-4, 0, 0), (18, 0, -3), 0.17)
    seat(c, tl, 'belt_b'); rack(c, tl, 'upper'); return mag(c)


def sb02(c, tl):
    """Elbow-out chop. A small snap stops dead on the cue. The elbow comes up and out, the gun canted outward so the
    magazine hangs out to the right of the forearm, still, then chopped down-out along the well and stopped dead: the
    magazine drops clear of the arm on the right. Down to the hip pouch. Up, held out in front and yanked back on the
    handle frame."""
    opener(c, tl, 'snap'); chop(c, tl, (0.03, -0.02, 0.01), (-2, 0, 30), (14, 0, 36), 0.17)
    seat(c, tl, 'hip_b'); rack(c, tl, 'yank'); return mag(c)


def sb03(c, tl):
    """Cant-in chop. The thumb presses the release: a small dip stops dead on the cue. The gun is lifted and canted
    inward (the magazine under the wrist points down-left), still, then chopped along the canted well and stopped
    dead: the magazine flies down between the guns. Down to the stomach pouch. Up, held muzzle-high, the muzzle
    thrown down on the handle frame."""
    opener(c, tl, 'press'); chop(c, tl, (0.03, -0.03, 0.02), (-2, 0, -30), (14, 0, -34), 0.16)
    seat(c, tl, 'stomach_b'); rack(c, tl, 'nod'); return mag(c)


def sb04(c, tl):
    """Muzzle-up shove. A muzzle-up snap stops dead on the cue. The muzzle is tipped up steep, the stock drawn down
    by the hip, still, then the gun is shoved down and forward along the raked well and stopped dead: the magazine
    shoots out ahead of the hand and falls in front. Down to the belt pouch. Up, cocked back, punched forward on the
    handle frame."""
    opener(c, tl, 'tip'); chop(c, tl, (0.0, -0.05, 0.01), (26, -4, -4), (30, -4, -4), 0.15)
    seat(c, tl, 'belt_b'); rack(c, tl, 'punch'); return mag(c)


def sb05(c, tl):
    """Reach-out chop. A tug back stops dead on the cue. The arm reaches out forward and up, still, then the gun is
    chopped straight down at arm's length and stopped dead: the magazine, far from the eye, is seen falling a long way
    in front. Back and down beside the thigh onto the fresh magazine. Up, held out in front and yanked back on the
    handle frame."""
    opener(c, tl, 'tug'); chop(c, tl, (0.0, -0.02, -0.01), (-2, 0, -2), (12, 0, -3), 0.19)
    seat(c, tl, 'thigh_b'); rack(c, tl, 'yank'); return mag(c)


def sb06(c, tl):
    """Backhand chop. A small snap stops dead on the cue. The gun is rolled onto its right side (the magazine points
    out to the right) and drawn in, still, then backhanded outward along the well and stopped dead: the magazine
    flies out sideways to the right and drops. Into the pouch behind the hip. Up, held muzzle-high, the muzzle thrown
    down on the handle frame."""
    opener(c, tl, 'snap'); chop(c, tl, (0.07, -0.03, 0.02), (2, -4, 72), (8, -2, 66), 0.17)
    seat(c, tl, 'rear_b'); rack(c, tl, 'nod'); return mag(c, tumble=5)


def sb07(c, tl):
    """Drop stop. The thumb presses the release: a small dip stops dead on the cue. The gun rises a hand high, level,
    still, then the arm drops it straight down and stops it dead low in front: the magazine keeps falling out of the
    well behind the hand. Onto the fresh magazine at the belt. Up, cocked back, punched forward on the handle frame."""
    opener(c, tl, 'press'); chop(c, tl, (0.04, -0.13, 0.05), (-2, 0, 3), (2, 0, 2), 0.22)
    seat(c, tl, 'belt_b'); rack(c, tl, 'punch'); return mag(c, tumble=2)


def sb08(c, tl):
    """Double pump. The opener is a short pump down the well that stops dead on the cue: the magazine is knocked
    loose (1.5 cm down). Wound up again, still, then the full chop stops dead: it flies out. Beside the thigh onto
    the fresh magazine. Up, cocked low, a rising punch on the handle frame."""
    B = c.B; k = c.P['k']; f = B['cue']; e = c.along((0, 0, 0), c.v['exit'], 0.05)
    tl.hold(1); tl.to(f - 3, -e * 0.6, (6, 0, -2), 'ease'); tl.to(f, e * 0.4, (-3, 0, 0), 'slam', rlag=0); tl.kick(f, -e * 0.15 * k, (2 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('cue', f); tl.nodrag.append((f - 3, f + 1))
    chop(c, tl, (0.0, -0.04, 0.02), (-4, 0, -2), (16, 0, -4), 0.16)
    seat(c, tl, 'thigh_b'); rack(c, tl, 'upper'); return mag(c, loosen=[[f, 0.015]])


def sb09(c, tl):
    """Cross-body chop. A tug back stops dead on the cue. The gun is wound up high and across toward the centre,
    canted out, still, then chopped diagonally down and out along the well and stopped dead: the magazine flies down
    and out to the right. Down to the hip pouch. Up, cocked back, punched forward on the handle frame."""
    opener(c, tl, 'tug'); chop(c, tl, (0.05, -0.05, 0.02), (-4, 6, 24), (14, 8, 30), 0.21)
    seat(c, tl, 'hip_b'); rack(c, tl, 'punch'); return mag(c, tumble=4)


def sb10(c, tl):
    """Stock-low tip chop. A muzzle-up snap stops dead on the cue. The gun is raised muzzle-down so the stock and the
    magazine behind the hand come up into view, still, then chopped down along the well (down and back) and stopped
    dead: the magazine drops out from under the stock past the forearm. Into the pouch behind the hip. Up, held out
    in front and yanked back on the handle frame."""
    opener(c, tl, 'tip'); chop(c, tl, (0.02, -0.01, 0.02), (-22, 0, -2), (-14, 0, -2), 0.16)
    seat(c, tl, 'rear_b'); rack(c, tl, 'yank'); return mag(c)


PICKS = {'SB01': ('Wind-up chop', sb01), 'SB02': ('Elbow-out chop', sb02), 'SB03': ('Cant-in chop', sb03), 'SB04': ('Muzzle-up shove', sb04), 'SB05': ('Reach-out chop', sb05),
         'SB06': ('Backhand chop', sb06), 'SB07': ('Drop stop', sb07), 'SB08': ('Double pump', sb08), 'SB09': ('Cross-body chop', sb09), 'SB10': ('Stock-low tip chop', sb10)}
LIFT = (0.0, 0.05, -0.05)      # every chop stops this much higher than drafted from the idle (as GRIP): the magazine is seen leaving
PARAMS = {p: {'lift': LIFT} for p in PICKS}

if __name__ == '__main__': r1lib.main(sys.modules[__name__], sys.argv[1:])
