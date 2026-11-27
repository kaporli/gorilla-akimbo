"""SMG GRIP family, round 1: ten one-handed reload drafts (SG01 to SG10) on the Senkoh LX, take A snappy (light,
0.9 l), right hand, male V, empty reload. Magazine in the pistol grip: it leaves down out of the grip along the
grip's rake (27 deg, from the magazine mesh; the game's own exit carries the left hand's sideways pull). Most chops
stop with the muzzle 16 to 22 deg up so the grip is about vertical: the magazine drops straight down in view
instead of back toward the eye. The fresh one waits in a belt pouch lying back along the body (the pouch search
turns the gun muzzle-down: a level gun at the hip bends the wrist 70 to 100 deg) and the gun is driven back onto it. Every draft: opener, wind-up, one chop along the
grip with a dead stop on the release beat (the magazine flies on at the gun's speed), down to the pouch, seated,
up, rack, idle (r1lib.BEATS take A, 68 frames).
The Senkoh's empty reload moves no gun part: the rack beat is a dead stop with nothing to drive.

usage: grip1.py list | events | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r1lib
from r1lib import opener, chop, seat, rack

FAMILY = 'GRIP'; GUN = 'senkoh'; TAKE = 'A'; PREFIX = 'SG'
_ex = np.array((0.0, -0.89, 0.45)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': -_ex}
# pouches: offset of the grip from the hips joint (x to the gun hand's side, y up, z back), search start angles. The
# grip points down into the pouch: the gun is held about level, muzzle forward-down, the magazine stands raked in it.
STATIONS = {'belt_g': ((0.27, 0.20, -0.07), (-20, -6, 4)), 'thigh_g': ((0.28, 0.12, -0.05), (-28, -8, 6)), 'hip_g': ((0.30, 0.21, 0.0), (-24, -12, 10)),
            'stomach_g': ((0.17, 0.22, -0.13), (-20, 10, -6)), 'rear_g': ((0.29, 0.21, 0.07), (-26, -14, 10))}


def mag(c, **k):
    B = c.B; d = {'release': B['rel'], 'mode': 'inertia', 'push': 0.004, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def sg01(c, tl):
    """Wind-up chop. A tug back stops dead on the cue. The muzzle is lifted and the gun raised along the grip, still,
    then chopped straight down the grip and stopped dead in front of the chest: the magazine flies on down out of the
    grip and falls. Down to the belt pouch, the grip driven onto the fresh magazine. Up, cocked low, a rising punch
    stops dead on the hit."""
    opener(c, tl, 'tug'); chop(c, tl, (0.0, -0.03, 0.02), (20, 0, 0), (36, 0, -3), 0.17)
    seat(c, tl, 'belt_g'); rack(c, tl, 'upper'); return mag(c)


def sg02(c, tl):
    """High chop. A muzzle-up snap stops dead on the cue. The gun is wound up high and out to the right, muzzle up,
    still, then one long chop down the grip stops dead at the lower chest: the magazine is thrown down hard. Down
    beside the thigh onto the fresh magazine. Up, cocked back, punched forward: dead stop on the hit."""
    opener(c, tl, 'tip'); chop(c, tl, (0.02, -0.08, 0.03), (18, 0, -2), (36, -4, -4), 0.21)
    seat(c, tl, 'thigh_g'); rack(c, tl, 'punch'); return mag(c, tumble=4)


def sg03(c, tl):
    """Cant-in chop. A small snap stops dead on the cue. The gun is lifted and canted inward (the grip points down
    and left), still, then chopped along the canted grip and stopped dead: the magazine flies out down-left, between
    the guns. Down to the stomach pouch. Up, held muzzle-high, and the muzzle is thrown down on the hit."""
    opener(c, tl, 'snap'); chop(c, tl, (0.03, -0.03, 0.02), (16, 0, -32), (28, 0, -36), 0.16)
    seat(c, tl, 'stomach_g'); rack(c, tl, 'nod'); return mag(c)


def sg04(c, tl):
    """Cant-out chop. The thumb presses the release: a small dip stops dead on the cue. The gun is canted outward and
    raised, still, then chopped down-out along the grip and stopped dead: the magazine flies out to the right and
    falls. Down to the hip pouch. Up, held out in front and yanked back on the hit."""
    opener(c, tl, 'press'); chop(c, tl, (0.02, -0.03, 0.02), (16, 0, 34), (28, 0, 38), 0.17)
    seat(c, tl, 'hip_g'); rack(c, tl, 'yank'); return mag(c)


def sg05(c, tl):
    """Reach-out chop. A tug back stops dead on the cue. The arm reaches out forward and up, muzzle up, still, then
    the gun is chopped straight down the grip at arm's length and stopped dead: the magazine, further from the eye,
    is seen dropping in front. Back and down into the pouch behind the hip. Up, cocked back, punched forward on the
    hit."""
    opener(c, tl, 'tug'); chop(c, tl, (0.0, -0.02, -0.04), (22, 0, -2), (30, 0, -3), 0.19)
    seat(c, tl, 'rear_g'); rack(c, tl, 'punch'); return mag(c)


def sg06(c, tl):
    """Muzzle-up shove. A muzzle-up snap stops dead on the cue. The muzzle is tipped up steep and the gun drawn in,
    still, then shoved down and forward along the grip and stopped dead: the magazine shoots out in front of the
    gun. Down to the belt pouch. Up, held out in front and yanked back on the hit."""
    opener(c, tl, 'tip'); chop(c, tl, (0.0, -0.05, 0.0), (36, -4, -4), (40, -4, -4), 0.16)
    seat(c, tl, 'belt_g'); rack(c, tl, 'yank'); return mag(c)


def sg07(c, tl):
    """Drop stop. The thumb presses the release: a small dip stops dead on the cue. The gun rises a hand high without
    turning, muzzle a little up, still, then the arm drops it straight down along the grip and stops it dead at the
    chest: the magazine keeps falling out of the grip. Onto the fresh magazine at the belt. Up, cocked back, punched forward on the hit."""
    opener(c, tl, 'press'); chop(c, tl, (0.03, -0.08, 0.03), (22, 0, 3), (22, 0, 2), 0.21)
    seat(c, tl, 'belt_g'); rack(c, tl, 'punch'); return mag(c, tumble=2)


def sg08(c, tl):
    """Double pump. The opener is a short pump down the grip that stops dead on the cue: the magazine is knocked
    loose (1.5 cm down the grip). Wound up again, still, then the full chop stops dead: it flies out. Beside the
    thigh onto the fresh magazine. Up, held out in front and yanked back on the hit."""
    B = c.B; k = c.P['k']; f = B['cue']; e = c.along((0, 0, 0), c.v['exit'], 0.05)
    tl.hold(1); tl.to(f - 3, -e * 0.6, (6, 0, -2), 'ease'); tl.to(f, e * 0.4, (-3, 0, 0), 'slam', rlag=0); tl.kick(f, -e * 0.15 * k, (2 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('cue', f); tl.nodrag.append((f - 3, f + 1))
    chop(c, tl, (0.0, -0.04, 0.02), (20, 0, -2), (34, 0, -4), 0.16)
    seat(c, tl, 'thigh_g'); rack(c, tl, 'yank'); return mag(c, loosen=[[f, 0.015]])


def sg09(c, tl):
    """Cross-body chop. A tug back stops dead on the cue. The gun is wound up high and across toward the centre,
    canted out, still, then chopped diagonally down and out along the grip and stopped dead: the magazine flies down
    and out to the right. Down to the hip pouch. Up, cocked back, punched forward on the hit."""
    opener(c, tl, 'tug'); chop(c, tl, (0.05, -0.05, 0.02), (16, 6, 24), (30, 8, 30), 0.21)
    seat(c, tl, 'hip_g'); rack(c, tl, 'punch'); return mag(c, tumble=4)


def sg10(c, tl):
    """Backhand chop. A small snap stops dead on the cue. The gun is rolled onto its right side (the grip points out
    to the right) and drawn in, still, then backhanded outward along the grip and stopped dead: the magazine flies
    out sideways to the right and drops. Into the pouch behind the hip. Up, held muzzle-high, the muzzle thrown down
    on the hit."""
    opener(c, tl, 'snap'); chop(c, tl, (0.07, -0.03, 0.02), (2, -4, 72), (8, -2, 66), 0.17)
    seat(c, tl, 'rear_g'); rack(c, tl, 'nod'); return mag(c, tumble=5)


PICKS = {'SG01': ('Wind-up chop', sg01), 'SG02': ('High chop', sg02), 'SG03': ('Cant-in chop', sg03), 'SG04': ('Cant-out chop', sg04), 'SG05': ('Reach-out chop', sg05),
         'SG06': ('Muzzle-up shove', sg06), 'SG07': ('Drop stop', sg07), 'SG08': ('Double pump', sg08), 'SG09': ('Cross-body chop', sg09), 'SG10': ('Backhand chop', sg10)}
LIFT = (0.0, 0.06, 0.01)      # every chop stops this much higher and further out than drafted from the idle: the grip's
                               # magazine starts 15 cm above the screen's lower edge and is seen leaving (first look: 1 frame)
PARAMS = {p: {'lift': LIFT} for p in PICKS}

if __name__ == '__main__': r1lib.main(sys.modules[__name__], sys.argv[1:])
