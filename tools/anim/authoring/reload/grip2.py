"""SMG GRIP family, round 2: ten one-handed reload techniques (SG11 to SG20) on the Senkoh LX, take A snappy (light,
0.9 l), right hand, male V, empty reload; owner pick 1 from round 1 (SG08 Double pump) shown first, kept as is.
Round 1 made every draft a wind-up chop (owner: not what was asked); here each draft is its own technique; no double
pump, and the only stop-throw is SG17, the owner's own example of a thumb-release drop on a short downward snap.
Tried and dropped: a forearm strip on the left wrist (the gun came 9 cm from the eye and touched the left gun), a
whip flip, a barrel roll and a pendulum swing (a spin pushes a grip magazine into its walls, not out: it left the
grip late, with a speed unrelated to the move).

Magazine in the pistol grip, 27 deg rake, about 15 cm long: released on the gun's own magazine-out frame (f18), it
slides down the grip under gravity and the gun's own acceleration (r2lib, mode well) or is held by a rig while the
gun is pulled off (mode hook), and is free 8 cm out. The fresh one waits in a pouch lying back along the belt and
the gun is driven onto it (pouch search: a level gun at the hip bends the wrist 70 to 100 deg, so muzzle down).
Same beats for all (r2lib.BEATS take A, 68 frames). The Senkoh moves no gun part in its empty reload: the rack
beat drives nothing.

usage: grip2.py list | events | build [ids] [--jobs n] | stats | gates | regate
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r2lib, author
from r2lib import opener, seat, rack, PUNCH
from fk import qrot

FAMILY = 'GRIP'; GUN = 'senkoh'; TAKE = 'A'; PREFIX = 'SG'
_ex = np.array((0.0, -0.89, 0.45)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': -_ex}
STATIONS = {'belt_g': ((0.27, 0.20, -0.07), (-20, -6, 4)), 'thigh_g': ((0.28, 0.12, -0.05), (-28, -8, 6)), 'hip_g': ((0.30, 0.21, 0.0), (-24, -12, 10)),
            'stomach_g': ((0.17, 0.22, -0.13), (-20, 10, -6)), 'rear_g': ((0.29, 0.21, 0.07), (-26, -14, 10))}
UP = 27                     # pitch that puts the grip axis vertical
BASE = np.array((-0.005, -0.113, 0.039))      # magazine floor plate, gun axes


def mag(c, mode='well', **k):
    B = c.B; d = {'release': B['rel'], 'mode': mode, 'out_len': 0.08, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def place(c, rot, local, world):
    """Grip offset that puts a point of the gun (gun axes) on a world point with the gun at angles rot."""
    return np.array(world, float) - c.g0 - qrot(author.qmul(c.q0, author.qeuler(*rot)), np.array(local, float))


def sg11(c, tl):
    """Press and drop. The gun is lifted a hand high and turned muzzle-up until the grip hangs straight down, still.
    The thumb presses the release (a small dip that stops dead on the release frame) and the magazine slides out of
    the grip by its own weight and drops past the hand. The gun holds still until it is clear, then goes down to the
    belt pouch onto the fresh magazine. Up, cocked back, punched forward on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; up = (0.01, 0.07, -0.02); ru = (UP, 0, -4)
    tl.hold(2); tl.to(r - 6, up, ru, 'drive', rlag=1); tl.kick(r - 6, (0, -0.004, 0), (-2, 0, 0), release=2.5)
    tl.hold(r - 3); tl.to(r, np.array(up) + (0, -0.006, 0), (UP - 2, 0, -4), 'slam', rlag=0); tl.kick(r, (0, 0.003 * k, 0), (1.5 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('cue', r - 3); tl.mark('release', r); tl.nodrag.append((r - 3, r + 6))
    seat(c, tl, 'belt_g', dep=B['dep'] + 2); rack(c, tl, 'punch'); return mag(c)


def sg12(c, tl):
    """Side flick. A tug back stops dead on the cue. The gun is turned in and up, then the wrist flicks it outward
    and rolls it onto its right side in one snap that stops dead with the grip pointing out: the magazine flies on
    out of the grip to the right. Down to the hip pouch. Up, held out in front and yanked back on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); p0, r0, re = (-0.03, 0.04, -0.01), (UP, 0, -24), (UP - 6, 0, 70)
    tl.hold(B['cue'] + 2); tl.to(r - 5, p0, r0, 'ease', rlag=1); tl.hold(r - 4)
    tl.to(r, r2lib.aligned(c, p0, r0, re, 0.07), re, 'slam', rlag=0); tl.kick(r, (-0.01 * k, 0, 0), (0, 0, -6 * k), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 4, r + 2))
    seat(c, tl, 'hip_g'); rack(c, tl, 'yank'); return mag(c, tumble=5)


def sg13(c, tl):
    """Belt strip. The thumb presses the release on the cue. The gun drops to the belt, the grip's floor plate
    hooked over the belt edge, and is ripped up off it along the grip: the belt holds the magazine, it slides off the
    gun and drops. Wound over the fresh magazine on the belt pouch beside it and slammed down onto it. Up, cocked
    back, punched forward on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press')
    hook, rot = c.station('belt_g'); hook = np.array(hook) + (0.02, 0.03, -0.06)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.16); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 6))
    seat(c, tl, 'belt_g', dep=r + 7, arr=B['slam'] - 2); rack(c, tl, 'punch'); return mag(c, mode='hook', appear=r + 9)


