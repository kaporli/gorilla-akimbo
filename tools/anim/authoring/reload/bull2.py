"""SMG BULLPUP family, round 2: ten one-handed reload techniques (SB11 to SB20) on the Pulsar, take A snappy (light,
2.2 l), right hand, male V, empty reload. Round 1 made every draft a wind-up chop (owner: not what was asked); here
each draft is its own technique and only SB11 (dropped behind past the hip, the owner's example) is a stop-throw.

The magazine sits behind the hand under the stock (centre 6.6 cm behind and 4.6 cm under the grip), curved forward
at its foot; it leaves down along the top of the magazine (14 deg forward), about 7 cm in the well. Released on the
gun's own magazine-out frame (f18), it slides along the well under gravity and the gun's own acceleration (r2lib,
mode well) or is held by a rig while the gun is pulled off (mode hook). The fresh one waits in a pouch and the rear
of the gun, behind the hand, is driven onto it. Same beats for all (r2lib.BEATS take A, 68 frames). The cocking
handle (gun f80 to 86) is time-mapped onto the hit (f53 to 56).

usage: bull2.py list | events | build [ids] [--jobs n] | stats | gates | regate
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r2lib, author
from r2lib import opener, seat, rack, PUNCH
from fk import qrot

FAMILY = 'BULLPUP'; GUN = 'pulsar'; TAKE = 'A'; PREFIX = 'SB'
_ex = np.array((0.0, -0.97, -0.24)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': -_ex}
STATIONS = {'belt_b': ((0.27, 0.22, -0.11), (-16, -6, 4)), 'thigh_b': ((0.28, 0.14, -0.09), (-24, -8, 6)), 'hip_b': ((0.30, 0.23, -0.05), (-20, -12, 10)),
            'stomach_b': ((0.16, 0.24, -0.17), (-16, 10, -6)), 'rear_b': ((0.29, 0.23, 0.02), (-22, -14, 10))}
UP = -14                    # pitch that puts the well vertical (muzzle a little down)
BASE = np.array((-0.007, -0.185, 0.018))      # magazine foot, gun axes


def mag(c, mode='well', **k):
    B = c.B; d = {'release': B['rel'], 'mode': mode, 'out_len': 0.07, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def place(c, rot, local, world):
    """Grip offset that puts a point of the gun (gun axes) on a world point with the gun at angles rot."""
    return np.array(world, float) - c.g0 - qrot(author.qmul(c.q0, author.qeuler(*rot)), np.array(local, float))


def sb11(c, tl):
    """Drop behind. A tug back stops dead on the cue. The gun is lifted in front of the belly, muzzle dipped hard so
    the well points down and back, then the arm drives it down and back past the hip along the well and stops it dead
    behind the hip: the magazine flies on out from under the stock, back and down. The only stop-throw of the family
    (the owner's example). Onto the fresh magazine in the pouch behind the hip. Up, cocked low, a rising punch on the
    cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); back, rrot = c.station('rear_b')
    re = (-45, -10, 8); end = np.array(back) + (0.03, 0.12, 0.0); wu = end - c.along(re, c.v['exit'], 0.18); wr = (-40, -8, 6)
    tl.hold(B['cue'] + 2); tl.to(r - 5, wu, wr, 'drive', rlag=1); tl.hold(r - 4)
    tl.to(r, r2lib.aligned(c, wu, wr, re, 0.18), re, 'slam', rlag=0)
    tl.kick(r, -c.along(re, c.v['exit'], 0.01 * k), (-2 * k, 0, 0), attack=0.5, release=2.5); tl.mark('release', r); tl.nodrag.append((r - 4, r + 1))
    seat(c, tl, 'rear_b', dep=B['dep'] + 1); rack(c, tl, 'upper'); return mag(c, tumble=4)


