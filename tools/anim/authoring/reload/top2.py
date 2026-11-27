"""SMG TOP family, round 2: ten one-handed reload techniques (ST11 to ST20) on the Warden, take B heavy (7.0 l),
right hand, male V, empty reload; its own one-handed reload, not the Shingen two-arm knock. Round 1 made every
draft a wind-up chop (owner: not what was asked); here each draft is its own technique and only ST13 (tip-forward
throw, the owner's example) is a stop-throw.

The magazine lies on top behind the sight and lifts off forward-up (42 deg above the barrel line), guided 6 cm:
the rule that it leaves along its axis is checked over the first 7 cm (rifle wells: 10 cm; past the rail it is clear
and the gun may move away in any direction).
Released on the gun's own magazine-out frame (f21, its latch opens on the cue f7), it slides along that axis under
gravity and the gun's own acceleration (r2lib, mode well) or is held by a rig while the gun is pulled off (hook).
The fresh one comes onto the top from the gun's above: up under a magazine hanging from the stomach rig, or the gun
turned over and pressed onto one in a belt pouch, on the hip or on the outer thigh. Same beats for all (r2lib.BEATS
take B, 77 frames). The cocking device (gun f95 to 119) is time-mapped onto the hit (f61) to the end.
On this gun a positive roll turns the top to the left (toward the other gun).

usage: top2.py list | events | build [ids] [--jobs n] | stats | gates | regate
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r2lib, author
from r2lib import opener, seat, rack, PUNCH
from fk import qrot

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'ST'
_ex = np.array((0.0, 0.67, -0.74)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': np.array((0.0, -1.0, 0.0))}
STATIONS = {'stomach_t': ((0.18, 0.22, -0.24), (-10, 20, 0)),      # upright, under a magazine hanging lips-down from the belt front
            'belt_t': ((0.27, 0.20, -0.08), (-40, 0, 180)),        # turned over, pressed down onto a magazine standing in a belt pouch
            'hip_t': ((0.31, 0.20, -0.10), (-60, -10, 160)),       # muzzle down, top back, pressed back onto a magazine on the hip
            'thigh_t': ((0.34, 0.18, -0.02), (-60, 0, 90))}        # muzzle down, top toward the leg, pressed onto a magazine on the outer thigh


def mag(c, mode='well', **k):
    B = c.B; d = {'release': B['rel'], 'mode': mode, 'out_len': 0.06, 'axis_check_m': 0.07, 'tumble': 3, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08}; d.update(k)
    return {'mag': d}


def press(c, tl, pos, rot, f0, r):
    """Into the pose by r - 3, still, a small press that stops dead on the release frame r."""
    k = c.P['k']; tl.hold(f0); tl.to(r - 4, pos, rot, 'drive', rlag=1); tl.kick(r - 4, (0, -0.004, 0), (-1.5, 0, 0), release=2.5); tl.hold(r - 2)
    tl.to(r, np.array(pos) + (0, -0.005, 0), rot, 'slam', rlag=0); tl.kick(r, (0, 0.003 * k, 0), (1.5 * k, 0, 0), attack=0.5, release=2.0)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 8))


def st11(c, tl):
    """Flip and drop. A small dip stops dead on the latch frame. The gun is turned over, top down, and pushed out a
    little, still; the thumb presses the release and the magazine slides off the underside by its own weight and
    falls in front. Still turned over, down to the belt and pressed onto the fresh magazine in the pouch. Rolled
    upright as it rises, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; opener(c, tl, 'press'); press(c, tl, (0.02, 0.0, -0.06), (0, 0, 172), B['cue'] + 2, r)
    seat(c, tl, 'belt_t', dep=r + 5); rack(c, tl, 'nod'); return mag(c)