def sg14(c, tl):
    """Tilt and shake. The thumb presses the release on the cue. The gun is canted inward, grip down, and shaken
    left and right three times: each shake works the magazine a little further out of the grip; on the last one the
    grip comes upright and it slides out by its weight. Down to the stomach pouch. Up, held muzzle-high, the muzzle
    thrown down on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); base = np.array((0.0, 0.05, -0.02))
    tl.hold(B['cue'] + 1); tl.to(B['cue'] + 4, base, (UP - 4, 0, -40), 'drive', rlag=1)
    f = B['cue'] + 4; marks = []
    for j, (dx, roll) in enumerate(((0.025, -18), (-0.02, -44), (0.025, -16))):
        tl.to(f + 2, base + (dx, 0, 0), (UP - 4, 0, roll), PUNCH, rlag=0); tl.kick(f + 2, (-dx * 0.2, 0, 0), (0, 0, 3 * k), attack=0.5, release=1.5); marks.append(f + 2); f += 2
    tl.to(r, base + (0.0, 0.01, 0), (UP, 0, -4), 'drive', rlag=0); tl.mark('loosen', marks[0]); tl.mark('release', r)
    seat(c, tl, 'stomach_g', dep=B['dep'] + 2); rack(c, tl, 'nod')
    return mag(c, loosen=[[marks[0], 0.01], [marks[1], 0.02], [marks[2], 0.035]])


def sg15(c, tl):
    """Jerk up. A small dip stops dead on the cue. The gun is held still at chest height, grip down; on the release
    frame the arm jerks it straight up along the grip: the magazine stays where it was, slides out of the rising grip
    and drops. The gun stops high, then goes down to the thigh pouch. Up, cocked low, a rising punch on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); low = np.array((0.01, -0.02, -0.01)); ru = (UP - 6, 0, -4)
    tl.hold(B['cue'] + 2); tl.to(r - 3, low, ru, 'drive', rlag=1); tl.hold(r)
    top = low - c.along(ru, c.v['exit'], 0.15); tl.to(r + 4, top, ru, (1.3, 2.6), rlag=0); tl.kick(r + 4, c.along(ru, c.v['exit'], 0.008), (-2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 5))
    seat(c, tl, 'thigh_g', dep=r + 5, arr=B['slam'] - 2); rack(c, tl, 'upper'); return mag(c)


def sg16(c, tl):
    """Thigh strip. The thumb presses the release on the cue. The gun swings down beside the thigh and the grip's
    floor plate is hooked on the edge of the thigh rig, then the gun is ripped forward and up off it along the grip:
    the rig holds the magazine, it slides off and drops. Back over the fresh magazine on the thigh pouch and slammed
    onto it. Up, held out in front and yanked back on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press')
    hook, rot = c.station('thigh_g'); hook = np.array(hook) + (0.02, 0.0, -0.08)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.16); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 6))
    seat(c, tl, 'thigh_g', dep=r + 7, arr=B['slam'] - 2); rack(c, tl, 'yank'); return mag(c, mode='hook', appear=r + 9)


def sg17(c, tl):
    """Snap drop. The gun is held still at chest height, grip down, the thumb on the release; one short snap down
    the grip (8 cm, no wind-up) stops dead on the release frame and the magazine drops on out of it. The owner's
    example of a thumb-release drop on a downward snap; the only stop-throw of the family. Down to the belt pouch.
    Up, cocked low, a rising punch on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; p0 = np.array((0.0, 0.06, -0.02)); ru = (UP - 2, 0, -4)
    tl.hold(3); tl.to(r - 5, p0, ru, 'drive', rlag=1); tl.kick(r - 5, (0, -0.004, 0), (-1.5, 0, 0), release=2.5); tl.mark('cue', r - 5); tl.hold(r - 3)
    tl.to(r, p0 + c.along(ru, c.v['exit'], 0.08), ru, 'slam', rlag=0); tl.kick(r, -c.along(ru, c.v['exit'], 0.01 * k), (1.5 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 3, r + 2))
    seat(c, tl, 'belt_g'); rack(c, tl, 'upper'); return mag(c)