def sb12(c, tl):
    """Belt strip. The thumb presses the release on the cue. The gun drops to the belt, the magazine's foot hooked
    over the belt edge behind the hand, and the gun is ripped up off it: the belt holds the magazine, it slides out
    from under the stock and drops. Over the fresh magazine on the belt pouch and slammed down onto it. Up, cocked
    back, punched forward on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press')
    hook, rot = c.station('belt_b'); hook = np.array(hook) + (0.02, 0.04, -0.06)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.14); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 6))
    seat(c, tl, 'belt_b', dep=r + 7, arr=B['slam'] - 2); rack(c, tl, 'punch'); return mag(c, mode='hook', appear=r + 9)


def sb13(c, tl):
    """Rattle. The thumb presses the release on the cue. The gun is lifted, well hanging down, still; then the hand
    bounces it down and up twice, the second bounce harder; the first stop lands on the release frame: each sudden
    stop walks the magazine further out from under the stock until it falls clear. Down to the belt pouch. Up, held
    out in front and yanked back on the cocking handle. (A strip on the other forearm was tried first: the gun came
    11 cm from the eye and touched the left gun.)"""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.0, 0.05, -0.04)); ru = (UP, 0, -4)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    e = c.along(ru, c.v['exit'], 1.0)
    tl.to(r + 2, p0 + e * 0.035, ru, PUNCH, rlag=0); tl.to(r + 4, p0, ru, (1.6, 1.6), rlag=0); tl.to(r + 6, p0 + e * 0.05, ru, PUNCH, rlag=0)   # the second bounce runs on into the dive
    tl.mark('release', r); tl.nodrag.append((r, r + 6))
    seat(c, tl, 'belt_b', dep=r + 6, arr=B['slam'] - 2); rack(c, tl, 'yank'); return mag(c)


def sb14(c, tl):
    """Tip back and shake. The thumb presses the release on the cue. The muzzle is tipped back up (the magazine's
    foot points forward and down) and the gun rocked three times, muzzle nodding: the magazine works loose and, on
    the last rock, slides out forward under the gun by its weight. Down to the stomach pouch. Up, held muzzle-high,
    the muzzle thrown down on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); base = np.array((0.0, 0.04, 0.0)); tip = 34
    tl.hold(B['cue'] + 1); tl.to(B['cue'] + 4, base, (tip, 0, -4), 'drive', rlag=1)
    f = B['cue'] + 4; marks = []
    for j, pitch in enumerate((tip + 10, tip - 6, tip + 8)):
        tl.to(f + 2, base + (0, 0.006 * (j % 2), 0), (pitch, 0, -4), PUNCH, rlag=0); tl.kick(f + 2, (0, 0, 0), (-2 * k, 0, 0), attack=0.5, release=1.5); marks.append(f + 2); f += 2
    tl.to(r - 1, base, (tip, 0, -4), 'drive', rlag=0); tl.hold(r); tl.mark('loosen', marks[0]); tl.mark('release', r)
    seat(c, tl, 'stomach_b', dep=B['dep'] + 2); rack(c, tl, 'nod')
    return mag(c, loosen=[[marks[0], 0.008], [marks[1], 0.016], [marks[2], 0.026]])


def sb15(c, tl):
    """Press and drop. The gun is lifted a hand high, muzzle a little down so the well hangs straight down, still.
    The thumb presses the release (a small dip that stops dead on the release frame) and the magazine slides out from
    under the stock by its own weight and drops past the forearm. Still until it is clear, then down to the belt
    pouch. Up, cocked back, punched forward on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; up = (0.01, 0.07, -0.04); ru = (UP, 0, -4)
    tl.hold(2); tl.to(r - 6, up, ru, 'drive', rlag=1); tl.kick(r - 6, (0, -0.004, 0), (-2, 0, 0), release=2.5)
    tl.hold(r - 3); tl.to(r, np.array(up) + (0, -0.006, 0), (UP - 2, 0, -4), 'slam', rlag=0); tl.kick(r, (0, 0.003 * k, 0), (1.5 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('cue', r - 3); tl.mark('release', r); tl.nodrag.append((r - 3, r + 6))
    seat(c, tl, 'belt_b', dep=B['dep'] + 2); rack(c, tl, 'punch'); return mag(c)


def sb16(c, tl):
    """Jerk up. A small dip stops dead on the cue. The gun is held still at chest height; on the release frame the
    arm jerks it straight up: the magazine stays where it was, slides out from under the rising stock and drops. The
    gun stops high, then goes down to the thigh pouch. Up, cocked low, a rising punch on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); low = np.array((0.01, -0.02, -0.03)); ru = (UP + 4, 0, -4)
    tl.hold(B['cue'] + 2); tl.to(r - 3, low, ru, 'drive', rlag=1); tl.hold(r)
    top = low - c.along(ru, c.v['exit'], 0.15); tl.to(r + 4, top, ru, (1.3, 2.6), rlag=0); tl.kick(r + 4, c.along(ru, c.v['exit'], 0.008), (-2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 5))
    seat(c, tl, 'thigh_b', dep=r + 5, arr=B['slam'] - 2); rack(c, tl, 'upper'); return mag(c)