def st12(c, tl):
    """Belt knock-off. A tug back stops dead on the latch frame. The gun is turned over and brought down to the belt,
    the magazine's front edge set against the lip of the belt rig, then pulled back and down off it: the rig holds the
    magazine, it is knocked off forward and drops. Over the fresh magazine in the pouch beside it and pressed down
    onto it. Rolled upright as it rises, cocked back, punched forward on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug')
    hook, rot = c.station('belt_t'); hook = np.array(hook) + (0.02, 0.10, -0.08)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0, -0.008 * k, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.10); tl.to(r + 5, off, rot, PUNCH, rlag=0); tl.kick(r + 5, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 7))
    seat(c, tl, 'belt_t', dep=r + 8, arr=B['slam'] - 1); rack(c, tl, 'punch'); return mag(c, mode='hook', appear=r + 10)


def st13(c, tl):
    """Tip-forward throw. The thumb presses the latch: a dip stops dead on its frame. The muzzle is tipped down and
    the gun rolled out a little and drawn back, then thrust forward and stopped dead: the magazine flies off the top
    ahead and drops in front. The only stop-throw of the family (the owner's example). Down in front of the stomach
    and driven up under the fresh magazine hanging from the belt rig. Up, cocked back, punched forward on the cocking
    device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); stop, sr, wr = np.array((0.03, -0.10, -0.02)), (-30, 0, 52), (-24, 0, 46)
    wu = stop - c.along(sr, c.v['exit'], 0.20); tl.hold(B['cue'] + 2); tl.to(r - 6, wu, wr, 'drive', rlag=1); tl.hold(r - 5)
    tl.to(r, r2lib.aligned(c, wu, wr, sr, 0.20), sr, 'slam', rlag=0); tl.kick(r, -c.along(sr, c.v['exit'], 0.012 * k), (1, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 5, r + 1))
    seat(c, tl, 'stomach_t'); rack(c, tl, 'punch'); return mag(c)


def st14(c, tl):
    """Jerk down. A tug back stops dead on the latch frame. The gun is held still at chest height; on the release
    frame the arm jerks it down, back and out to the right from under the magazine: the magazine stays in the air
    where it was, the gun drops away from under it and it falls in front. Down and up under the magazine hanging from the belt rig. Up, cocked low,
    a rising punch on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug'); p0 = np.array((0.0, 0.02, -0.02)); ru = (0, 0, -3)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    low = p0 - c.along(ru, c.v['exit'], 0.12) + (0.16, -0.04, 0.0); tl.to(r + 5, low, (-6, 0, -3), (1.3, 2.6), rlag=0); tl.kick(r + 5, (0, 0.004, 0), (2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 6))
    seat(c, tl, 'stomach_t', dep=r + 6); rack(c, tl, 'upper'); return mag(c)


def st15(c, tl):
    """Inverted shake. The thumb presses the latch: a dip stops dead on its frame. The gun is turned over and shaken
    out to the side and back twice, the magazine working loose on its rail; on the release frame the gun stops,
    still, and it slides off the underside by its weight. Turned over, pressed onto the magazine in the belt pouch.
    Rolled upright as it rises, held out in front and yanked back on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); base = np.array((0.02, 0.0, -0.05)); inv = (0, 0, 172)
    tl.hold(B['cue'] + 1); tl.to(B['cue'] + 5, base, inv, 'drive', rlag=1); f = B['cue'] + 5; marks = []
    for dx in (0.03, -0.01, 0.03):
        tl.to(f + 2, base + (dx, 0, 0), (0, 0, 172 - dx * 200), PUNCH, rlag=0); tl.kick(f + 2, (-dx * 0.2, 0, 0), (0, 0, 2 * k), attack=0.5, release=1.5); marks.append(f + 2); f += 2
    tl.to(r - 1, base, inv, 'drive', rlag=0); tl.hold(r); tl.mark('loosen', marks[0]); tl.mark('release', r)
    seat(c, tl, 'belt_t', dep=r + 5); rack(c, tl, 'yank')
    return mag(c, loosen=[[marks[0], 0.004], [marks[1], 0.008], [marks[2], 0.012]])