def sg18(c, tl):
    """Forward jab. The thumb presses the release on the cue. The gun is held still, muzzle a little down; on the
    release frame the arm jabs it forward and up along the grip and stops at arm's length: the magazine is left
    behind, slides out of the grip and drops under the arm. Back and down to the hip pouch. Up, held muzzle-high,
    the muzzle thrown down on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.01, 0.0, 0.02)); ru = (-20, 0, -4)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    out = p0 - c.along(ru, c.v['exit'], 0.15); tl.to(r + 4, out, ru, (1.3, 2.6), rlag=0); tl.kick(r + 4, c.along(ru, c.v['exit'], 0.008), (-2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 5))
    seat(c, tl, 'hip_g', dep=r + 5, arr=B['slam'] - 2); rack(c, tl, 'nod'); return mag(c)


def sg19(c, tl):
    """Rattle. The thumb presses the release on the cue. The gun is lifted, grip down, still; on the release frame
    the hand bounces it down and up, then down again harder, running on into the dive: each sudden stop walks
    the magazine further out of the grip until it falls clear. Down to the thigh pouch. Up, held muzzle-high, the muzzle thrown down on the
    hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.0, 0.05, -0.02)); ru = (UP - 2, 0, -4)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    e = c.along(ru, c.v['exit'], 1.0)
    tl.to(r + 2, p0 + e * 0.035, ru, PUNCH, rlag=0); tl.to(r + 4, p0, ru, (1.6, 1.6), rlag=0); tl.to(r + 6, p0 + e * 0.05, ru, PUNCH, rlag=0)   # the second bounce runs on into the dive
    tl.mark('release', r); tl.nodrag.append((r, r + 6))
    seat(c, tl, 'thigh_g', dep=r + 6, arr=B['slam'] - 2); rack(c, tl, 'nod'); return mag(c)


def sg20(c, tl):
    """Pouch dump. A tug back stops dead on the cue. The gun goes straight down to the belt and stops dead over the
    pouch: the magazine drops out of the grip past the pouch. A short shift back and the gun is driven onto the fresh
    magazine standing beside it: the whole change happens at the belt, out of view. Up, cocked back, punched forward
    on the hit."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); pos, rot = c.station('belt_g'); hov = np.array(pos) + c.along(rot, c.v['enter'], 0.12) + (0.05, 0.02, -0.04)
    tl.hold(B['cue'] + 2); tl.to(r, hov, rot, 'slam', rlag=1); tl.kick(r, -c.along(rot, c.v['exit'], 0.01 * k), (-2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r)
    seat(c, tl, 'belt_g', dep=r + 6, arr=B['slam'] - 2); rack(c, tl, 'punch'); return mag(c, appear=r + 8)


def _pinned(c, tl): pass
_pinned.__doc__ = 'Owner pick 1 of 3 from round 1, kept as is (round1-grip/clips/pma).'

PINNED = {'SG08': 'Owner pick 1 of 3 (round 1)'}
PICKS = {'SG08': ('Double pump', _pinned),
         'SG11': ('Press and drop', sg11), 'SG12': ('Side flick', sg12), 'SG13': ('Belt strip', sg13), 'SG14': ('Tilt and shake', sg14), 'SG15': ('Jerk up', sg15),
         'SG16': ('Thigh strip', sg16), 'SG17': ('Snap drop', sg17), 'SG18': ('Forward jab', sg18), 'SG19': ('Rattle', sg19), 'SG20': ('Pouch dump', sg20)}
PARAMS = {}

if __name__ == '__main__': r2lib.main(sys.modules[__name__], sys.argv[1:])