def sb17(c, tl):
    """Side flick. A tug back stops dead on the cue. The gun is turned in, then the wrist flicks it outward and rolls
    it onto its right side in one snap that stops dead with the well pointing out: the magazine flies on out from
    under the stock to the right. Down to the hip pouch. Up, held out in front and yanked back on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); p0, r0, re = (-0.02, 0.04, -0.03), (UP, 0, -24), (UP - 4, 0, 70)
    tl.hold(B['cue'] + 2); tl.to(r - 5, p0, r0, 'ease', rlag=1); tl.hold(r - 4)
    tl.to(r, r2lib.aligned(c, p0, r0, re, 0.07), re, 'slam', rlag=0); tl.kick(r, (-0.01 * k, 0, 0), (0, 0, -6 * k), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 4, r + 2))
    seat(c, tl, 'hip_b'); rack(c, tl, 'yank'); return mag(c, tumble=5)


def sb18(c, tl):
    """Thigh strip. The thumb presses the release on the cue. The gun swings down beside the thigh, the magazine's
    foot hooked on the edge of the thigh rig, then ripped forward and up off it: the rig holds the magazine, it
    slides out and drops. Back over the fresh magazine on the thigh pouch and slammed onto it. Up, held muzzle-high,
    the muzzle thrown down on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press')
    hook, rot = c.station('thigh_b'); hook = np.array(hook) + (0.02, 0.0, -0.08)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.14); tl.to(r + 4, off, rot, PUNCH, rlag=0); tl.kick(r + 4, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 6))
    seat(c, tl, 'thigh_b', dep=r + 7, arr=B['slam'] - 2); rack(c, tl, 'nod'); return mag(c, mode='hook', appear=r + 9)


def sb19(c, tl):
    """Pouch dump. A tug back stops dead on the cue. The gun goes down to the belt, then drops the last hand along
    the well and stops dead over the pouch: the magazine drops on out from under the stock past the pouch. A short
    shift back and the gun is driven onto the fresh magazine beside it: the change happens at the belt, out of view.
    Up, cocked back, punched forward on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); pos, rot = c.station('belt_b'); hov = np.array(pos) + c.along(rot, c.v['enter'], 0.12) + (0.05, 0.02, -0.04)
    pre = hov - c.along(rot, c.v['exit'], 0.12)
    tl.hold(B['cue'] + 2); tl.to(r - 4, pre, rot, 'drive', rlag=1); tl.hold(r - 3); tl.to(r, hov, rot, 'slam', rlag=0)
    tl.kick(r, -c.along(rot, c.v['exit'], 0.01 * k), (-2 * k, 0, 0), attack=0.5, release=2.5); tl.mark('release', r); tl.nodrag.append((r - 3, r + 1))
    seat(c, tl, 'belt_b', dep=r + 6, arr=B['slam'] - 2); rack(c, tl, 'punch'); return mag(c, appear=r + 8)


def sb20(c, tl):
    """Forward jab. The thumb presses the release on the cue. The gun is held still; on the release frame the arm
    jabs it forward and up and stops at arm's length: the magazine is left behind under the forearm, slides out and
    drops. Back and down to the hip pouch. Up, held muzzle-high, the muzzle thrown down on the cocking handle."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.01, 0.0, 0.0)); ru = (UP + 4, 0, -4)
    jab = np.array((0.0, 0.12, -0.06))
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    tl.to(r + 4, p0 + jab, ru, (1.3, 2.6), rlag=0); tl.kick(r + 4, (0, -0.004, 0.008), (-2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 5))
    seat(c, tl, 'hip_b', dep=r + 5, arr=B['slam'] - 2); rack(c, tl, 'nod'); return mag(c)


PICKS = {'SB11': ('Drop behind', sb11), 'SB12': ('Belt strip', sb12), 'SB13': ('Rattle', sb13), 'SB14': ('Tip back and shake', sb14), 'SB15': ('Press and drop', sb15),
         'SB16': ('Jerk up', sb16), 'SB17': ('Side flick', sb17), 'SB18': ('Thigh strip', sb18), 'SB19': ('Pouch dump', sb19), 'SB20': ('Forward jab', sb20)}
PARAMS = {}

if __name__ == '__main__': r2lib.main(sys.modules[__name__], sys.argv[1:])