def st16(c, tl):
    """Yank back. The thumb presses the latch: a dip stops dead on its frame. The gun is held out in front, still;
    on the release frame the arm yanks it back, down and out to the right: the magazine is left hanging in front, the
    gun pulled out from under it, and it falls. Down to the hip and pressed back onto the magazine there. Up, held
    muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.0, 0.0, -0.08)); ru = (-4, 0, -3)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    back = p0 + np.array((0.16, -0.08, 0.10)); tl.to(r + 5, back, (-10, 0, -3), (1.3, 2.6), rlag=0); tl.kick(r + 5, (0, 0.004, -0.006), (2 * k, 0, 0), attack=0.5, release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 1, r + 6))
    seat(c, tl, 'hip_t', dep=r + 6); rack(c, tl, 'nod'); return mag(c)


def st17(c, tl):
    """Thigh knock-off. A tug back stops dead on the latch frame. Muzzle down, top toward the leg, the gun swings
    down beside the thigh and the magazine's front edge is set against the thigh rig, then the gun is pulled back
    and up off it: the rig holds the magazine, it is knocked off and drops. Onto the fresh magazine on the outer
    thigh. Up, cocked low, a rising punch on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'tug')
    hook, rot = c.station('thigh_t'); hook = np.array(hook) + (0.06, 0.04, -0.04)
    tl.hold(B['cue'] + 2); tl.to(r, hook, rot, 'heavy', rlag=1); tl.kick(r, (0.006 * k, 0, 0), (-2, 0, 0), attack=0.5, release=2.0)
    off = hook - c.along(rot, c.v['exit'], 0.10); tl.to(r + 5, off, rot, PUNCH, rlag=0); tl.kick(r + 5, c.along(rot, c.v['exit'], 0.01), (2, 0, 0), release=2.5)
    tl.mark('release', r); tl.nodrag.append((r - 2, r + 7))
    seat(c, tl, 'thigh_t', dep=r + 8, arr=B['slam'] - 1); rack(c, tl, 'upper'); return mag(c, mode='hook', appear=r + 10)


def st18(c, tl):
    """Belt pour. A small snap stops dead on the latch frame. The gun goes down to the belt and turns over above the
    pouch, still; the thumb presses the release and the magazine pours off the underside past the pouch. A short
    shift and the gun is pressed onto the fresh magazine standing beside it: the change happens at the belt, out of
    view. Rolled upright as it rises, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; opener(c, tl, 'snap'); pos, rot = c.station('belt_t'); hov = np.array(pos) + (0.06, 0.10, -0.08)
    press(c, tl, hov, rot, B['cue'] + 2, r)
    seat(c, tl, 'belt_t', dep=r + 6, arr=B['slam'] - 1); rack(c, tl, 'punch'); return mag(c, appear=r + 9)


def st19(c, tl):
    """Muzzle-down tip. A tug back stops dead on the latch frame. The gun is held low in front of the belly and the
    muzzle tipped down and the gun rolled onto its right side, still: the magazine's axis now points forward, down and
    out; the thumb presses the release and it slides off the side of the gun by its weight. Down and up under the magazine hanging from the belt
    rig. Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; opener(c, tl, 'tug'); press(c, tl, (0.02, -0.12, -0.06), (-60, 0, -55), B['cue'] + 2, r)
    seat(c, tl, 'stomach_t', dep=r + 6); rack(c, tl, 'yank'); return mag(c)


def st20(c, tl):
    """Rattle off. The thumb presses the latch: a dip stops dead on its frame. The gun is held out in front, still;
    on the release frame the arm shoves it forward and back twice, short and sharp, the second stroke harder: each
    stop sends the magazine further up its rail until it hops off forward and drops. Down to the hip and pressed back
    onto the magazine there. Up, cocked back, punched forward on the cocking device."""
    B = c.B; k = c.P['k']; r = B['rel']; opener(c, tl, 'press'); p0 = np.array((0.0, 0.0, -0.02)); ru = (-6, 0, -3)
    tl.hold(B['cue'] + 2); tl.to(r - 3, p0, ru, 'drive', rlag=1); tl.hold(r)
    tl.to(r + 2, p0 + (0, 0, -0.04), ru, PUNCH, rlag=0); tl.to(r + 4, p0 + (0, 0, 0.01), ru, (1.6, 1.6), rlag=0); tl.to(r + 6, p0 + (0, 0.01, -0.05), ru, PUNCH, rlag=0)
    tl.kick(r + 6, (0, 0, 0.008 * k), (1.5 * k, 0, 0), attack=0.5, release=2.0); tl.mark('release', r); tl.nodrag.append((r, r + 7))
    seat(c, tl, 'hip_t', dep=r + 6); rack(c, tl, 'punch'); return mag(c)


PICKS = {'ST11': ('Flip and drop', st11), 'ST12': ('Belt knock-off', st12), 'ST13': ('Tip-forward throw', st13), 'ST14': ('Jerk down', st14), 'ST15': ('Inverted shake', st15),
         'ST16': ('Yank back', st16), 'ST17': ('Thigh knock-off', st17), 'ST18': ('Belt pour', st18), 'ST19': ('Muzzle-down tip', st19), 'ST20': ('Rattle off', st20)}
PARAMS = {}

if __name__ == '__main__': r2lib.main(sys.modules[__name__], sys.argv[1:])
